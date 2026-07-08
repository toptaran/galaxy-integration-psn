import json
import logging
from typing import Dict, List

from bs4 import BeautifulSoup
from galaxy.api.errors import UnknownBackendResponse
from galaxy.api.types import SubscriptionGame

logger = logging.getLogger(__name__)


class NotFoundSubscriptionPaginator(Exception):
    pass


class PSNGamesParser:
    _SUBSCRIBED_GAMES_PAGINATOR_CSS_CLASS = "psw-strand-scroller"
    _SUBSCRIBED_GAMES_CSS_CLASS = "ems-sdk-product-tile-link"
    _GAME_DATA_TAG = "data-telemetry-meta"

    def parse(self, response: str) -> List[SubscriptionGame]:
        try:
            games = self._subscription_games(response)
        except NotFoundSubscriptionPaginator as exc:
            raise UnknownBackendResponse(
                f"HTML tag {self._SUBSCRIBED_GAMES_PAGINATOR_CSS_CLASS} was not found in response."
            ) from exc

        return [
            SubscriptionGame(game_id=game["titleId"], game_title=game["name"])
            for game in games
            if game.get("name")
            and game.get("titleId")
            and not game["name"].startswith("PlayStation")
        ]

    def _subscription_games(self, response: str) -> List[Dict]:
        parsed_html = BeautifulSoup(response, "html.parser")
        paginator = parsed_html.find("ul", class_=self._SUBSCRIBED_GAMES_PAGINATOR_CSS_CLASS)
        if not paginator:
            raise NotFoundSubscriptionPaginator

        logger.debug(
            "HTML response slice of %s tag:\n%s",
            self._SUBSCRIBED_GAMES_PAGINATOR_CSS_CLASS,
            paginator.decode_contents(),
        )
        games = paginator.find_all("a", class_=self._SUBSCRIBED_GAMES_CSS_CLASS)
        result = []
        for game in games:
            try:
                game_data = getattr(game, "attrs", {}).get(self._GAME_DATA_TAG)
                result.append(json.loads(game_data))
            except (json.JSONDecodeError, TypeError) as exc:
                logger.error(exc)
        return result
