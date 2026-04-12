from pathlib import Path

import yaml


def test_config_yaml_has_required_sections() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "config" / "config.yaml"

    with config_path.open("r", encoding="utf-8") as file_handle:
        config = yaml.safe_load(file_handle)

    required_sections = {"ai", "embeddings", "logger", "storage", "server", "database"}
    assert required_sections.issubset(config.keys())


def test_database_queries_configured() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "config" / "config.yaml"

    with config_path.open("r", encoding="utf-8") as file_handle:
        config = yaml.safe_load(file_handle)

    queries = config.get("database", {}).get("queries", [])
    assert isinstance(queries, list)
    assert len(queries) > 0
