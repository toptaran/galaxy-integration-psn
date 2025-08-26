import json
import time
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Dict, List, Any
import threading

from psnawp_api import PSNAWP
from psnawp_api.models.title_stats import PlatformCategory
from psnawp_api.models.trophies import PlatformType

from galaxy.api.consts import LicenseType
from galaxy.api.types import Game, GameTime, LicenseInfo, Achievement


logger = logging.getLogger("psnawp_client")


@dataclass
class PsnTrophy:
    trophy_id: int
    name: str
    earned_timestamp: int

@dataclass
class PsnGame:
    title_id: str
    name: str
    platform: PlatformType
    np_communication_id: str
    last_played_timestamp: int
    play_duration: int
    trophies: Dict[int, PsnTrophy]

    def __init__(self, title_id: str, name: str, platform: PlatformType):
        self.title_id = title_id
        self.name = name
        self.platform = platform
        self.np_communication_id = ''
        self.last_played_timestamp = 0
        self.play_duration = 0
        self.trophies = {}

    def get_gog_game(self) -> Game:
        return Game(self.title_id, self.name, None, LicenseInfo(LicenseType.SinglePurchase))

    def get_gog_game_time(self) -> GameTime:
        return GameTime(self.title_id, self.play_duration, self.last_played_timestamp)

    def get_gog_achievement(self, trophy_id: int) -> Achievement:
        trophy = self.trophies[trophy_id]
        return Achievement(trophy.earned_timestamp, "{0}_{1}".format(self.np_communication_id, trophy_id), trophy.name)

    def get_gog_achievements(self) -> List[Achievement]:
        achievements: List[Achievement] = []
        for trophy_id, trophy in self.trophies.items():
            achievements.append(Achievement(trophy.earned_timestamp, "{0}_{1}".format(self.np_communication_id, trophy_id), trophy.name))
        return achievements

class PSNAWPClient:
    def __init__(self, npsso_token):
        self.npsso_token = npsso_token
        self.psnawp = PSNAWP(self.npsso_token)
        self.is_inited = False
        self.is_updating = False
        self.last_update_time = datetime.min
        self.work_thread = None

    def set_new_npsso_token(self, npsso_token):
        self.npsso_token = npsso_token
        self.psnawp.authenticator.npsso_cookie = self.npsso_token
        self.psnawp.authenticator.token_response = None

    async def get_own_user_info(self):
        client = self.psnawp.me()
        try:
            user_id = client.account_id
            user_name = client.online_id
        except:
            user_id = ""
            user_name = ""
        return user_id, user_name

    def init_cache(self, psnplugin):
        # serialize PsnGame objects from cache on init
        persistent_cache: Dict[str, Any] = psnplugin.persistent_cache
        if not self.is_inited:
            for title_id, value in persistent_cache.items():
                # Key must start from CUSA(PS4) or PPSA(PS5), exmaple: CUSA34390_00, PPSA08332_00
                # Value start { - it's Dict
                if (title_id.startswith("CUSA") or title_id.startswith("PPSA")) and value.startswith("{"):
                    persistent_cache[title_id] = self.load_psn_game_from_json(value)

    def get_owned_games(self, psnplugin) -> List[Game]:
        persistent_cache: Dict[str, Any] = psnplugin.persistent_cache
        games: List[Game] = []
        for title_id, value in persistent_cache.items():
            # Key must start from CUSA(PS4) or PPSA(PS5), exmaple: CUSA34390_00, PPSA08332_00
            if title_id.startswith("CUSA") or title_id.startswith("PPSA"):
                psn_game: PsnGame = value
                games.append(psn_game.get_gog_game())
        return games

    def get_unlocked_achievements(self, psnplugin, game_id: str) -> List[Achievement]:
        persistent_cache: Dict[str, Any] = psnplugin.persistent_cache
        if game_id in persistent_cache:
            psn_game: PsnGame = persistent_cache[game_id]
            return psn_game.get_gog_achievements()
        return []

    def get_game_time(self, psnplugin, game_id: str) -> GameTime:
        persistent_cache: Dict[str, Any] = psnplugin.persistent_cache
        if game_id in persistent_cache:
            psn_game: PsnGame = persistent_cache[game_id]
            return psn_game.get_gog_game_time()
        return GameTime(game_id, 0, 0)

    @staticmethod
    def get_platform_from_game_meta_type(ptype: str) -> PlatformType:
        if ptype == 'PS4GD':
            return PlatformType.PS4
        if ptype == 'PSGD':
            return PlatformType.PS5
        return PlatformType.UNKNOWN

    @staticmethod
    def get_platform_from_category(ptype: PlatformCategory) -> PlatformType:
        if ptype == PlatformCategory.PS4:
            return PlatformType.PS4
        if ptype == PlatformCategory.PS5:
            return PlatformType.PS5
        return PlatformType.UNKNOWN

    @staticmethod
    def load_psn_game_from_json(jsonstr: str) -> PsnGame:
        data: Dict[str, Any] = json.loads(jsonstr)
        psn_game: PsnGame = PsnGame(data["title_id"], data["name"], PlatformType(data["platform"]))
        psn_game.np_communication_id = data["np_communication_id"]
        psn_game.last_played_timestamp = int(data["last_played_timestamp"])
        psn_game.play_duration = int(data["play_duration"])
        for trophy_id, trophy_data in data["trophies"].items():
            trophy: PsnTrophy = PsnTrophy(int(trophy_id), trophy_data["name"], int(trophy_data["earned_timestamp"]))
            psn_game.trophies[trophy.trophy_id] = trophy
        return psn_game

    def update_task(self, psnplugin):
        try:
            # sleep a little before init, let client finish init
            if not self.is_inited:
                time.sleep(10)

            persistent_cache: Dict[str, Any] = psnplugin.persistent_cache

            game_entitlement_count: int = 0
            title_stats_last_updated: int = 0
            trophy_titles_last_updated: int = 0

            if "game_entitlement_count" in persistent_cache:
                game_entitlement_count: int = int(persistent_cache["game_entitlement_count"])
            if "title_stats_last_updated" in persistent_cache:
                title_stats_last_updated: int = int(persistent_cache["title_stats_last_updated"])
            if "trophy_titles_last_updated" in persistent_cache:
                trophy_titles_last_updated: int = int(persistent_cache["trophy_titles_last_updated"])

            logging.debug(f"update_task start {datetime.now()}")
            logging.debug(f"game_entitlement_count({game_entitlement_count}) title_stats_last_updated({title_stats_last_updated}) trophy_titles_last_updated({trophy_titles_last_updated})")

            client = self.psnawp.me()
            psntrophytitlelist: Dict[str, str] = {}
            have_changes = False
            psn_game: PsnGame = None

            # getting data of games owned by user from offset, do not need to read all list every time, it's quite long
            # 3 seconds for every 20 games
            logging.debug(f"get game_entitlements {datetime.now()}")
            game_entitlements = client.game_entitlements(offset=game_entitlement_count)
            for gameEntitlement in game_entitlements:
                game_entitlement_count = game_entitlement_count + 1
                have_changes = True
                if gameEntitlement["titleMeta"]["titleId"] not in persistent_cache:
                    psn_game = PsnGame(gameEntitlement["titleMeta"]["titleId"], gameEntitlement["titleMeta"]["name"], self.get_platform_from_game_meta_type(gameEntitlement["gameMeta"]["type"]))
                    persistent_cache[psn_game.title_id] = psn_game
                    # better to add/update games in batch with delay
                    #psnplugin.add_game(persistent_cache[gameEntitlement["titleMeta"]["titleId"]].get_gog_game())
                else:
                    psn_game = persistent_cache[gameEntitlement["titleMeta"]["titleId"]]
                    if len(psn_game.np_communication_id) > 0:
                        psntrophytitlelist[psn_game.np_communication_id] = psn_game.title_id

                # propagate data as it received with delay, to make it easier for gog and user see smth doing
                psnplugin.add_game(psn_game.get_gog_game())
                time.sleep(0.2)

            # getting data of played games limited by last timestamp, do not need to read all list every time, it can be long
            # 3 seconds for every 200 played games
            titleids: List[str] = []
            new_title_stats_last_updated: int = title_stats_last_updated
            logging.debug(f"get title_stats {datetime.now()}")
            title_stats = client.title_stats()
            for title_stat in title_stats:
                last_played_timestamp = int(title_stat.last_played_date_time.timestamp())
                if title_stats_last_updated >= last_played_timestamp:
                    break

                have_changes = True
                if new_title_stats_last_updated < last_played_timestamp:
                    new_title_stats_last_updated = last_played_timestamp

                if title_stat.category == PlatformCategory.UNKNOWN:
                    continue

                if title_stat.title_id not in persistent_cache:
                    persistent_cache[title_stat.title_id] = PsnGame(title_stat.title_id, title_stat.name, self.get_platform_from_category(title_stat.category))
                    # better to add/update games in batch with delay
                    #psnplugin.add_game(persistent_cache[title_stat.title_id])

                psn_game = persistent_cache[title_stat.title_id]
                psn_game.last_played_timestamp = last_played_timestamp
                psn_game.play_duration = int(title_stat.play_duration.total_seconds() / 60)

                # gog client will auto request this data on game add, id do your self can get request processing error because of limits
                #psnplugin.update_game_time(psn_game.get_gog_game_time())
                if len(psn_game.np_communication_id) == 0:
                    titleids.append(title_stat.title_id)

                # propagate data as it received with delay, to make it easier for gog and user see smth doing
                psnplugin.add_game(psn_game.get_gog_game())
                time.sleep(0.2)
            title_stats_last_updated = new_title_stats_last_updated

            # getting np_communication_id of played games if not have it, it can be quite long
            # 3 seconds for every 5 games
            logging.debug(f"get trophy_titles_for_title {datetime.now()}")
            i = 0
            while i < len(titleids):
                trophy_titles_for_title = client.trophy_titles_for_title(titleids[i:i + 5])
                for trophy_title in trophy_titles_for_title:
                    psn_game = persistent_cache[trophy_title.np_title_id]
                    psn_game.np_communication_id = trophy_title.np_communication_id
                    psntrophytitlelist[trophy_title.np_communication_id] = trophy_title.np_title_id
                i = i + 5

            # getting trophy(achievement) data of played games limited by last update timestamp, do not need to read all list every time,
            # it can be rally long, 3 seconds for every game
            new_trophy_titles_last_updated: int = trophy_titles_last_updated
            logging.debug(f"get trophy_titles {datetime.now()}")
            trophy_titles = client.trophy_titles()
            for trophy_title in trophy_titles:
                if trophy_title.np_communication_id in psntrophytitlelist:
                    last_updated_timestamp = int(trophy_title.last_updated_datetime.timestamp())
                    if trophy_titles_last_updated >= last_updated_timestamp:
                        break

                    have_changes = True
                    if new_trophy_titles_last_updated < last_updated_timestamp:
                        new_trophy_titles_last_updated = last_updated_timestamp

                    psn_game = persistent_cache[psntrophytitlelist[trophy_title.np_communication_id]]

                    trophies = client.trophies(psn_game.np_communication_id, psn_game.platform, True, "all")
                    for trophy in trophies:
                        if trophy.earned and trophy.trophy_id not in psn_game.trophies:
                            psn_game.trophies[trophy.trophy_id] = PsnTrophy(trophy.trophy_id, trophy.trophy_name, int(trophy.earned_date_time.timestamp()))
                            # gog client will auto request this data on game add, id do your self can get request processing error because of limits
                            #psnplugin.unlock_achievement(psn_game.title_id, psn_game.get_gog_achievement(trophy.trophy_id))

                    #update only if there are any trophies
                    if len(psn_game.trophies) > 0:
                        # propagate data as it received with delay, to make it easier for gog and user see smth doing
                        psnplugin.add_game(psn_game.get_gog_game())
                        time.sleep(0.2)
            trophy_titles_last_updated = new_trophy_titles_last_updated

            persistent_cache["game_entitlement_count"] = game_entitlement_count
            persistent_cache["title_stats_last_updated"] = title_stats_last_updated
            persistent_cache["trophy_titles_last_updated"] = trophy_titles_last_updated

            if have_changes:
                psnplugin.push_cache()

            logging.debug(f"update_task finish {datetime.now()}")
            logging.debug(f"game_entitlement_count({game_entitlement_count}) title_stats_last_updated({title_stats_last_updated}) trophy_titles_last_updated({trophy_titles_last_updated})")

        except Exception as e:
            logging.critical(e, exc_info=True)

        self.last_update_time = datetime.now()
        self.is_inited = True
        self.is_updating = False

    def start_init(self, psnplugin):
        self.init_cache(psnplugin)
        self.work_thread = threading.Thread(target=self.update_task, args=(psnplugin,))
        self.work_thread.start()

    def tick(self, psnplugin) -> None:
        if not self.is_inited:
            return
        if self.is_updating:
            return
        if (datetime.now() - self.last_update_time).total_seconds() > 5 * 60:
            self.is_updating = True
            self.work_thread = threading.Thread(target=self.update_task, args=(psnplugin,))
            self.work_thread.start()