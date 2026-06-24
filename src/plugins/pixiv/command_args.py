from typing import Literal

from .config import LoliconConfig, PixivImageQuality, R18Mode

QualityArg = Literal[
    'mini',
    'thumb',
    'small',
    'regular',
    'original',
    '1',
    '2',
    '3',
    '4',
    '5',
]

QUALITY_ALIAS: dict[QualityArg, PixivImageQuality] = {
    'mini': PixivImageQuality.MINI,
    'thumb': PixivImageQuality.THUMB,
    'small': PixivImageQuality.SMALL,
    'regular': PixivImageQuality.REGULAR,
    'original': PixivImageQuality.ORIGINAL,
    '1': PixivImageQuality.MINI,
    '2': PixivImageQuality.THUMB,
    '3': PixivImageQuality.SMALL,
    '4': PixivImageQuality.REGULAR,
    '5': PixivImageQuality.ORIGINAL,
}


def resolve_quality(quality: QualityArg | None) -> PixivImageQuality:
    if quality is None:
        return LoliconConfig().size
    return QUALITY_ALIAS[quality]


def build_lolicon_config(
    *,
    tags: list[str],
    r18: bool,
    num: int | None,
    quality: PixivImageQuality,
    exclude_ai: bool,
) -> LoliconConfig:
    return LoliconConfig(
        r18=R18Mode.R18 if r18 else R18Mode.NON_R18,
        num=num or 1,
        tag=tags,
        size=quality,
        exclude_ai=exclude_ai,
    )
