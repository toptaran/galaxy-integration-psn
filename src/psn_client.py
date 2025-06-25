import asyncio
import logging
from datetime import datetime, timezone
from functools import partial
from typing import List, NewType

from galaxy.api.errors import UnknownBackendResponse
from galaxy.api.types import SubscriptionGame

from parsers import PSNGamesParser


GAME_LIST_URL = "https://web.np.playstation.com/api/graphql/v1/op" \
                "?operationName=getPurchasedGameList" \
                '&variables={{"isActive":true,"platform":["ps3","ps4","ps5"],"start":{start},"size":{size},"subscriptionService":"NONE"}}' \
                '&extensions={{"persistedQuery":{{"version":1,"sha256Hash":"827a423f6a8ddca4107ac01395af2ec0eafd8396fc7fa204aaf9b7ed2eefa168"}}}}'

PLAYED_GAME_LIST_URL = "https://web.np.playstation.com/api/graphql/v1/op" \
                       "?operationName=getUserGameList" \
                       '&variables={{"categories":"ps3_game,ps4_game,ps5_native_game","limit":{size}}}' \
                       '&extensions={{"persistedQuery":{{"version":1,"sha256Hash":"e0136f81d7d1fb6be58238c574e9a46e1c0cc2f7f6977a08a5a46f224523a004"}}}}'

USER_INFO_URL = "https://web.np.playstation.com/api/graphql/v1/op" \
                "?operationName=getProfileOracle" \
                "&variables={}" \
                '&extensions={"persistedQuery":{"version":1,"sha256Hash":"fc0d765f537f3dce3e0d91c71e85daa401042ba43066acde9f8f584faced10df"}}'

PSN_PLUS_SUBSCRIPTIONS_URL = 'https://store.playstation.com/subscriptions'

HEADERS = {"content-type": "application/json", "apollographql-client-name": "oracle-web-toolbar"}

DEFAULT_LIMIT = 100

# 100 is a maximum possible value to provide
PLAYED_GAME_LIST_URL = PLAYED_GAME_LIST_URL.format(size=DEFAULT_LIMIT)

UnixTimestamp = NewType("UnixTimestamp", int)

def parse_timestamp(earned_date) -> UnixTimestamp:
    date_format = "%Y-%m-%dT%H:%M:%S.%fZ" if '.' in earned_date else "%Y-%m-%dT%H:%M:%SZ"
    dt = datetime.strptime(earned_date, date_format)
    dt = datetime.combine(dt.date(), dt.time(), timezone.utc)
    return UnixTimestamp(int(dt.timestamp()))

class PSNClient:
    def __init__(self, http_client):
        self._http_client = http_client

    @staticmethod
    async def _async(method, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(method, *args, **kwargs))

    async def fetch_paginated_data(
        self,
        parser,
        url,
        operation_name,
        counter_name,
        limit=DEFAULT_LIMIT,
        *args,
        **kwargs
    ):
        response = await self._http_client.get(url.format(size=limit, start=0), *args, **kwargs)
        if not response:
            return []

        try:
            total = int(response["data"][operation_name]["pageInfo"].get(counter_name, 0))
        except (ValueError, KeyError, TypeError) as e:
            raise UnknownBackendResponse(e)

        responses = [response] + await asyncio.gather(*[
            self._http_client.get(url.format(size=limit, start=offset), *args, **kwargs)
            for offset in range(limit, total, limit)
        ])

        try:
            return [rec for res in responses for rec in parser(res)]
        except Exception:
            logging.exception("Cannot parse data")
            raise UnknownBackendResponse()

    async def fetch_data(self, parser, *args, **kwargs):
        response = await self._http_client.get(*args, **kwargs)

        try:
            return parser(response)
        except Exception:
            logging.exception("Cannot parse data")
            raise UnknownBackendResponse()

    async def async_get_own_user_info(self):
        def user_info_parser(response):
            logging.debug(f'user profile data: {response}')
            try:
                return response["data"]["oracleUserProfileRetrieve"]["accountId"], \
                       response["data"]["oracleUserProfileRetrieve"]["onlineId"]
            except (KeyError, TypeError) as e:
                raise UnknownBackendResponse(e)
        return await self.fetch_data(user_info_parser, USER_INFO_URL, headers=HEADERS)

    async def get_psplus_status(self) -> bool:

        def user_subscription_parser(response):
            try:
                status = response["data"]["oracleUserProfileRetrieve"]['isPsPlusMember']
                if status in [0, 1, True, False]:
                    return bool(status)
                raise TypeError
            except (KeyError, TypeError) as e:
                raise UnknownBackendResponse(e)

        return await self.fetch_data(user_subscription_parser, USER_INFO_URL, headers=HEADERS)

    async def get_subscription_games(self) -> List[SubscriptionGame]:
        return await self.fetch_data(PSNGamesParser().parse, PSN_PLUS_SUBSCRIPTIONS_URL, get_json=False, silent=True)

    async def async_get_purchased_games(self):
        def games_parser(response):
            try:
                games = response['data']['purchasedTitlesRetrieve']['games']
                return [
                    {"titleId": title["titleId"], "name": title["name"]} for title in games
                ] if games else []
            except (KeyError, TypeError) as e:
                raise UnknownBackendResponse(e)

        return await self.fetch_paginated_data(games_parser, GAME_LIST_URL, "purchasedTitlesRetrieve", "totalCount", DEFAULT_LIMIT, headers=HEADERS)

    async def async_get_played_games(self):
        def games_parser(response):
            try:
                games = response['data']['gameLibraryTitlesRetrieve']['games']
                return [
                    {"titleId": title["titleId"], "name": title["name"], "lastPlayedDateTime": title["lastPlayedDateTime"]} for title in games
                ] if games else []
            except (KeyError, TypeError) as e:
                raise UnknownBackendResponse(e)

        return await self.fetch_data(games_parser, PLAYED_GAME_LIST_URL, headers=HEADERS)
