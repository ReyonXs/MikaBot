from __future__ import annotations

from hashlib import file_digest, sha1
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class BlobVerificationError(ValueError):
    pass


def verify_blob(path: Path, size: int, sha: str) -> None:
    actual_size = path.stat().st_size
    if actual_size != size:
        msg = f'{path.name} 大小不符 (预期 {size} 字节, 实际 {actual_size} 字节)'
        raise BlobVerificationError(msg)
    digest = sha1(f'blob {size}\0'.encode('ascii'), usedforsecurity=False)
    with path.open('rb') as source:
        actual_sha = file_digest(source, lambda: digest).hexdigest()
    if actual_sha != sha:
        msg = f'{path.name} 的 SHA 校验失败'
        raise BlobVerificationError(msg)
