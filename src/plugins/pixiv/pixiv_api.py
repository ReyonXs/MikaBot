from httpx import HTTPError
from nonebot import logger

from src.plugins.lib import web_utils

from .config import HEADERS


async def get_pixiv_data(pid: int) -> dict:
    return _parse_illust_data(await _get_illust_data(pid))


async def _get_illust_data(pid: int) -> dict:
    client = web_utils.get_client()
    try:
        response = await client.get(
            f'https://www.pixiv.net/ajax/illust/{pid}',
            headers=HEADERS,
        )
        response.raise_for_status()

        return response.json()
    except HTTPError as exc:
        logger.error(f'图片数据请求失败: {exc}')
        return {}


def _parse_illust_data(raw_json: dict) -> dict:
    body = raw_json.get('body', {})
    return {
        'title': body.get('illustTitle') or body.get('title'),
        'urls': body.get('urls'),
        'userName': body.get('userName'),
    }
