from __future__ import annotations

from secret_santa.bot import config as config_module
from secret_santa.bot.config import Config


def test_config_loads_project_env_and_resolves_relative_database_path(
    tmp_path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    env_file = project_root / ".env"
    env_file.write_text(
        "BOT_TOKEN=test-token\nDATABASE_PATH=data/secret_santa.db\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "_PROJECT_ROOT", project_root)
    monkeypatch.setattr(config_module, "_ENV_FILE", env_file)
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    config = Config.from_env()

    assert config.bot_token == "test-token"
    assert config.database_path == str(project_root / "data" / "secret_santa.db")


def test_config_defaults_to_database_in_project_root(tmp_path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(config_module, "_PROJECT_ROOT", project_root)
    monkeypatch.setattr(
        config_module,
        "_DEFAULT_DATABASE_PATH",
        project_root / "secret_santa.db",
    )
    monkeypatch.setattr(config_module, "_ENV_FILE", project_root / ".env")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.delenv("DATABASE_PATH", raising=False)

    config = Config.from_env()

    assert config.database_path == str(project_root / "secret_santa.db")


def test_config_preserves_absolute_database_path(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "data" / "secret_santa.db"
    monkeypatch.setattr(config_module, "_ENV_FILE", tmp_path / ".env")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))

    config = Config.from_env()

    assert config.database_path == str(database_path)
