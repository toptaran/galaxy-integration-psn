import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from galaxy.api.errors import UnknownBackendResponse
from galaxy.api.types import Achievement, GameTime, SubscriptionGame, UserInfo

from psn.constants import (
    DEFAULT_PAGE_SIZE,
    FRIENDS_PAGE_SIZE,
    PLAYED_GAMES_PAGE_SIZE,
    PSN_PLUS_SUBSCRIPTIONS_URL,
    TROPHY_TITLES_PAGE_SIZE,
)
from psn.duration import parse_play_duration
from psn.graphql import played_games_url, profile_url, purchased_games_url
from psn.library_utils import (
    alias_context_by_siblings,
    build_concept_siblings,
    dedupe_library_by_concept,
    enrich_purchased_concept_ids,
    expand_concept_sibling_skus,
    merge_library_entries,
    parse_iso_datetime,
    pick_display_name,
)
from psn.parsers import PSNGamesParser
from psn.trophies import extract_store_title_mappings, merge_earned_with_definitions
from psn.rest_urls import (
    friends_url,
    played_games_url as rest_played_games_url,
    profile_url as rest_profile_url,
    title_trophies_url,
    trophy_titles_url,
    user_trophies_earned_url,
    user_trophies_for_titles_url,
)

logger = logging.getLogger(__name__)

STORE_TITLE_PREFIXES = ("CUSA", "PPSA", "PCSE", "PCSA")


FRIENDS_PROFILE_BATCH = 8


@dataclass
class AchievementsContext:
    """Shared indexes for per-game trophy import (fetch happens in get_unlocked_achievements)."""

    concept_siblings: Dict[str, List[str]] = field(default_factory=dict)
    trophy_title_index: Dict[str, Dict[str, str]] = field(default_factory=dict)
    cache: Dict[str, List[Achievement]] = field(default_factory=dict)
    games_with_trophies: int = 0
    games_empty: int = 0
    total_unlocked: int = 0


class PSNClient:
    def __init__(self, http_client):
        self._http_client = http_client
        self._played_games_cache: Optional[List[Dict[str, Any]]] = None
        self._trophy_title_index: Dict[str, Dict[str, str]] = {}
        self._concept_siblings: Dict[str, List[str]] = {}

    async def get_own_user_info(self) -> Tuple[str, str]:
        response = await self._http_client.graphql_get(profile_url())
        logger.debug("user profile data: %s", response)
        try:
            profile = response["data"]["oracleUserProfileRetrieve"]
            return profile["accountId"], profile["onlineId"]
        except (KeyError, TypeError) as exc:
            raise UnknownBackendResponse(str(exc)) from exc

    async def get_psplus_status(self) -> bool:
        try:
            response = await self._http_client.graphql_get(profile_url())
            status = response["data"]["oracleUserProfileRetrieve"]["isPsPlusMember"]
            return bool(status)
        except Exception:
            logger.warning(
                "Could not determine PS Plus status (profile API unavailable)",
                exc_info=True,
            )
            return False

    async def get_subscription_games(self) -> List[SubscriptionGame]:
        response = await self._http_client.get(
            PSN_PLUS_SUBSCRIPTIONS_URL,
            get_json=False,
            silent=True,
        )
        try:
            return PSNGamesParser().parse(response)
        except Exception as exc:
            logger.exception("Cannot parse subscription games")
            raise UnknownBackendResponse(str(exc)) from exc

    @staticmethod
    def _parse_purchased(response) -> List[Dict[str, str]]:
        try:
            data = (response or {}).get("data") or {}
            container = data.get("purchasedTitlesRetrieve") or {}
            games = container.get("games") or []
            return [
                {"titleId": title["titleId"], "name": title["name"], "source": "purchased"}
                for title in games
                if title.get("titleId") and title.get("name")
            ]
        except (KeyError, TypeError, AttributeError) as exc:
            raise UnknownBackendResponse(str(exc)) from exc

    async def get_purchased_games(self) -> List[Dict[str, str]]:
        all_games: List[Dict[str, str]] = []
        start = 0
        page = DEFAULT_PAGE_SIZE
        while True:
            response = await self._http_client.graphql_get(
                purchased_games_url(start=start, size=page)
            )
            batch = self._parse_purchased(response)
            all_games.extend(batch)
            logger.info("Fetched %d purchased games (start=%d)", len(batch), start)
            if len(batch) < page:
                break
            start += page
        return all_games

    async def get_played_games_graphql(self) -> List[Dict[str, str]]:
        response = await self._http_client.graphql_get(
            played_games_url(limit=DEFAULT_PAGE_SIZE)
        )
        try:
            data = (response or {}).get("data") or {}
            container = data.get("gameLibraryTitlesRetrieve") or {}
            games = container.get("games") or []
            return [
                {"titleId": title["titleId"], "name": title["name"], "source": "played"}
                for title in games
                if title.get("titleId") and title.get("name")
            ]
        except (KeyError, TypeError, AttributeError) as exc:
            raise UnknownBackendResponse(str(exc)) from exc

    async def get_played_games(self) -> List[Dict[str, Any]]:
        if self._played_games_cache is not None:
            return self._played_games_cache

        all_titles: List[Dict[str, Any]] = []
        offset = 0
        page = PLAYED_GAMES_PAGE_SIZE
        skipped_unknown = 0
        while True:
            response = await self._http_client.api_get(
                rest_played_games_url(limit=page, offset=offset)
            )
            titles = response.get("titles") or []
            for title in titles:
                if title.get("category") == "unknown":
                    if not pick_display_name(
                        title.get("name"),
                        title.get("localizedName"),
                        (title.get("concept") or {}).get("name"),
                    ):
                        skipped_unknown += 1
                        continue
                all_titles.append(title)
            logger.info(
                "Fetched %d played games (offset=%d, skipped_unknown=%d)",
                len(titles),
                offset,
                skipped_unknown,
            )
            if len(titles) < page:
                break
            offset += page

        self._played_games_cache = all_titles
        return all_titles

    async def get_trophy_library_games(self) -> List[Dict[str, str]]:
        all_titles: List[Dict[str, str]] = []
        offset = 0
        page = TROPHY_TITLES_PAGE_SIZE
        index: Dict[str, Dict[str, str]] = {}
        while True:
            response = await self._http_client.api_get(
                trophy_titles_url(limit=page, offset=offset)
            )
            batch = response.get("trophyTitles") or []
            for title in batch:
                np_id = title.get("npCommunicationId")
                if not np_id:
                    continue
                platform = title.get("trophyTitlePlatform") or ""
                np_service = title.get("npServiceName") or (
                    "trophy2" if "PS5" in platform else "trophy"
                )
                index[np_id] = {
                    "npCommunicationId": np_id,
                    "npServiceName": np_service,
                    "name": title.get("trophyTitleName") or "",
                    "platform": platform,
                }
                if title.get("hiddenFlag"):
                    continue
                name = title.get("trophyTitleName")
                if not name:
                    continue
                all_titles.append(
                    {
                        "titleId": np_id,
                        "name": name,
                        "source": "trophy",
                    }
                )
            logger.info("Fetched %d trophy titles (offset=%d)", len(batch), offset)
            if len(batch) < page:
                break
            offset += page

        self._trophy_title_index = index
        return all_titles

    async def get_all_library_titles(self) -> List[Dict[str, str]]:
        purchased_games = await self.get_purchased_games()
        try:
            played_games = await self.get_played_games()
        except Exception:
            logger.warning("REST played games unavailable, trying GraphQL fallback", exc_info=True)
            try:
                played_games = await self.get_played_games_graphql()
            except Exception:
                logger.warning("Could not fetch played games", exc_info=True)
                played_games = []

        try:
            trophy_games = await self.get_trophy_library_games()
        except Exception:
            logger.warning("Could not fetch trophy titles for library expansion", exc_info=True)
            trophy_games = []

        purchased_ids = {game["titleId"] for game in purchased_games}
        played_entries = [
            {
                **title,
                "source": "played",
                "conceptId": (title.get("concept") or {}).get("id"),
                "name": pick_display_name(
                    title.get("localizedName"),
                    title.get("name"),
                    (title.get("concept") or {}).get("name"),
                ),
            }
            for title in played_games
            if isinstance(title, dict)
        ]
        self._concept_siblings = build_concept_siblings(played_games)
        enrich_purchased_concept_ids(purchased_games, played_games)

        trophy_only = []
        for game in trophy_games:
            if game["titleId"] in purchased_ids:
                continue
            if game["titleId"].startswith(STORE_TITLE_PREFIXES):
                continue
            meta = self._trophy_title_index.get(game["titleId"], {})
            platform = meta.get("platform") or ""
            if any(tag in platform for tag in ("PS4", "PS5", "PSPC")):
                continue
            trophy_only.append(game)

        merged = merge_library_entries(purchased_games + played_entries + trophy_only)
        deduped = dedupe_library_by_concept(merged)
        library = expand_concept_sibling_skus(deduped, self._concept_siblings)
        logger.info(
            "Total library titles: %d (merged=%d, deduped=%d, with sibling SKUs=%d, "
            "purchased=%d, played=%d, trophy-only=%d)",
            len(library),
            len(merged),
            len(deduped),
            len(library),
            len(purchased_games),
            len(played_entries),
            len(trophy_only),
        )
        return library

    async def build_game_times_context(self, game_ids: List[str]) -> Dict[str, GameTime]:
        try:
            played_games = await self.get_played_games()
        except Exception:
            logger.warning("Could not fetch played games for game time import", exc_info=True)
            return {}

        wanted = set(game_ids)
        context: Dict[str, GameTime] = {}
        for title in played_games:
            title_id = title.get("titleId")
            if title_id not in wanted:
                continue
            context[title_id] = GameTime(
                game_id=title_id,
                time_played=parse_play_duration(title.get("playDuration")),
                last_played_time=parse_iso_datetime(title.get("lastPlayedDateTime")),
            )
        if not self._concept_siblings:
            self._concept_siblings = build_concept_siblings(played_games)
        alias_context_by_siblings(
            context,
            game_ids,
            self._concept_siblings,
            has_data=lambda item: item.time_played is not None
            or item.last_played_time is not None,
        )
        with_time = sum(
            1 for item in context.values() if item.time_played is not None
        )
        logger.info(
            "Prepared game time data for %d/%d games (%d with play time)",
            len(context),
            len(game_ids),
            with_time,
        )
        return context

    @staticmethod
    def _is_store_title_id(game_id: str) -> bool:
        return game_id.startswith(STORE_TITLE_PREFIXES)

    async def _load_np_comm_achievements(
        self, np_comm_id: str, np_service_name: str
    ) -> List[Achievement]:
        earned_response = await self._http_client.api_get(
            user_trophies_earned_url(
                np_communication_id=np_comm_id,
                np_service_name=np_service_name,
            )
        )
        title_response = await self._http_client.api_get(
            title_trophies_url(
                np_communication_id=np_comm_id,
                np_service_name=np_service_name,
            )
        )
        return merge_earned_with_definitions(
            earned_response, title_response, np_comm_id
        )

    async def _resolve_store_trophy_sets(self, store_id: str) -> List[dict]:
        response = await self._http_client.api_get(
            user_trophies_for_titles_url(np_title_ids=store_id),
            not_found_ok=True,
        )
        if not response:
            return []
        return extract_store_title_mappings(response).get(store_id, [])

    async def _fetch_achievements_for_title(self, game_id: str) -> List[Achievement]:
        if self._is_store_title_id(game_id):
            trophy_sets = await self._resolve_store_trophy_sets(game_id)
            if not trophy_sets:
                return []
            earned: List[Achievement] = []
            for trophy_set in trophy_sets:
                np_comm_id = trophy_set.get("npCommunicationId")
                if not np_comm_id:
                    continue
                try:
                    earned.extend(
                        await self._load_np_comm_achievements(
                            np_comm_id,
                            trophy_set.get("npServiceName") or "trophy",
                        )
                    )
                except Exception:
                    logger.debug(
                        "Could not fetch trophies for %s (%s)",
                        game_id,
                        np_comm_id,
                        exc_info=True,
                    )
            return earned

        meta = self._trophy_title_index.get(game_id)
        if not meta:
            return []
        np_service = meta.get("npServiceName") or "trophy"
        try:
            return await self._load_np_comm_achievements(game_id, np_service)
        except Exception:
            logger.debug("Could not fetch trophies for %s", game_id, exc_info=True)
            return []

    async def prepare_achievements_context(
        self, game_ids: List[str]
    ) -> AchievementsContext:
        if not self._trophy_title_index:
            try:
                await self.get_trophy_library_games()
            except Exception:
                logger.warning("Could not load trophy title index", exc_info=True)

        if not self._concept_siblings:
            try:
                played_games = await self.get_played_games()
                self._concept_siblings = build_concept_siblings(played_games)
            except Exception:
                logger.debug("Could not build concept sibling map", exc_info=True)

        logger.info(
            "Prepared achievements context for %d games (index=%d titles, siblings=%d)",
            len(game_ids),
            len(self._trophy_title_index),
            len(self._concept_siblings),
        )
        return AchievementsContext(
            concept_siblings=dict(self._concept_siblings),
            trophy_title_index=dict(self._trophy_title_index),
        )

    def _cache_achievements_for_siblings(
        self,
        context: AchievementsContext,
        game_id: str,
        achievements: List[Achievement],
    ) -> None:
        context.cache[game_id] = achievements
        if not achievements:
            return
        for sibling_id in context.concept_siblings.get(game_id, []):
            context.cache[sibling_id] = achievements

    async def fetch_unlocked_achievements(
        self, game_id: str, context: AchievementsContext
    ) -> List[Achievement]:
        if game_id in context.cache:
            return context.cache[game_id]

        if not context.trophy_title_index and self._trophy_title_index:
            context.trophy_title_index = dict(self._trophy_title_index)

        achievements = await self._fetch_achievements_for_title(game_id)
        aliased_from = None
        self._cache_achievements_for_siblings(context, game_id, achievements)

        if not achievements:
            for sibling_id in context.concept_siblings.get(game_id, []):
                if sibling_id not in context.cache:
                    sibling_achievements = await self._fetch_achievements_for_title(
                        sibling_id
                    )
                    self._cache_achievements_for_siblings(
                        context, sibling_id, sibling_achievements
                    )
                sibling_achievements = context.cache.get(sibling_id) or []
                if sibling_achievements:
                    aliased_from = sibling_id
                    self._cache_achievements_for_siblings(
                        context, game_id, sibling_achievements
                    )
                    break

        result = context.cache.get(game_id, [])
        if result:
            context.games_with_trophies += 1
            context.total_unlocked += len(result)
            if aliased_from:
                logger.info(
                    "Trophies for %s: %d unlocked (from sibling %s)",
                    game_id,
                    len(result),
                    aliased_from,
                )
            else:
                logger.info(
                    "Trophies for %s: %d unlocked", game_id, len(result)
                )
        else:
            context.games_empty += 1
            reason = "no PSN trophy set"
            if self._is_store_title_id(game_id):
                reason = "no store→trophy mapping"
            elif game_id not in self._trophy_title_index:
                reason = "not in trophy index"
            logger.info(
                "Trophies for %s: none (%s, siblings=%s)",
                game_id,
                reason,
                context.concept_siblings.get(game_id, []),
            )
        return result

    async def _load_friend_profile(self, account_id: str) -> Optional[UserInfo]:
        try:
            profile = await self._http_client.api_get(rest_profile_url(account_id))
        except Exception:
            logger.debug("Could not load profile for friend %s", account_id, exc_info=True)
            return None

        avatar_url = None
        for avatar in profile.get("avatars") or []:
            if avatar.get("size") == "l":
                avatar_url = avatar.get("url")
                break
        if avatar_url is None and profile.get("avatars"):
            avatar_url = profile["avatars"][0].get("url")

        online_id = profile.get("onlineId") or str(account_id)
        return UserInfo(
            user_id=str(account_id),
            user_name=online_id,
            avatar_url=avatar_url,
            profile_url=f"https://profile.playstation.com/{online_id}",
        )

    async def get_friends(self) -> List[UserInfo]:
        response = await self._http_client.api_get(
            friends_url(limit=FRIENDS_PAGE_SIZE, offset=0)
        )
        account_ids = response.get("friends") or []
        friends: List[UserInfo] = []
        for index in range(0, len(account_ids), FRIENDS_PROFILE_BATCH):
            batch = account_ids[index : index + FRIENDS_PROFILE_BATCH]
            results = await asyncio.gather(
                *(self._load_friend_profile(account_id) for account_id in batch)
            )
            friends.extend(friend for friend in results if friend is not None)
        logger.info("Fetched %d friends", len(friends))
        return friends
