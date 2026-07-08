from psn.parsers import PSNGamesParser


def test_subscription_parser_parses_games():
    html = """
    <ul class="psw-strand-scroller">
      <a class="ems-sdk-product-tile-link"
         data-telemetry-meta='{"titleId":"CUSA99999_00","name":"Free Game"}'>
      </a>
      <a class="ems-sdk-product-tile-link"
         data-telemetry-meta='{"titleId":"CUSA00000_00","name":"PlayStation Plus"}'>
      </a>
    </ul>
    """
    games = PSNGamesParser().parse(html)
    assert len(games) == 1
    assert games[0].game_id == "CUSA99999_00"
    assert games[0].game_title == "Free Game"
