from psn.graphql import purchased_games_url


def test_purchased_games_url_uses_current_hash_and_params():
    url = purchased_games_url(start=0, size=24)
    assert "operationName=getPurchasedGameList" in url
    assert "827a423f6a8ddca4107ac01395af2ec0eafd8396fc7fa204aaf9b7ed2eefa168" in url
    assert "sortBy" in url
    assert "ps4" in url
    assert "subscriptionService" not in url
