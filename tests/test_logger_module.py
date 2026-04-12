import importlib.util
from pathlib import Path


def test_logger_module_exposes_public_api() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    logger_module_path = repo_root / "src" / "utils" / "logger.py"

    module_spec = importlib.util.spec_from_file_location("project_logger", logger_module_path)
    assert module_spec is not None
    assert module_spec.loader is not None

    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)

    assert hasattr(module, "get_project_root")
    assert hasattr(module, "setup_logger")


def test_get_project_root_returns_existing_directory() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    logger_module_path = repo_root / "src" / "utils" / "logger.py"

    module_spec = importlib.util.spec_from_file_location("project_logger", logger_module_path)
    assert module_spec is not None
    assert module_spec.loader is not None

    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)

    project_root = module.get_project_root()
    assert Path(project_root).exists()
    assert Path(project_root).is_dir()
