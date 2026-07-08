import json
import logging

import aiohttp
from galaxy.api.errors import AuthenticationRequired, UnknownBackendResponse
from galaxy.http import create_client_session, handle_exception

from psn.constants import REFRESH_COOKIES_URL

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
GRAPHQL_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

logger = logging.getLogger(__name__)


class CookieJar(aiohttp.CookieJar):
    def __init__(self):
        super().__init__()
        self._cookies_updated_callback = None

    def set_cookies_updated_callback(self, callback):
        self._cookies_updated_callback = callback

    def update_cookies(self, cookies, *args, **kwargs):
        super().update_cookies(cookies, *args, **kwargs)
        if cookies and self._cookies_updated_callback:
            self._cookies_updated_callback(list(self))


class HttpClient:
    def __init__(self):
        self._cookie_jar = CookieJar()
        self._session = create_client_session(
            cookie_jar=self._cookie_jar,
            timeout=REQUEST_TIMEOUT,
        )
        self._access_token = None
        self._api_session = create_client_session(
            cookie_jar=aiohttp.DummyCookieJar(),
            timeout=REQUEST_TIMEOUT,
            raise_for_status=False,
        )

    async def close(self):
        await self._session.close()
        await self._api_session.close()

    @property
    def cookie_jar(self):
        return self._cookie_jar

    def set_access_token(self, access_token):
        self._access_token = access_token

    def _auth_headers(self):
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        return {}

    async def _api_json_get(
        self, url: str, *, label: str = "API", not_found_ok: bool = False
    ):
        if not self._access_token:
            raise AuthenticationRequired("PlayStation access token is missing")

        headers = {**GRAPHQL_HEADERS, **self._auth_headers()}
        response = await self._api_session.get(url, headers=headers)
        body = await response.text()
        if response.status == 404 and not_found_ok:
            logger.debug("%s not found (404): %s", label, url)
            return None
        if response.status >= 400:
            logger.error(
                "%s request failed (%s):\n%s\n%s",
                label,
                response.status,
                url,
                body[:1000],
            )
            with handle_exception():
                response.raise_for_status()
        logger.debug("%s response for:\n%s\n%s", label, url, body[:2000])
        try:
            return json.loads(body)
        except ValueError as exc:
            logger.exception("Invalid %s response for:\n%s", label, url)
            raise UnknownBackendResponse() from exc

    async def graphql_get(self, url: str):
        return await self._api_json_get(url, label="GraphQL")

    async def api_get(self, url: str, *, not_found_ok: bool = False):
        return await self._api_json_get(url, label="REST", not_found_ok=not_found_ok)

    async def request(self, method, url, *args, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        headers.update(self._auth_headers())
        kwargs["headers"] = headers
        with handle_exception():
            return await self._session.request(method, url, *args, **kwargs)

    async def raw_request(self, method, url, *args, **kwargs):
        return await self._session.request(method, url, *args, **kwargs)

    async def _request(self, method, url, *args, **kwargs):
        return await self.request(method, url, *args, **kwargs)

    async def get(self, url, *args, **kwargs):
        silent = kwargs.pop("silent", False)
        get_json = kwargs.pop("get_json", True)
        response = await self._request("GET", url=url, *args, **kwargs)
        try:
            raw_response = "***" if silent else await response.text()
            logger.debug("Response for:\n%s\n%s", url, raw_response)
            if get_json:
                return await response.json()
            return await response.text()
        except ValueError:
            logger.exception("Invalid response data for:\n%s", url)
            raise UnknownBackendResponse()

    async def post(self, url, *args, **kwargs):
        logger.debug("Sending POST:\n%s", url)
        response = await self._request("POST", url=url, *args, **kwargs)
        logger.debug("Response for POST:\n%s\n%s", url, await response.text())
        return response

    def set_cookies_updated_callback(self, callback):
        self._cookie_jar.set_cookies_updated_callback(callback)

    def update_cookies(self, cookies, url=None):
        if url is not None:
            self._cookie_jar.update_cookies(cookies, response_url=url)
        else:
            self._cookie_jar.update_cookies(cookies)

    async def refresh_cookies(self):
        await self.get(REFRESH_COOKIES_URL, silent=True, get_json=False)
