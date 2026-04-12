from pathlib import Path


def test_docs_diagram_assets_exist() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    images_dir = repo_root / "docs" / "images"

    expected_assets = [
        images_dir / "architecture_overview.mmd",
        images_dir / "architecture_overview.png",
        images_dir / "experimental_workflow.mmd",
        images_dir / "experimental_workflow.png",
    ]

    for asset in expected_assets:
        assert asset.exists(), f"Missing asset: {asset}"
