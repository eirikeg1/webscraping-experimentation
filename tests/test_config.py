"""Tests for config loading and validation. Written before implementation."""

import pytest

from livescores.config import AppConfig, load_config


class TestLoadConfig:
    def test_load_valid_config(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[general]
poll_interval_min = 5.0
poll_interval_max = 10.0
schedule_refresh_minutes = 30

[sources]
priority = ["espn", "sofascore"]

[leagues]
tracked = ["premier_league", "laliga"]

[top_teams]
names = ["Arsenal", "Barcelona"]

[top_teams.extra_competitions]
include = ["champions_league", "fa_cup"]

[server]
host = "0.0.0.0"
port = 8000
""")
        config = load_config(config_file)
        assert config.general.poll_interval_min == 5.0
        assert config.general.poll_interval_max == 10.0
        assert config.general.schedule_refresh_minutes == 30
        assert config.sources.priority == ["espn", "sofascore"]
        assert "premier_league" in config.leagues.tracked
        assert "Arsenal" in config.top_teams.names
        assert "champions_league" in config.top_teams.extra_competitions
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000

    def test_load_minimal_config_uses_defaults(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("")
        config = load_config(config_file)
        assert config.general.poll_interval_min == 5.0
        assert config.general.poll_interval_max == 10.0
        assert config.general.schedule_refresh_minutes == 30
        assert config.sources.priority == ["espn", "sofascore"]
        assert config.server.port == 8000

    def test_load_partial_config(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[top_teams]
names = ["Real Madrid"]
""")
        config = load_config(config_file)
        assert "Real Madrid" in config.top_teams.names
        # Defaults still apply for unspecified sections
        assert config.general.poll_interval_min == 5.0

    def test_missing_file_uses_defaults(self, tmp_path):
        config_file = tmp_path / "nonexistent.toml"
        config = load_config(config_file)
        assert isinstance(config, AppConfig)
        assert config.general.poll_interval_min == 5.0


class TestAppConfig:
    def test_poll_interval_min_must_be_positive(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[general]
poll_interval_min = -1.0
""")
        with pytest.raises(ValueError):
            load_config(config_file)

    def test_poll_interval_max_must_be_positive(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[general]
poll_interval_max = 0
""")
        with pytest.raises(ValueError):
            load_config(config_file)

    def test_port_must_be_valid(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[server]
port = 99999
""")
        with pytest.raises(ValueError):
            load_config(config_file)

    def test_empty_priority_list_rejected(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[sources]
priority = []
""")
        with pytest.raises(ValueError):
            load_config(config_file)
