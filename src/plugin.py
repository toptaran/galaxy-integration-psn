import logging
import sys

if sys.version_info < (3, 13):
    raise ImportError(
        "This plugin requires GOG Galaxy 2.1.3 or newer (bundled Python 3.13). "
        f"Detected Python {sys.version_info.major}.{sys.version_info.minor}. "
        "Update GOG Galaxy from https://www.gog.com/galaxy, then reinstall the plugin."
    )

from typing import Any, List

from galaxy.api.consts import LicenseType, Platform
from galaxy.api.plugin import Plugin, create_and_run_plugin
from galaxy.api.types import (
    Achievement,
    Game,
    GameTime,
    LicenseInfo,
    Subscription,
    SubscriptionGame,
    UserInfo,
)

from http_client import HttpClient
from psn.auth import PSNAuthenticator
from psn.client import PSNClient
from version import __version__

logger = logging.getLogger(__name__)


class PSNPlugin(Plugin):
    def __init__(self, reader, writer, token):
        super().__init__(Platform.Psn, __version__, reader, writer, token)
        self._http_client = HttpClient()
        self._psn_client = PSNClient(self._http_client)
        self._authenticator = PSNAuthenticator(
            self._http_client,
            self._psn_client,
            self.store_credentials,
        )
        logging.getLogger("urllib3").setLevel(logging.FATAL)

    async def authenticate(self, stored_credentials=None):
        return await self._authenticator.authenticate(stored_credentials)

    async def pass_login_credentials(self, step, credentials, cookies):
        return await self._authenticator.complete_browser_login(
            step, credentials, cookies
        )

    async def get_subscriptions(self) -> List[Subscription]:
        is_plus_active = await self._psn_client.get_psplus_status()
        return [
            Subscription(
                subscription_name="PlayStation PLUS",
                end_time=None,
                owned=is_plus_active,
            )
        ]

    async def get_subscription_games(
        self, subscription_name: str, context: Any
    ):
        yield await self._psn_client.get_subscription_games()

    async def _ensure_authenticated(self):
        if self._http_client._access_token:
            return
        payload = self._authenticator._stored_payload
        npsso = (payload or {}).get("npsso")
        if npsso:
            await self._authenticator._authenticate_with_npsso(npsso)

    async def get_owned_games(self):
        await self._ensure_authenticated()
        titles = await self._psn_client.get_all_library_titles()
        return [
            Game(
                game_id=title["titleId"],
                game_title=title["name"],
                dlcs=[],
                license_info=LicenseInfo(LicenseType.SinglePurchase, None),
            )
            for title in titles
        ]

    async def prepare_game_times_context(self, game_ids: List[str]) -> Any:
        await self._ensure_authenticated()
        return await self._psn_client.build_game_times_context(game_ids)

    async def get_game_time(self, game_id: str, context: Any) -> GameTime:
        if context and game_id in context:
            return context[game_id]
        return GameTime(game_id=game_id, time_played=None, last_played_time=None)

    async def prepare_achievements_context(self, game_ids: List[str]) -> Any:
        await self._ensure_authenticated()
        context = await self._psn_client.prepare_achievements_context(game_ids)
        self._last_achievements_context = context
        return context

    async def get_unlocked_achievements(
        self, game_id: str, context: Any
    ) -> List[Achievement]:
        if not context:
            return []
        return await self._psn_client.fetch_unlocked_achievements(game_id, context)

    def achievements_import_complete(self):
        context = getattr(self, "_last_achievements_context", None)
        if context is None:
            return
        logger.info(
            "Trophy import finished: %d games with unlocks (%d total trophies), "
            "%d games empty",
            context.games_with_trophies,
            context.total_unlocked,
            context.games_empty,
        )

    async def get_friends(self) -> List[UserInfo]:
        await self._ensure_authenticated()
        try:
            return await self._psn_client.get_friends()
        except Exception:
            logger.warning("Could not fetch friends list", exc_info=True)
            return []

    async def shutdown(self):
        await self._authenticator.stop()
        await self._http_client.close()


def main():
    create_and_run_plugin(PSNPlugin, sys.argv)


if __name__ == "__main__":
    main()
