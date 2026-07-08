import asyncio
import re

from psn.auth import npsso_from_end_uri, npsso_token_file_path
from psn.local_server import DONE_PATH, LocalAuthServer


def test_npsso_from_end_uri_extracts_query_param():
    end_uri = "http://127.0.0.1:54321/done?npsso=abc123XYZ"
    assert npsso_from_end_uri(end_uri) == "abc123XYZ"


def test_npsso_from_end_uri_url_decodes_token():
    end_uri = "http://127.0.0.1:54321/done?npsso=token%2Bvalue"
    assert npsso_from_end_uri(end_uri) == "token+value"


def test_npsso_from_end_uri_handles_fragment():
    end_uri = "http://127.0.0.1:54321/done#npsso=fragToken"
    assert npsso_from_end_uri(end_uri) == "fragToken"


def test_npsso_from_end_uri_ignores_url_without_token():
    assert npsso_from_end_uri("http://127.0.0.1:54321/done") is None
    assert npsso_from_end_uri("") is None


def test_npsso_token_file_path_is_plugin_directory():
    assert npsso_token_file_path().name == "npsso.token"


def test_local_server_serves_form_and_captures_token():
    import aiohttp

    async def run():
        server = LocalAuthServer()
        try:
            await server.start()
            async with aiohttp.ClientSession() as session:
                async with session.get(server.base_url) as resp:
                    assert resp.status == 200
                    body = await resp.text()
                    assert 'name="npsso"' in body
                    assert 'id="open-store"' in body
                    assert 'id="open-npsso"' in body
                    assert f'action="{DONE_PATH}"' in body
                async with session.get(f"{server.base_url.rstrip('/')}/open?target=store") as resp:
                    assert resp.status == 204
                async with session.get(f"{server.base_url.rstrip('/')}/open?target=invalid") as resp:
                    assert resp.status == 400
                done_url = f"{server.base_url.rstrip('/')}{DONE_PATH}?npsso=mytoken"
                async with session.get(done_url, allow_redirects=False) as resp:
                    assert resp.status == 302
                    assert "playstation.com" in resp.headers["Location"]
            assert server.captured_npsso == "mytoken"
        finally:
            await server.stop()

    asyncio.run(run())


def test_local_server_end_uri_regex_matches_playstation():
    server = LocalAuthServer()
    regex = server.end_uri_regex
    assert re.match(regex, "https://www.playstation.com/")
    assert re.match(regex, "https://www.playstation.com/en-us/")
    assert not re.match(regex, "http://127.0.0.1:54321/")
