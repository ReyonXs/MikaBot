import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import httpx
from nonebot import get_driver, logger, require
from sqlalchemy import inspect, select
from sqlalchemy.exc import OperationalError

from src.plugins.lib import BlobVerificationError

require('nonebot_plugin_apscheduler')
require('nonebot_plugin_orm')
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_orm import get_session

from .config import (
    COMBINATIONS_VIEW_NAME,
    RETRY_DELAY_MINUTES,
    RETRYABLE_HTTP_STATUSES,
    TABLE_NAMES,
    UPDATE_INTERVAL_DAYS,
)
from .metadata import METADATA
from .rebuild import rebuild
from .utils import get_metadata_entry

driver = get_driver()
check_lock = asyncio.Lock()


async def check_tables() -> None:
    async with get_session() as session:
        conn = await session.connection()
        existing_tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
        missing_tables = set(TABLE_NAMES.values()).difference(existing_tables)
        views = await conn.run_sync(lambda c: inspect(c).get_view_names())
        if not missing_tables and COMBINATIONS_VIEW_NAME in views:
            stored_sha = await session.scalar(
                select(METADATA.c.value).where(METADATA.c.key == 'sha')
            )
        else:
            stored_sha = None

    entry = await get_metadata_entry()
    if stored_sha != entry['sha']:
        await rebuild(entry)
        logger.info('元数据已更新')
    else:
        logger.debug('元数据已是最新版本')


def is_retryable(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        headers = error.response.headers
        if error.response.status_code == HTTPStatus.FORBIDDEN:
            return (
                'retry-after' in headers or headers.get('x-ratelimit-remaining') == '0'
            )
        return error.response.status_code in RETRYABLE_HTTP_STATUSES
    if isinstance(error, OperationalError):
        code = getattr(error.orig, 'sqlite_errorcode', 0)
        return code & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    return isinstance(
        error,
        (
            httpx.NetworkError,
            httpx.TimeoutException,
            httpx.RemoteProtocolError,
            httpx.ProxyError,
            BlobVerificationError,
        ),
    )


def schedule_check(delay: timedelta) -> None:
    scheduler.add_job(
        run_check,
        'date',
        run_date=datetime.now(UTC) + delay,
        id='emoji_kitchen_check_updates',
        replace_existing=True,
        misfire_grace_time=None,
    )


@logger.catch(message='元数据更新失败, 本轮停止重试')
async def run_check() -> None:
    try:
        async with check_lock:
            await check_tables()
    except (httpx.HTTPError, OperationalError, BlobVerificationError) as exc:
        if not is_retryable(exc):
            raise
        schedule_check(timedelta(minutes=RETRY_DELAY_MINUTES))
        logger.warning(f'元数据更新失败, {RETRY_DELAY_MINUTES} 分钟后重试 ({exc!r})')


@scheduler.scheduled_job(
    'interval',
    days=UPDATE_INTERVAL_DAYS,
    id='emoji_kitchen_weekly_update',
    coalesce=True,
    misfire_grace_time=None,
)
async def schedule_weekly_update() -> None:
    schedule_check(timedelta(0))


@driver.on_startup
@logger.catch(message='启动检查调度失败')
async def _() -> None:
    schedule_check(timedelta(0))
