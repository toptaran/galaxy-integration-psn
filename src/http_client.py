import logging

import aiohttp
from galaxy.api.errors import UnknownBackendResponse
from galaxy.http import handle_exception, create_client_session

OAUTH_LOGIN_REDIRECT_URL = "https://www.playstation.com/"

OAUTH_LOGIN_FINISH_URL = "https://ca.account.sony.com/api/v1/ssocookie"

OAUTH_LOGIN_URL = "https://web.np.playstation.com/api/session/v1/signin" \
                  "?redirect_uri=https://io.playstation.com/central/auth/login" \
                  "%3FpostSignInURL={redirect_url}" \
                  "%26cancelURL={redirect_url}" \
                  "&smcid=web:pdc"

JS_NPSSO_TOKEN_HELP_URL = "https://github.com/toptaran/galaxy-integration-psn/wiki/How-to-obtain-the-NPSSO-token"

JS_REPLACE_APPLY_URL = "https://my.account.sony.com/"

OAUTH_LOGIN_URL_FAKE = OAUTH_LOGIN_URL.format(redirect_url=OAUTH_LOGIN_REDIRECT_URL)

OAUTH_LOGIN_URL = OAUTH_LOGIN_URL.format(redirect_url=OAUTH_LOGIN_FINISH_URL)

REFRESH_COOKIES_URL = OAUTH_LOGIN_URL

AUTH_PARAMS = {
    "window_title": "Login to PlayStation Network",
    "window_width": 536,
    "window_height": 675,
    "start_uri": OAUTH_LOGIN_URL,
    "end_uri_regex": "^" + OAUTH_LOGIN_REDIRECT_URL + ".*",
    "end_uri": OAUTH_LOGIN_FINISH_URL
}
AUTH_PARAMS_MAIN = {
    "window_title": "FINISH AUTH PROCESS AT ANOTHER WINDOW AND CLICK NEXT",
    "window_width": 536,
    "window_height": 400,
    "start_uri": OAUTH_LOGIN_URL_FAKE,
    "end_uri_regex": "^" + OAUTH_LOGIN_REDIRECT_URL + ".*",
    "end_uri": OAUTH_LOGIN_REDIRECT_URL
}

JS_REPLACE_APPLY_DATA = r'''
            document.body.innerHTML = '';
            function validateForm() {{
                var errors = 0;
                var npssotoken = document.getElementById("npssotoken");
                var npssotokenval = npssotoken.value.trim()

                if (npssotokenval === "") {{
                    npssotoken.value = '';
                    errors++;
                }} else {{
                    var date = new Date();
                    date.setTime(date.getTime() + (24*60*60*1000));
                    expires = "; expires=" + date.toUTCString();
                    document.cookie = "npsso=" + (npssotokenval || "")  + expires + "; path=/";
                }}
                return errors === 0;
            }}

            setTimeout(() => {{
                document.write('<body bgcolor="FFFFFF" style="padding: 30px;">' +
                '<center><form novalidate="" action="{redirect_url}">' +
                '<span style="text-decoration: none; display: inline-block; font-size: 16px; font-weight: bold;' +
                'margin: 4px;">FINISH AUTH PROCESS AT ANOTHER WINDOW AND CLICK NEXT</span>' +
                '<button style="background-color: #008CBA; border: none; color: white; text-align: center; text-decoration: none;' +
                'display: inline-block; font-size: 16px; font-weight: bold; margin: 4px; cursor: pointer; padding: 14px 40px;">NEXT</button>' +
                '</form>' +
                '<span style="text-decoration: none; display: inline-block; font-size: 16px; font-weight: bold;' +
                'margin: 4px;">OR</span><br>' +
                '<form novalidate="" action="{redirect_url}" onsubmit="return validateForm()">' +
                '<span style="text-decoration: none; display: inline-block; font-size: 16px; font-weight: bold;' +
                'margin: 4px;">PUT NPSSO TOKEN</span><a style="background-color: #008CBA; border: none; color: white; text-align: center; text-decoration: none; padding:2px 10px"' +
                'href="{npsso_token_help_url}" target="_blank">?</a><br>' +
                '<input type="text" id="npssotoken" size=50 placeholder="Put NPSSO token here">' +
                '<button style="background-color: #008CBA; border: none; color: white; text-align: center; text-decoration: none;' +
                'display: inline-block; font-size: 16px; font-weight: bold; margin: 4px; cursor: pointer; padding: 14px 40px;">USE TOKEN</button>' +
                '</form>' +
                '</center></body>');
            }}, 1000);
'''
JS_REPLACE_APPLY_DATA = JS_REPLACE_APPLY_DATA.format_map({'redirect_url':OAUTH_LOGIN_REDIRECT_URL,'npsso_token_help_url':JS_NPSSO_TOKEN_HELP_URL})

AUTH_PARAMS_MAIN_JS = {r"^" + JS_REPLACE_APPLY_URL + ".*": [JS_REPLACE_APPLY_DATA]}


DEFAULT_TIMEOUT = 30


class CookieJar(aiohttp.CookieJar):
    def __init__(self):
        super().__init__()
        self._cookies_updated_callback = None

    def set_cookies_updated_callback(self, callback):
        self._cookies_updated_callback = callback

    def update_cookies(self, cookies, *args):
        super().update_cookies(cookies, *args)
        if cookies and self._cookies_updated_callback:
            self._cookies_updated_callback(list(self))


class HttpClient:

    def __init__(self):
        self._cookie_jar = CookieJar()
        self._session = create_client_session(cookie_jar=self._cookie_jar)

    async def close(self):
        await self._session.close()

    async def _request(self, method, url, *args, **kwargs):
        with handle_exception():
            return await self._session.request(method, url, *args, **kwargs)

    async def get(self, url, *args, **kwargs):
        silent = kwargs.pop('silent', False)
        get_json = kwargs.pop('get_json', True)
        response = await self._request("GET", *args, url=url, **kwargs)
        try:
            raw_response = '***' if silent else await response.text()
            logging.debug("Response for:\n{url}\n{data}".format(url=url, data=raw_response))
            return await response.json() if get_json else await response.text()
        except ValueError:
            logging.exception("Invalid response data for:\n{url}".format(url=url))
            raise UnknownBackendResponse()

    async def post(self, url, *args, **kwargs):
        logging.debug("Sending data:\n{url}".format(url=url))
        response = await self._request("POST", *args, url=url, **kwargs)
        logging.debug("Response for post:\n{url}\n{data}".format(url=url, data=await response.text()))
        return response

    def set_cookies_updated_callback(self, callback):
        self._cookie_jar.set_cookies_updated_callback(callback)

    def update_cookies(self, cookies):
        self._cookie_jar.update_cookies(cookies)

    async def refresh_cookies(self):
        await self.get(REFRESH_COOKIES_URL, silent=True, get_json=False)
