from __future__ import annotations

import asyncio
import json
import mmap
import re
from typing import TYPE_CHECKING, cast

from nonebot import logger
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
)
from sqlalchemy.dialects.sqlite import insert

from src.plugins.lib import decode_hex_codepoints

from .config import (
    BATCH_SIZE,
    COMBINATIONS_VIEW_NAME,
    METADATA_FILENAME,
    MMAP_RELEASE_INTERVAL_BYTES,
    TABLE_NAMES,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from typing import BinaryIO

    from aiosqlite import Connection
    from sqlalchemy.ext.asyncio import AsyncSession

SCHEMA = MetaData()
METADATA = Table(
    TABLE_NAMES['metadata'],
    SCHEMA,
    Column('key', Text, primary_key=True),
    Column('value', Text, nullable=False),
    sqlite_with_rowid=False,
)
CODES = Table(
    TABLE_NAMES['code'],
    SCHEMA,
    Column('id', Integer, primary_key=True),
    Column('emoji', Text, nullable=False, unique=True),
    Column('code', Text, nullable=False),
)
DATES = Table(
    TABLE_NAMES['data'],
    SCHEMA,
    Column('id', Integer, primary_key=True),
    Column('image_date', Integer, nullable=False, unique=True),
)
PAIRS = Table(
    TABLE_NAMES['pair'],
    SCHEMA,
    Column('emoji1_id', Integer, ForeignKey(CODES.c.id), primary_key=True),
    Column('emoji2_id', Integer, ForeignKey(CODES.c.id), primary_key=True),
    Column(
        'date_id',
        Integer,
        ForeignKey(DATES.c.id, deferrable=True, initially='DEFERRED'),
        nullable=False,
    ),
    Column(
        'is_reversed', Integer, CheckConstraint('is_reversed IN (0, 1)'), nullable=False
    ),
    Column(
        'bidirectional',
        Integer,
        CheckConstraint('bidirectional IN (0, 1)'),
        nullable=False,
    ),
    sqlite_with_rowid=False,
)
VIEW_SQL = '''
CREATE VIEW {view} AS
WITH urls AS NOT MATERIALIZED (
    SELECT a.emoji AS emoji1, b.emoji AS emoji2, p.bidirectional,
           (SELECT value FROM {metadata} WHERE key = 'url_prefix') ||
           printf('%08d/', d.image_date) ||
           CASE WHEN p.is_reversed
               THEN b.code || '/' || b.code || '_' || a.code
               ELSE a.code || '/' || a.code || '_' || b.code
           END || '.png' AS url
    FROM {pair} AS p
    JOIN {code} AS a ON a.id = p.emoji1_id
    JOIN {code} AS b ON b.id = p.emoji2_id
    JOIN {data} AS d ON d.id = p.date_id
)
SELECT emoji1, emoji2, url FROM urls
UNION ALL
SELECT emoji2, emoji1, url FROM urls WHERE bidirectional;
'''.strip()

DATA_START = b'"data":{'
COMBINATIONS_START = b'"combinations":{'
COMBO_PREFIX = re.compile(rb'"([^"]+)":\[\{"gStaticUrl":"([^"]*+)(?<!\\)"')
QUOTE_BYTE = b'"'
RIGHT_BRACKET_BYTE = b']'

BACKSLASH = ord('\\')
COMMA = ord(',')
RIGHT_BRACE = ord('}')


class MetadataParseError(ValueError):
    @classmethod
    def missing_marker(cls, marker: bytes) -> MetadataParseError:
        return cls(f'未找到 JSON 标记 {marker.decode("ascii")}')

    @classmethod
    def unterminated_string(cls) -> MetadataParseError:
        return cls('JSON 字符串缺少结束引号')

    @classmethod
    def missing_asset_list_end(cls) -> MetadataParseError:
        return cls('组合的图片数组缺少结束方括号')


def image_rows(combinations: dict, codes: dict, prefix: str) -> Iterator:
    for emoji1, partners in sorted(combinations.items()):
        for emoji2, url in sorted(partners.items()):
            reverse_url = combinations.get(emoji2, {}).get(emoji1)
            bidirectional = emoji1 != emoji2 and reverse_url == url
            if bidirectional and emoji1 > emoji2:
                continue
            _, date, folder, _ = url.rsplit('/', 3)
            left, right = codes[emoji1], codes[emoji2]
            is_reversed = folder != left
            if is_reversed:
                left, right = right, left
            image_date = int(date)
            if url != f'{prefix}{image_date:08d}/{left}/{left}_{right}.png':
                msg = f'表情组合 {emoji1}/{emoji2} 的图片地址不符'
                raise MetadataParseError(msg)
            yield emoji1, emoji2, image_date, is_reversed, bidirectional


def index_after(raw_data: bytes | mmap.mmap, marker: bytes, start: int = 0) -> int:
    index = raw_data.find(marker, start)
    if index < 0:
        raise MetadataParseError.missing_marker(marker)
    return index + len(marker)


def find_string_end(raw_data: bytes | mmap.mmap, start: int) -> int:
    end = raw_data.find(QUOTE_BYTE, start)
    while end >= 0:
        backslashes = 0
        cursor = end - 1
        while cursor >= start and raw_data[cursor] == BACKSLASH:
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return end
        end = raw_data.find(QUOTE_BYTE, end + 1)
    raise MetadataParseError.unterminated_string()


def read_json_string(raw_data: bytes | mmap.mmap, start: int) -> tuple:
    end = find_string_end(raw_data, start + 1)
    return raw_data[start + 1 : end], end + 1


def read_partners(raw_data: bytes | mmap.mmap, cursor: int) -> tuple:
    match_asset = COMBO_PREFIX.match
    combinations = {}
    while raw_data[cursor] != RIGHT_BRACE:
        match = match_asset(raw_data, cursor)
        if match is None:
            msg = '组合记录不符合紧凑格式'
            raise MetadataParseError(msg)
        combo_hex, url = match.groups()
        if BACKSLASH in url:
            msg = '图片地址含有 JSON 转义字符'
            raise MetadataParseError(msg)

        image_url = url.decode('ascii')
        combinations[decode_hex_codepoints(combo_hex)] = image_url

        cursor = raw_data.find(RIGHT_BRACKET_BYTE, match.end())
        if cursor < 0:
            raise MetadataParseError.missing_asset_list_end()
        cursor += 1
        if raw_data[cursor] == COMMA:
            cursor += 1
    return combinations, cursor


def build_new_data(raw_data: bytes | mmap.mmap) -> dict:
    cursor = index_after(raw_data, DATA_START)
    result = {}
    advise = getattr(raw_data, 'madvise', None)
    discard_pages = getattr(mmap, 'MADV_DONTNEED', None)
    released = 0

    while raw_data[cursor] != RIGHT_BRACE:
        if (
            advise is not None
            and discard_pages is not None
            and cursor - released >= MMAP_RELEASE_INTERVAL_BYTES
        ):
            end = cursor - cursor % mmap.PAGESIZE
            try:
                advise(discard_pages, released, end - released)
            except OSError:
                advise = None
            released = end

        base_hex, cursor = read_json_string(raw_data, cursor)

        start = index_after(raw_data, COMBINATIONS_START, cursor)
        if raw_data.find(b'}', cursor, start) >= 0:
            msg = '无法定位当前表情的 combinations 字段'
            raise MetadataParseError(msg)
        combinations, cursor = read_partners(raw_data, start)
        result[decode_hex_codepoints(base_hex)] = combinations

        cursor += 1
        if raw_data[cursor] != RIGHT_BRACE:
            msg = 'combinations 后还有其他字段'
            raise MetadataParseError(msg)
        cursor += 1
        if raw_data[cursor] == COMMA:
            cursor += 1

    return result


def parse_metadata_json(source: BinaryIO) -> dict:
    try:
        document = json.load(source)
    except json.JSONDecodeError as exc:
        msg = f'{METADATA_FILENAME} 格式无效 (第 {exc.lineno} 行, 第 {exc.colno} 列)'
        raise MetadataParseError(msg) from exc
    if not isinstance(document, dict) or not isinstance(document.get('data'), dict):
        msg = f'{METADATA_FILENAME} 缺少有效的 data 对象'
        raise MetadataParseError(msg)
    result = {}
    for base_hex, entry in document['data'].items():
        if not isinstance(entry, dict) or not isinstance(
            entry.get('combinations'), dict
        ):
            msg = f'{base_hex} 缺少有效的 combinations 对象'
            raise MetadataParseError(msg)
        partners = {}
        for combo_hex, assets in entry['combinations'].items():
            if (
                not isinstance(assets, list)
                or not assets
                or not isinstance(assets[0], dict)
            ):
                msg = f'表情组合 {base_hex}/{combo_hex} 缺少图片记录'
                raise MetadataParseError(msg)
            url = assets[0].get('gStaticUrl')
            if not isinstance(url, str) or not url:
                msg = f'表情组合 {base_hex}/{combo_hex} 缺少有效的 gStaticUrl'
                raise MetadataParseError(msg)
            partners[decode_hex_codepoints(combo_hex.encode('ascii'))] = url
        result[decode_hex_codepoints(base_hex.encode('ascii'))] = partners
    return result


def read_combinations(metadata_path: Path) -> dict:
    with metadata_path.open('rb') as source:
        try:
            with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as raw:
                return build_new_data(raw)
        except (IndexError, ValueError, OverflowError) as exc:
            logger.warning(f'改用标准 JSON 解析器 ({exc})')

        source.seek(0)
        return parse_metadata_json(source)


def prepare_metadata(metadata_path: Path) -> tuple:
    combinations = read_combinations(metadata_path)

    first_url = next(
        (url for partners in combinations.values() for url in partners.values()),
        None,
    )
    if not first_url:
        msg = f'{metadata_path.name} 中没有可导入的组合'
        raise ValueError(msg)
    prefix = first_url.rsplit('/', 3)[0] + '/'

    emojis = set(combinations)
    for partners in combinations.values():
        emojis.update(partners)
    emoji_ids = {emoji: i for i, emoji in enumerate(sorted(emojis))}
    codes = {emoji: '-'.join(f'u{ord(ch):x}' for ch in emoji) for emoji in emojis}
    date_ids: dict = {}

    code_rows = [
        {'id': i, 'emoji': emoji, 'code': codes[emoji]}
        for emoji, i in emoji_ids.items()
    ]
    pair_rows = [
        {
            'emoji1_id': emoji_ids[left],
            'emoji2_id': emoji_ids[right],
            'date_id': date_ids.setdefault(date, len(date_ids)),
            'is_reversed': is_reversed,
            'bidirectional': bidirectional,
        }
        for left, right, date, is_reversed, bidirectional in image_rows(
            combinations, codes, prefix
        )
    ]
    date_rows = [{'id': i, 'image_date': date} for date, i in date_ids.items()]
    return prefix, code_rows, date_rows, pair_rows


async def import_metadata(
    session: AsyncSession, metadata_path: Path, sha: str
) -> frozenset:
    prefix, codes, dates, pairs = await asyncio.to_thread(
        prepare_metadata, metadata_path
    )
    conn = await session.connection()
    raw = await conn.get_raw_connection()
    driver = cast('Connection', raw.driver_connection)
    if not driver.in_transaction:
        await conn.exec_driver_sql('BEGIN IMMEDIATE')

    await conn.run_sync(SCHEMA.create_all)
    quote = conn.dialect.identifier_preparer.quote_identifier
    names = {key: quote(name) for key, name in TABLE_NAMES.items()}
    view_name = quote(COMBINATIONS_VIEW_NAME)
    await conn.exec_driver_sql(f'DROP VIEW IF EXISTS {view_name}')
    await conn.exec_driver_sql(VIEW_SQL.format(view=view_name, **names))
    for table in (PAIRS, DATES, CODES):
        await session.execute(table.delete())

    update_metadata = insert(METADATA)
    await session.execute(
        update_metadata.on_conflict_do_update(
            index_elements=[METADATA.c.key],
            set_={'value': update_metadata.excluded.value},
        ),
        [{'key': 'url_prefix', 'value': prefix}, {'key': 'sha', 'value': sha}],
    )
    for table, rows in ((CODES, codes), (DATES, dates), (PAIRS, pairs)):
        for start in range(0, len(rows), BATCH_SIZE):
            await session.execute(table.insert(), rows[start : start + BATCH_SIZE])
    return frozenset(row['emoji'] for row in codes)
