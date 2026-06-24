from enum import IntEnum, StrEnum

from furl import furl
from pydantic import BaseModel, ConfigDict, Field

HEADERS = {
    'Referer': 'https://www.pixiv.net/'
}
LOLICON_API = furl('https://api.lolicon.app/setu/v2')

class PixivImageQuality(StrEnum):
    MINI = 'mini'
    THUMB = 'thumb'
    SMALL = 'small'
    REGULAR = 'regular'
    ORIGINAL = 'original'

class R18Mode(IntEnum):
    NON_R18 = 0
    R18 = 1
    MIXED = 2

class LoliconConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    r18: R18Mode = R18Mode.NON_R18
    num: int = 1
    tag: list = Field(default_factory=list)
    size: PixivImageQuality = PixivImageQuality.SMALL
    proxy: furl = Field(default_factory=lambda: furl('i.pximg.net'))
    exclude_ai: bool = False

DEFAULT_LOLICON_CONFIG = LoliconConfig()
