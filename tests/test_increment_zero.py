import ast
import importlib
from pathlib import Path
import sys
import unittest


BASE = Path(__file__).resolve().parents[1]
SRC = BASE / "src"
PACKAGE = SRC / "iceberg_router"
sys.path.insert(0, str(SRC))


EXPECTED_MODULES = {
    "iceberg_router",
    "iceberg_router.contracts",
    "iceberg_router.contracts._validation",
    "iceberg_router.contracts.decisions",
    "iceberg_router.contracts.events",
    "iceberg_router.contracts.feedback",
    "iceberg_router.contracts.identifiers",
    "iceberg_router.contracts.money",
    "iceberg_router.contracts.options",
    "iceberg_router.core",
    "iceberg_router.core.executor",
    "iceberg_router.core.governor",
    "iceberg_router.core.graph",
    "iceberg_router.core.journal",
    "iceberg_router.core.ledger",
    "iceberg_router.policies",
    "iceberg_router.policies.fixed",
    "iceberg_router.policies.random_mixture",
    "iceberg_router.policies.task_rule",
    "iceberg_router.adapters",
    "iceberg_router.testing",
}

ALLOWED_ICEBERG_IMPORTS = {
    "contracts": {"contracts"},
    "core": {"contracts"},
    "policies": {"contracts"},
    "adapters": {"contracts"},
    "testing": {"contracts", "core", "policies", "adapters", "testing"},
}


def module_name(path: Path) -> str:
    relative = path.relative_to(SRC).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_iceberg_layers(path: Path) -> set[str]:
    layers: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current = module_name(path).split(".")

    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = current if path.name == "__init__.py" else current[:-1]
                prefix = anchor[: len(anchor) - node.level + 1]
                absolute = ".".join(prefix + ((node.module or "").split(".")))
                names.append(absolute.rstrip("."))
            elif node.module:
                names.append(node.module)

        for name in names:
            parts = name.split(".")
            if len(parts) >= 2 and parts[0] == "iceberg_router":
                layers.add(parts[1])
    return layers


class IncrementZeroStructureTests(unittest.TestCase):
    def test_expected_modules_are_importable(self):
        discovered = {module_name(path) for path in PACKAGE.rglob("*.py")}
        self.assertEqual(EXPECTED_MODULES, discovered)
        for name in sorted(EXPECTED_MODULES):
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_product_layers_follow_dependency_direction(self):
        for path in PACKAGE.rglob("*.py"):
            relative = path.relative_to(PACKAGE)
            if len(relative.parts) < 2:
                allowed: set[str] = set()
            else:
                allowed = ALLOWED_ICEBERG_IMPORTS[relative.parts[0]]
            actual = imported_iceberg_layers(path)
            with self.subTest(path=str(relative)):
                self.assertLessEqual(actual, allowed)

    def test_scaffold_has_no_third_party_runtime_dependencies(self):
        for path in PACKAGE.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imports.append(node.module)
            with self.subTest(path=str(path.relative_to(PACKAGE))):
                self.assertTrue(
                    all(
                        name.split(".")[0] in sys.stdlib_module_names
                        or name == "iceberg_router"
                        or name.startswith("iceberg_router.")
                        for name in imports
                    ),
                    f"product module imports a third-party runtime dependency: {imports}",
                )

    def test_reference_directories_are_outside_product_package(self):
        product_roots = {path.name for path in PACKAGE.iterdir() if path.is_dir()}
        reference_roots = {
            "LLMRouterBench",
            "RouteLLM",
            "cascade-routing",
            "R2-Router",
            "LLMRouter",
            "litellm",
        }
        self.assertTrue(all((BASE / name).is_dir() for name in reference_roots))
        self.assertTrue(product_roots.isdisjoint(reference_roots))


if __name__ == "__main__":
    unittest.main()
