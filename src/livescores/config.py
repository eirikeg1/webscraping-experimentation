import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class GeneralConfig(BaseModel):
    poll_interval_min: float = 5.0
    poll_interval_max: float = 10.0
    schedule_refresh_minutes: int = 30

    @field_validator("poll_interval_min", "poll_interval_max")
    @classmethod
    def positive_interval(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Poll interval must be positive")
        return v


class SourcesConfig(BaseModel):
    priority: list[str] = Field(default_factory=lambda: ["espn", "sofascore"])
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown: int = 60

    @field_validator("priority")
    @classmethod
    def non_empty_priority(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Source priority list cannot be empty")
        return v


class LeaguesConfig(BaseModel):
    tracked: list[str] = Field(default_factory=lambda: ["premier_league", "laliga", "international_friendly"])


class TopTeamsConfig(BaseModel):
    names: list[str] = Field(default_factory=list)
    extra_competitions: list[str] = Field(default_factory=lambda: [
        "champions_league",
        "europa_league",
        "conference_league",
        "fa_cup",
        "carabao_cup",
        "copa_del_rey",
    ])


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000

    @field_validator("port")
    @classmethod
    def valid_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v


class AppConfig(BaseModel):
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    leagues: LeaguesConfig = Field(default_factory=LeaguesConfig)
    top_teams: TopTeamsConfig = Field(default_factory=TopTeamsConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        return AppConfig()

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    # Flatten top_teams.extra_competitions from nested TOML structure
    if "top_teams" in raw and "extra_competitions" in raw["top_teams"]:
        ec = raw["top_teams"]["extra_competitions"]
        if isinstance(ec, dict) and "include" in ec:
            raw["top_teams"]["extra_competitions"] = ec["include"]

    return AppConfig.model_validate(raw)
