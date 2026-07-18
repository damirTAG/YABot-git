import asyncio
import json
import logging
import re
from typing import Any

import aiohttp

from config.settings import TELEGRAPH_ACCESS_TOKEN

TELEGRAPH_API_URL = 'https://api.telegra.ph'

# Узел контента Telegraph: строка или {"tag": ..., "attrs": ..., "children": [...]}
Node = str | dict[str, Any]

_FLOOD_WAIT_RE = re.compile(r'FLOOD_WAIT_(\d+)')

logger = logging.getLogger('mangagraph.telegraph')

class TelegraphError(Exception):
    def __init__(self, method: str, message: str):
        super().__init__(f'Telegraph API error in {method}: {message}')
        self.method = method
        self.message = message

class TelegraphClient:
    """
    Минимальный async-клиент Telegraph API (https://telegra.ph/api) на aiohttp.

    Покрывает только используемые методы: createAccount, createPage, editPage.
    Flood wait (ошибка FLOOD_WAIT_X) обрабатывается внутри `_request`
    повтором запроса после ожидания.

    Можно использовать самостоятельно:

        async with TelegraphClient() as telegraph:
            await telegraph.create_account(short_name='Damir')
            page = await telegraph.create_page('Title', [{'tag': 'p', 'children': ['Hi']}])

    Либо без контекстного менеджера — сессия создается лениво,
    закрывается через `await telegraph.close()`.

    Args:
        access_token: Токен существующего аккаунта Telegraph. Если не передан —
            вызовите `create_account`, токен сохранится в `self.access_token`.
    """

    def __init__(self, access_token: str | None = None):
        self.access_token = access_token
        self.flood_wait_count = 0
        self._session: aiohttp.ClientSession | None = None

    async def ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def __aenter__(self) -> 'TelegraphClient':
        await self.ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def _request(self, method: str, retries: int = 3, **params) -> dict[str, Any]:
        """POST-запрос к API. Ответ Telegraph: {"ok": true, "result": ...} либо
        {"ok": false, "error": "..."}."""
        session = await self.ensure_session()
        data = {key: value for key, value in params.items() if value is not None}

        for attempt in range(retries):
            async with session.post(f'{TELEGRAPH_API_URL}/{method}', data=data) as response:
                payload = await response.json()

            if payload.get('ok'):
                return payload['result']

            error = str(payload.get('error', 'unknown error'))
            flood = _FLOOD_WAIT_RE.fullmatch(error)
            if flood is None:
                raise TelegraphError(method, error)

            self.flood_wait_count += 1
            wait_time = max(int(flood.group(1)), 5)
            logger.info(
                f'Flood wait #{self.flood_wait_count}, '
                f'ждём {wait_time} сек. (попытка {attempt + 1}/{retries})'
            )
            await asyncio.sleep(wait_time)

        raise TelegraphError(method, f'flood wait не прошёл за {retries} попыток')

    async def create_account(
        self,
        short_name: str,
        author_name: str | None = None,
        author_url: str | None = None
    ) -> dict[str, Any]:
        """Создает аккаунт и сохраняет его access_token в клиенте."""
        result = await self._request(
            'createAccount',
            short_name=short_name,
            author_name=author_name,
            author_url=author_url
        )
        self.access_token = result['access_token']
        return result

    async def create_page(
        self,
        title: str,
        content: list[Node],
        author_name: str | None = None,
        author_url: str | None = None
    ) -> dict[str, Any]:
        """Создает страницу. Возвращает result с 'path' и 'url'."""
        return await self._request(
            'createPage',
            access_token=self.access_token,
            title=title,
            content=json.dumps(content, ensure_ascii=False),
            author_name=author_name,
            author_url=author_url
        )

    async def edit_page(
        self,
        path: str,
        title: str,
        content: list[Node],
        author_name: str | None = None,
        author_url: str | None = None
    ) -> dict[str, Any]:
        """Редактирует существующую страницу по ее path."""
        return await self._request(
            'editPage',
            access_token=self.access_token,
            path=path,
            title=title,
            content=json.dumps(content, ensure_ascii=False),
            author_name=author_name,
            author_url=author_url
        )
    
telegraph = TelegraphClient(access_token=TELEGRAPH_ACCESS_TOKEN)