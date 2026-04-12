import ast
from pathlib import Path


def _find_route_decorator_path(decorator: ast.AST) -> str | None:
    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            route_path = decorator.args[0].value
            if isinstance(route_path, str):
                return route_path
    return None


def test_server_exposes_operational_routes() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    server_path = repo_root / "src" / "server.py"
    server_ast = ast.parse(server_path.read_text(encoding="utf-8"))

    found_routes: set[str] = set()

    for node in ast.walk(server_ast):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                route_path = _find_route_decorator_path(decorator)
                if route_path:
                    found_routes.add(route_path)

    assert "/health" in found_routes
    assert "/ready" in found_routes
    assert "/metrics" in found_routes
