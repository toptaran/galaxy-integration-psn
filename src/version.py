__version__ = "0.36"

__changelog__ = {
    "unreleased": """
    """,
    "0.36": """
        - Restore last played date (thx to flabbamann)
        - Fixed bad request error with new hashes and headers
        - Added custom cefpython3 with chromium 108 (thx to llcc01/cefpython)
        - Added user friendly auth process, does not need to get and insert npsso token manually
        - Temporary removed macos support(sry i do not have mac, can't support it)
    """,
    "0.35": """
        - Fix pagination of fetched purchased games
    """,
    "0.34": """
        - Add refreshing cookies by doing request to playstation login website
        - Fix logging by changing oauth which is the same as in web client for playstation.com
        - Add support for PS5 games
        - Remove no longer available features: achievements, friends, friends presence, game times  
    """,
    "0.33": """
        - Add game time feature 
    """,
    "0.32": """
        - Fix showing correct PS Plus monthly games in Galaxy Subscription tab
    """,
    "0.31": """
        - Fix losing authentication as side effect of shutdown while refreshing credentials
        - Add cache invalidation for title-communication_ids map every 7 days; fixes not showing updated games without reconnection
        - Provide fallback game name using trophy titles; fixes not showing some games (Cyberpunk 2077, Mafia: Definitive Edition, ...)
    """,
    "0.30": """
        - Only allow one token refresh at a time
    """,
    "0.29": """
        - Fix broken authentication due to change on psn side
    """,
    "0.28": """
        - Implements `get_subscription_games` to report current free games from PSPlus
    """
}
