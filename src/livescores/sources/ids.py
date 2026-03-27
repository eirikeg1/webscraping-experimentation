"""League and competition ID mappings per source."""

# Internal league keys -> ESPN league codes
ESPN_LEAGUES: dict[str, str] = {
    "premier_league": "eng.1",
    "laliga": "esp.1",
    "champions_league": "uefa.champions",
    "europa_league": "uefa.europa",
    "conference_league": "uefa.europa.conf",
    "fa_cup": "eng.fa",
    "carabao_cup": "eng.league_cup",
    "copa_del_rey": "esp.copa_del_rey",
    "international_friendly": "fifa.friendly",
}

# Internal league keys -> SofaScore unique tournament IDs
SOFASCORE_TOURNAMENTS: dict[str, int] = {
    "premier_league": 17,
    "laliga": 8,
    "champions_league": 7,
    "europa_league": 679,
    "conference_league": 17015,
    "fa_cup": 29,
    "carabao_cup": 21,
    "copa_del_rey": 329,
    "international_friendly": 10783,
}

# ESPN league code -> display name
ESPN_LEAGUE_NAMES: dict[str, str] = {
    "eng.1": "Premier League",
    "esp.1": "La Liga",
    "uefa.champions": "Champions League",
    "uefa.europa": "Europa League",
    "uefa.europa.conf": "Conference League",
    "eng.fa": "FA Cup",
    "eng.league_cup": "Carabao Cup",
    "esp.copa_del_rey": "Copa del Rey",
    "fifa.friendly": "International Friendlies",
}
