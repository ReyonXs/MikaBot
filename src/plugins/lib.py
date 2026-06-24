from httpx import AsyncClient
from nonebot import get_driver

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'  # noqa: E501
}

class WebUtils:
    def __init__(self) -> None:
        self.client: AsyncClient | None = None

    async def startup(self) -> None:
        if self.client is None or self.client.is_closed:
            self.client = AsyncClient(headers=HEADERS)

    async def shutdown(self) -> None:
        if self.client is not None and not self.client.is_closed:
            await self.client.aclose()

    def get_client(self) -> AsyncClient:
        if self.client is None or self.client.is_closed:
            msg = 'AsyncClient 尚未初始化'
            raise RuntimeError(msg)
        return self.client


web_utils = WebUtils()
driver = get_driver()


@driver.on_startup
async def _() -> None:
    await web_utils.startup()


@driver.on_shutdown
async def _() -> None:
    await web_utils.shutdown()
