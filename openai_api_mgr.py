from config import Config

from openai import OpenAI, AsyncOpenAI
from httpx_socks import SyncProxyTransport, AsyncProxyTransport
import httpx

class OpenAI_API_Manager:
    def __init__(self) -> None:
        self.openai_api_sync  = None
        self.openai_api_async = None

    @staticmethod
    def get_sync() -> OpenAI:
        return OpenAI(
            api_key=Config.OPENAI_TOKEN,
            http_client=httpx.Client(
                transport=SyncProxyTransport.from_url(Config.OPENAI_PROXY),
                timeout=120.0
            ) if len(Config.OPENAI_PROXY) > 0 else None,
            timeout=120.0
        )

    @staticmethod
    def get_async() -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=Config.OPENAI_TOKEN,
            http_client=httpx.AsyncClient(
                transport=AsyncProxyTransport.from_url(Config.OPENAI_PROXY),
                timeout=120.0
            ) 
            if len(Config.OPENAI_PROXY) > 0 else
            httpx.AsyncClient(
                headers=[('Connection', 'close')],
                timeout=120.0
            ),
            timeout=120.0
        )

    def __enter__(self) -> OpenAI:
        if self.openai_api_sync is None:
            self.openai_api_sync = OpenAI_API_Manager.get_sync()
        return self.openai_api_sync

    def __exit__(self, exc_type, exc_val, exc_tb):
        return exc_val is None

    async def __aenter__(self) -> AsyncOpenAI:
        if self.openai_api_async is None:
            self.openai_api_async = OpenAI_API_Manager.get_async()
        return self.openai_api_async

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return exc_val is None
