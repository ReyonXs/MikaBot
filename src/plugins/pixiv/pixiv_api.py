import asyncio

from httpx import HTTPError
from nonebot import logger

from src.plugins.lib import web_utils

from .config import HEADERS


async def get_pixiv_data(pid: int) -> dict:
    raw_data, raw_urls = await asyncio.gather(
        _get_illust_data(pid), _get_images_data(pid)
    )
    data = _parse_illust_data(raw_data)
    urls = _parse_images_data(raw_urls)
    if data and urls:
        data['urls'] = urls
        return data
    return {}


async def _get_images_data(pid: int) -> dict:
    client = web_utils.get_client()
    try:
        response = await client.get(
            f'https://www.pixiv.net/ajax/illust/{pid}/pages',
            headers=HEADERS
        )
        response.raise_for_status()

        return response.json()
    except HTTPError as exc:
        logger.error(f'图片获取失败: {exc!r}')
        return {}


def _parse_images_data(raw_json: dict) -> list:
    body = raw_json.get('body')
    if raw_json.get('error') or not isinstance(body, list):
        return []
    return [item.get('urls', {}) for item in body]


async def _get_illust_data(pid: int) -> dict:
    client = web_utils.get_client()
    try:
        response = await client.get(
            f'https://www.pixiv.net/ajax/illust/{pid}'
        )
        response.raise_for_status()

        return response.json()
    except HTTPError as exc:
        logger.error(f'图片数据请求失败: {exc!r}')
        return {}


def _parse_illust_data(raw_json: dict) -> dict:
    body = raw_json.get('body')
    if raw_json.get('error') or not isinstance(body, dict):
        return {}
    return {
        'title': body.get('illustTitle') or body.get('title'),
        'userName': body.get('userName'),
        'xRestrict': body.get('xRestrict'),
    }
