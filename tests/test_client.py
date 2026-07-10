import asyncio

import pytest
from galaxy.api.errors import BackendTimeout, UnknownBackendResponse, UnknownError

from psn.client import AchievementsContext, PSNClient
from psn.constants import ACCOUNT_ME_URL, TROPHY_FETCH_CONCURRENCY
from psn.rest_urls import profile_url as rest_profile_url

ACCOUNT_ID = "5210829823825494249"
OWN_PROFILE_URL = rest_profile_url(ACCOUNT_ID)


class FakeHttpClient:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    async def api_get(self, url, **kwargs):
        self.calls.append(url)
        result = self._responses[url]
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.asyncio
async def test_get_own_user_info_uses_seeded_account_id():
    http_client = FakeHttpClient(
        {OWN_PROFILE_URL: {"onlineId": "gamer123", "isPlus": True}}
    )
    client = PSNClient(http_client)
    client.set_account_id(ACCOUNT_ID)

    user_id, user_name = await client.get_own_user_info()

    assert user_id == ACCOUNT_ID
    assert user_name == "gamer123"
    assert ACCOUNT_ME_URL not in http_client.calls


@pytest.mark.asyncio
async def test_get_own_user_info_resolves_account_id_when_not_seeded():
    http_client = FakeHttpClient(
        {
            ACCOUNT_ME_URL: {"accountId": int(ACCOUNT_ID)},
            OWN_PROFILE_URL: {"onlineId": "gamer123", "isPlus": False},
        }
    )
    client = PSNClient(http_client)

    user_id, user_name = await client.get_own_user_info()

    assert user_id == ACCOUNT_ID
    assert user_name == "gamer123"


@pytest.mark.asyncio
async def test_get_own_user_info_raises_on_malformed_response():
    http_client = FakeHttpClient({OWN_PROFILE_URL: {"isPlus": False}})
    client = PSNClient(http_client)
    client.set_account_id(ACCOUNT_ID)

    with pytest.raises(UnknownBackendResponse):
        await client.get_own_user_info()


@pytest.mark.asyncio
async def test_get_psplus_status_reads_is_plus():
    http_client = FakeHttpClient(
        {OWN_PROFILE_URL: {"onlineId": "gamer123", "isPlus": True}}
    )
    client = PSNClient(http_client)
    client.set_account_id(ACCOUNT_ID)

    assert await client.get_psplus_status() is True


@pytest.mark.asyncio
async def test_get_psplus_status_false_when_profile_unavailable():
    http_client = FakeHttpClient({OWN_PROFILE_URL: RuntimeError("backend down")})
    client = PSNClient(http_client)
    client.set_account_id(ACCOUNT_ID)

    assert await client.get_psplus_status() is False


@pytest.mark.asyncio
async def test_own_profile_is_cached_between_calls():
    http_client = FakeHttpClient(
        {OWN_PROFILE_URL: {"onlineId": "gamer123", "isPlus": False}}
    )
    client = PSNClient(http_client)
    client.set_account_id(ACCOUNT_ID)

    await client.get_own_user_info()
    await client.get_psplus_status()

    assert http_client.calls.count(OWN_PROFILE_URL) == 1


class RaisingHttpClient:
    def __init__(self, error):
        self._error = error

    async def api_get(self, url, **kwargs):
        raise self._error


def make_trophy_client(http_client) -> PSNClient:
    client = PSNClient(http_client)
    client._trophy_title_index = {
        "NPWR00001_00": {
            "npCommunicationId": "NPWR00001_00",
            "npServiceName": "trophy",
            "name": "Some Game",
            "platform": "PS4",
        }
    }
    return client


@pytest.mark.asyncio
async def test_transient_trophy_error_propagates_instead_of_caching_empty():
    client = make_trophy_client(RaisingHttpClient(BackendTimeout()))
    context = AchievementsContext()

    with pytest.raises(BackendTimeout):
        await client.fetch_unlocked_achievements("NPWR00001_00", context)

    assert "NPWR00001_00" not in context.cache


@pytest.mark.asyncio
async def test_definitive_trophy_miss_is_recorded_as_empty():
    client = make_trophy_client(RaisingHttpClient(UnknownError("404")))
    context = AchievementsContext()

    result = await client.fetch_unlocked_achievements("NPWR00001_00", context)

    assert result == []
    assert context.cache["NPWR00001_00"] == []


class ConcurrencyTrackingHttpClient:
    def __init__(self):
        self.active = 0
        self.max_active = 0

    async def api_get(self, url, **kwargs):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.001)
        self.active -= 1
        return {"titles": []}


@pytest.mark.asyncio
async def test_trophy_fetch_concurrency_is_bounded():
    http_client = ConcurrencyTrackingHttpClient()
    client = PSNClient(http_client)
    context = AchievementsContext()
    game_ids = [f"CUSA{index:05d}_00" for index in range(30)]

    await asyncio.gather(
        *(client.fetch_unlocked_achievements(game_id, context) for game_id in game_ids)
    )

    assert 0 < http_client.max_active <= TROPHY_FETCH_CONCURRENCY
