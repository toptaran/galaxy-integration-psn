import logging
import sys
import threading
from typing import List, Any, Dict

from galaxy.api.consts import Platform
from galaxy.api.errors import InvalidCredentials
from galaxy.api.plugin import Plugin, create_and_run_plugin
from galaxy.api.types import Authentication, Achievement, Game, GameTime, NextStep

from http_client import HttpClient
from http_client import OAUTH_LOGIN_URL, OAUTH_LOGIN_REDIRECT_URL, OAUTH_LOGIN_FINISH_URL, OAUTH_LOGIN_URL_FAKE
from cef_client import get_npsso_token
from psnawp_client import PSNAWPClient, PsnGame

from version import __version__

AUTH_PARAMS = {
    "window_title": "Login to PlayStation Network",
    "window_width": 536,
    "window_height": 675,
    "start_uri": OAUTH_LOGIN_URL,
    "end_uri_regex": "^" + OAUTH_LOGIN_REDIRECT_URL + ".*",
    "end_uri": OAUTH_LOGIN_FINISH_URL
}
AUTH_PARAMS_FAKE = {
    "window_title": "FINISH AUTH PROCESS AT ANOTHER WINDOW AND CLICK NEXT",
    "window_width": 536,
    "window_height": 200,
    "start_uri": OAUTH_LOGIN_URL_FAKE,
    "end_uri_regex": "^" + OAUTH_LOGIN_REDIRECT_URL + ".*",
    "end_uri": OAUTH_LOGIN_REDIRECT_URL
}

JS = {r"^https://my\.account\.sony\.com/.*": [
         r'''
                 document.body.innerHTML = '';
                 setTimeout(() => {
                     document.write('<body bgcolor="FFFFFF" style="padding: 30px;">' +
                     '<center><form novalidate="" action="https://www.playstation.com/">' +
                     '<span style="text-decoration: none; display: inline-block; font-size: 16px; font-weight: bold;' +
                     'margin: 4px;">FINISH AUTH PROCESS AT ANOTHER WINDOW AND CLICK NEXT</span>' +
                     '<button style="background-color: #008CBA; border: none; color: white; text-align: center; text-decoration: none;' +
                     'display: inline-block; font-size: 16px; font-weight: bold; margin: 4px; cursor: pointer; padding: 14px 40px;">NEXT</button>' +
                     '</form></center></body>');
                 }, 1000);
         '''
     ]}


logger = logging.getLogger(__name__)


class PSNPlugin(Plugin):
    def __init__(self, reader, writer, token):
        super().__init__(Platform.Psn, __version__, reader, writer, token)
        self._http_client = HttpClient()
        self._npsso_token = ""
        self._psnawp_client = PSNAWPClient(self._npsso_token)
        self._cef_thread = threading.Thread(target=get_npsso_token, args=(AUTH_PARAMS, self, ))
        logging.getLogger("urllib3").setLevel(logging.FATAL)
        logging.getLogger("psnawp_client").setLevel(logging.DEBUG)

    async def _do_auth(self, cookies):
        if not cookies:
            raise InvalidCredentials()

        self._npsso_token = cookies.get("npsso")
        self._psnawp_client.set_new_npsso_token(self._npsso_token)
        user_id, user_name = await self._psnawp_client.get_own_user_info()
        if user_id == "":
            raise InvalidCredentials()

        self._psnawp_client.start_init(self)
        return Authentication(user_id=user_id, user_name=user_name)

    async def authenticate(self, stored_credentials=None):
        stored_cookies = stored_credentials.get("cookies") if stored_credentials else None
        if not stored_cookies:
            # clear and push cache, client do not autoremove it
            self.persistent_cache.clear()
            self.push_cache()
            # need to use threading, asyncio.run() makes loop exception
            self._cef_thread.start()
            # need to use nextstep, because main thread will crash plugin if will not get answer in 20 seconds
            return NextStep("web_session", AUTH_PARAMS_FAKE, cookies=[], js=JS)

        auth_info = await self._do_auth(stored_cookies)
        return auth_info

    async def pass_login_credentials(self, step, credentials, cookies):
        #cookies = {cookie["name"]: cookie["value"] for cookie in cookies}
        cookies = {"npsso": self._npsso_token}
        self._store_cookies(cookies)
        return await self._do_auth(cookies)

    def _store_cookies(self, cookies):
        credentials = {
            "cookies": cookies
        }
        self.store_credentials(credentials)

    def _update_stored_cookies(self, morsels):
        cookies = {}
        for morsel in morsels:
            cookies[morsel.key] = morsel.value
        self._store_cookies(cookies)

    '''
    #comment it for now, maybe implement later if someone need it
    async def get_subscriptions(self) -> List[Subscription]:
        is_plus_active = await self._psn_client.get_psplus_status()
        return [Subscription(subscription_name="PlayStation PLUS", end_time=None, owned=is_plus_active)]

    async def get_subscription_games(self, subscription_name: str, context: Any) -> AsyncGenerator[List[SubscriptionGame], None]:
        yield await self._psn_client.get_subscription_games()
    '''

    async def get_owned_games(self) -> List[Game]:
        return self._psnawp_client.get_owned_games(self)

    async def get_unlocked_achievements(self, game_id: str, context: Any) -> List[Achievement]:
        return self._psnawp_client.get_unlocked_achievements(self, game_id)

    async def get_game_time(self, game_id: str, context: Any) -> GameTime:
        return self._psnawp_client.get_game_time(self, game_id)

    def tick(self) -> None:
        self._psnawp_client.tick(self)

    async def shutdown(self):
        await self._http_client.close()


def main():
    create_and_run_plugin(PSNPlugin, sys.argv)


if __name__ == "__main__":
    main()
