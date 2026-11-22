import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Final

import cv2
import numpy as np
from nonebot import get_driver
from numba import njit, prange
from PIL import Image

DEFAULT_INNER_SCALE: Final = 0.8
DEFAULT_COVER_SCALE: Final = 0.4
DEFAULT_INNER_WEIGHT: Final = 0.7
BLUR_PREVIEW_SIZE: Final = 16
BLUR_BRIGHTNESS: Final = 0.65
MAX_CHANNEL_VALUE: Final = 255.0
VISIBLE_ALPHA_THRESHOLD: Final = 0.5
THREAD_POOL_MAX_WORKERS: Final = 1

_THREAD_POOL = ThreadPoolExecutor(
    max_workers=THREAD_POOL_MAX_WORKERS,
    thread_name_prefix='mirage-colored',
)
_driver = get_driver()


async def generate(
    inner_image: Image.Image,
    cover_image: Image.Image | None = None,
    *,
    inner_scale: float = DEFAULT_INNER_SCALE,
    cover_scale: float = DEFAULT_COVER_SCALE,
    inner_weight: float = DEFAULT_INNER_WEIGHT,
) -> Image.Image:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _THREAD_POOL,
        _process,
        inner_image,
        cover_image,
        inner_scale,
        cover_scale,
        inner_weight,
    )


def _warmup() -> None:
    dummy = np.empty((1, 1, 3), dtype=np.uint8)
    _render(
        dummy,
        dummy,
        DEFAULT_INNER_SCALE,
        DEFAULT_COVER_SCALE,
        DEFAULT_INNER_WEIGHT,
    )


@_driver.on_startup
async def _() -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_THREAD_POOL, _warmup)


def _process(
    inner_image: Image.Image,
    cover_image: Image.Image | None,
    inner_scale: float,
    cover_scale: float,
    inner_weight: float,
) -> Image.Image:
    inner = _to_rgb(inner_image)
    cover = (
        _make_cover(inner)
        if cover_image is None
        else _fit_cover_to_inner(_to_rgb(cover_image), inner)
    )
    rgba = _render(inner, cover, inner_scale, cover_scale, inner_weight)
    return Image.fromarray(rgba, 'RGBA')


def _to_rgb(image: Image.Image) -> np.ndarray:
    if image.mode == 'RGB':
        return np.ascontiguousarray(np.asarray(image))

    return np.ascontiguousarray(np.asarray(image.convert('RGB')))


def _make_cover(
    data: np.ndarray,
) -> np.ndarray:
    """从 inner 生成低频 cover，先极小化下采样再线性放大。"""
    height, width = data.shape[:2]
    scale = BLUR_PREVIEW_SIZE / max(width, height)
    preview_width = max(1, round(width * scale))
    preview_height = max(1, round(height * scale))

    preview = cv2.resize(
        data,
        (preview_width, preview_height),
        interpolation=cv2.INTER_AREA,
    )
    if BLUR_BRIGHTNESS != 1.0:
        preview = cv2.convertScaleAbs(preview, alpha=BLUR_BRIGHTNESS, beta=0)

    return cv2.resize(
        preview,
        (width, height),
        interpolation=cv2.INTER_LINEAR,
    )


def _fit_cover_to_inner(cover: np.ndarray, inner: np.ndarray) -> np.ndarray:
    """按 inner 宽高比居中裁剪 cover，并缩放到相同尺寸。"""
    inner_height, inner_width = inner.shape[:2]
    cover_height, cover_width = cover.shape[:2]
    if (cover_width, cover_height) == (inner_width, inner_height):
        return cover

    target_ratio = inner_width / inner_height
    current_ratio = cover_width / cover_height
    if current_ratio < target_ratio:
        crop_width = cover_width
        crop_height = max(1, round(cover_width / target_ratio))
    else:
        crop_width = max(1, round(cover_height * target_ratio))
        crop_height = cover_height

    start_x = (cover_width - crop_width) // 2
    start_y = (cover_height - crop_height) // 2
    cropped = cover[
        start_y : start_y + crop_height,
        start_x : start_x + crop_width,
    ]
    return cv2.resize(
        cropped,
        (inner_width, inner_height),
        interpolation=cv2.INTER_LINEAR,
    )


@njit(cache=True, fastmath=True, nogil=True, boundscheck=False, inline='always')
def _clip_channel_value(value: np.float32, max_channel_value: np.float32) -> np.float32:
    return max(np.float32(0.0), min(max_channel_value, value))


@njit(cache=True, fastmath=True, nogil=True, boundscheck=False, inline='always')
def _pack_rgba(
    r: np.uint32,
    g: np.uint32,
    b: np.uint32,
    a: np.uint32,
) -> np.uint32:
    return r | (g << np.uint32(8)) | (b << np.uint32(16)) | (a << np.uint32(24))


@njit(cache=True, fastmath=True, nogil=True, boundscheck=False, inline='always')
def _compute_pixel(  # noqa: PLR0913, PLR0917
    ir: np.float32,
    ig: np.float32,
    ib: np.float32,
    cr: np.float32,
    cg: np.float32,
    cb: np.float32,
    cover_scale: np.float32,
    scale_i_weight_i: np.float32,
    cover_weight_scale: np.float32,
    const_cw_255: np.float32,
    max_channel_value: np.float32,
    visible_alpha_threshold: np.float32,
    rw_i: np.float32,
    gw_i: np.float32,
    bw_i: np.float32,
    rw_c: np.float32,
    gw_c: np.float32,
    bw_c: np.float32,
) -> np.uint32:
    alpha = (
        cover_scale
        + (ir * rw_i + ig * gw_i + ib * bw_i)
        - (cr * rw_c + cg * gw_c + cb * bw_c)
    )
    alpha = max(np.float32(0.0), min(np.float32(1.0), alpha))
    alpha255 = alpha * np.float32(255.0)

    if alpha255 >= visible_alpha_threshold:
        inv_alpha = np.float32(1.0) / alpha
        inner_factor = scale_i_weight_i * inv_alpha
        cover_factor = cover_weight_scale * inv_alpha

        value = (
            ir * inner_factor + (cr - np.float32(255.0)) * cover_factor + const_cw_255
        )
        value = _clip_channel_value(value, max_channel_value)
        r = np.uint32(np.uint8(value))

        value = (
            ig * inner_factor + (cg - np.float32(255.0)) * cover_factor + const_cw_255
        )
        value = _clip_channel_value(value, max_channel_value)
        g = np.uint32(np.uint8(value))

        value = (
            ib * inner_factor + (cb - np.float32(255.0)) * cover_factor + const_cw_255
        )
        value = _clip_channel_value(value, max_channel_value)
        b = np.uint32(np.uint8(value))
    else:
        r = np.uint32(0)
        g = np.uint32(0)
        b = np.uint32(0)

    a = np.uint32(np.uint8(alpha255 + np.float32(0.5)))
    return _pack_rgba(r, g, b, a)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, boundscheck=False)
def _render(
    inner: np.ndarray,
    cover: np.ndarray,
    inner_scale_value: float,
    cover_scale_value: float,
    inner_weight_value: float,
) -> np.ndarray:
    height, width = inner.shape[:2]
    total_pixels = height * width
    inner_flat = inner.ravel()
    cover_flat = cover.ravel()
    output_uint32_flat = np.empty(total_pixels, dtype=np.uint32)
    max_channel_value = np.float32(MAX_CHANNEL_VALUE)
    visible_alpha_threshold = np.float32(VISIBLE_ALPHA_THRESHOLD)
    inner_scale = np.float32(inner_scale_value)
    cover_scale = np.float32(1.0 - cover_scale_value)
    inner_weight = np.float32(inner_weight_value)
    cover_weight = np.float32(1.0 - inner_weight)
    scale_i_255 = np.float32(inner_scale / 255.0)
    cover_scale_255 = np.float32(cover_scale / 255.0)
    scale_i_weight_i = np.float32(inner_scale * inner_weight)
    cover_weight_scale = np.float32(cover_weight * cover_scale)
    const_cw_255 = np.float32(cover_weight * 255.0 + 0.5)
    red_weight = np.float32(0.299)
    green_weight = np.float32(0.587)
    blue_weight = np.float32(0.114)
    rw_i = np.float32(red_weight * scale_i_255)
    gw_i = np.float32(green_weight * scale_i_255)
    bw_i = np.float32(blue_weight * scale_i_255)
    rw_c = np.float32(red_weight * cover_scale_255)
    gw_c = np.float32(green_weight * cover_scale_255)
    bw_c = np.float32(blue_weight * cover_scale_255)

    for i in prange(total_pixels):
        idx = i * 3
        ir = np.float32(inner_flat[idx])
        ig = np.float32(inner_flat[idx + 1])
        ib = np.float32(inner_flat[idx + 2])
        cr = np.float32(cover_flat[idx])
        cg = np.float32(cover_flat[idx + 1])
        cb = np.float32(cover_flat[idx + 2])

        output_uint32_flat[i] = _compute_pixel(
            ir,
            ig,
            ib,
            cr,
            cg,
            cb,
            cover_scale,
            scale_i_weight_i,
            cover_weight_scale,
            const_cw_255,
            max_channel_value,
            visible_alpha_threshold,
            rw_i,
            gw_i,
            bw_i,
            rw_c,
            gw_c,
            bw_c,
        )

    return output_uint32_flat.view(np.uint8).reshape((height, width, 4))

__all__ = ['generate']
