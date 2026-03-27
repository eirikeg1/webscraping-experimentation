import re
import unicodedata
from difflib import SequenceMatcher

# Alias groups: each list contains names that refer to the same team.
# All comparisons use the first entry as the canonical form.
_ALIAS_GROUPS: list[list[str]] = [
    # Premier League
    ["manchester united", "man utd", "man united"],
    ["manchester city", "man city"],
    ["tottenham hotspur", "tottenham", "spurs"],
    ["wolverhampton wanderers", "wolves"],
    ["brighton and hove albion", "brighton", "brighton & hove albion"],
    ["west ham united", "west ham"],
    ["newcastle united", "newcastle"],
    ["nottingham forest", "nott'm forest", "nottm forest"],
    ["leicester city", "leicester"],
    ["ipswich town", "ipswich"],
    ["crystal palace", "c. palace"],
    ["afc bournemouth", "bournemouth"],
    # La Liga
    ["atletico madrid", "atletico de madrid", "atl. madrid", "atl madrid", "club atletico de madrid"],
    ["real betis", "real betis balompie"],
    ["real sociedad", "real sociedad de futbol"],
    ["athletic bilbao", "athletic club", "athletic club bilbao"],
    ["rcd espanyol", "espanyol"],
    ["deportivo alaves", "alaves"],
    ["rcd mallorca", "mallorca"],
    ["real valladolid", "valladolid"],
    ["celta vigo", "celta de vigo", "rc celta"],
    ["ud las palmas", "las palmas"],
    ["ca osasuna", "osasuna"],
    ["cd leganes", "leganes"],
    ["girona fc", "girona"],
    ["getafe cf", "getafe"],
    ["rayo vallecano", "rayo"],
    ["villarreal cf", "villarreal"],
    ["sevilla fc", "sevilla"],
    ["valencia cf", "valencia"],
    ["real madrid", "real madrid cf"],
    ["barcelona", "fc barcelona", "barca"],
]

# Build lookup: normalized alias -> set of all normalized aliases in that group
_ALIAS_LOOKUP: dict[str, set[str]] = {}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def normalize_name(name: str) -> str:
    """Normalize a team name for comparison."""
    name = name.strip().lower()
    name = _strip_accents(name)
    # Strip common suffixes
    name = re.sub(r"\s+(fc|cf|sc|afc)$", "", name)
    return name.strip()


def _build_alias_lookup() -> None:
    for group in _ALIAS_GROUPS:
        normalized_group = {normalize_name(alias) for alias in group}
        for alias in normalized_group:
            _ALIAS_LOOKUP[alias] = normalized_group


_build_alias_lookup()


def are_same_team(name1: str, name2: str) -> bool:
    """Check if two team names refer to the same team."""
    if not name1 or not name2:
        return False

    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    # Exact match after normalization
    if n1 == n2:
        return True

    # Check alias table
    aliases1 = _ALIAS_LOOKUP.get(n1)
    aliases2 = _ALIAS_LOOKUP.get(n2)

    if aliases1 and n2 in aliases1:
        return True
    if aliases2 and n1 in aliases2:
        return True

    # If either name is in the alias table but didn't match the other,
    # they are definitively different teams (prevents "Man United" ≈ "Man City")
    if aliases1 or aliases2:
        return False

    # Fuzzy match as fallback for names not in the alias table
    ratio = SequenceMatcher(None, n1, n2).ratio()
    return ratio >= 0.8
