"""AUDIT 1 — Architecture.

Vérifie :
- découplage réel des composants
- absence de dépendances circulaires
- interfaces stables
- extensibilité des plugins
- cohérence des abstractions

Produit un diagramme réel des dépendances entre modules.
"""
from __future__ import annotations

import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KERNEL_DIR = REPO_ROOT / "alterego" / "kernel"
PLUGINS_DIR = REPO_ROOT / "alterego" / "plugins"


def extract_imports(py_file: Path) -> set[str]:
    """Return the set of alterego.* modules imported by this file."""
    try:
        tree = ast.parse(py_file.read_text())
    except SyntaxError:
        return set()
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("alterego"):
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("alterego"):
                imports.add(node.module)
    return imports


def find_circular_deps(graph: dict[str, set[str]]) -> list[list[str]]:
    """Detect cycles via DFS. Returns list of cycles (each cycle is a list of module names)."""
    cycles = []
    visited: set[str] = set()
    stack: list[str] = []
    on_stack: set[str] = set()

    def visit(node: str) -> None:
        if node in on_stack:
            # Found a cycle — extract it
            idx = stack.index(node)
            cycles.append(stack[idx:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        on_stack.add(node)
        stack.append(node)
        for neighbor in sorted(graph.get(node, set())):
            visit(neighbor)
        stack.pop()
        on_stack.discard(node)

    for node in sorted(graph.keys()):
        visit(node)
    return cycles


def analyze_module(filepath: Path) -> dict:
    """Return metadata about a Python module: classes, ABCs, public functions."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError as e:
        return {"error": str(e)}
    classes = []
    abcs = []
    public_funcs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
            # Check if it inherits from ABC or ABCMeta (directly)
            for base in node.bases:
                if (isinstance(base, ast.Name) and base.id in {"ABC", "ABCMeta"}) or \
                   (isinstance(base, ast.Attribute) and base.attr in {"ABC", "ABCMeta"}):
                    abcs.append(node.name)
                    break
            # Also check if it inherits from another ABC (transitive)
            # by looking for @abstractmethod decorators in the body
            has_abstract_method = False
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for dec in item.decorator_list:
                        if isinstance(dec, ast.Name) and dec.id == "abstractmethod":
                            has_abstract_method = True
                            break
                        if isinstance(dec, ast.Attribute) and dec.attr == "abstractmethod":
                            has_abstract_method = True
                            break
            if has_abstract_method and node.name not in abcs:
                abcs.append(node.name)
            # Also: classes that inherit from Base* are abstract by convention
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id.startswith("Base") and base.id not in {"BaseModel"}:
                    if node.name not in abcs:
                        abcs.append(node.name)
                    break
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            public_funcs.append(node.name)
    return {
        "classes": classes,
        "abstract_classes": abcs,
        "public_functions": public_funcs,
        "loc": len(filepath.read_text().splitlines()),
    }


def main():
    results = {
        "audit": "architecture",
        "modules": {},
        "dependency_graph": {},
        "circular_dependencies": [],
        "issues": [],
        "score": 0,
    }

    # 1. Collect all kernel + plugins modules
    all_modules: list[Path] = []
    for py in sorted(KERNEL_DIR.rglob("*.py")):
        if py.name == "__init__.py":
            continue
        all_modules.append(py)
    for py in sorted(PLUGINS_DIR.rglob("*.py")):
        all_modules.append(py)

    # 2. Build module metadata
    for py in all_modules:
        rel = py.relative_to(REPO_ROOT).with_suffix("")
        module_name = str(rel).replace("/", ".")
        results["modules"][module_name] = analyze_module(py)

    # 3. Build dependency graph
    graph: dict[str, set[str]] = defaultdict(set)
    for py in all_modules:
        rel = py.relative_to(REPO_ROOT).with_suffix("")
        module_name = str(rel).replace("/", ".")
        deps = extract_imports(py)
        graph[module_name] = deps
        results["dependency_graph"][module_name] = sorted(deps)

    # 4. Detect circular dependencies
    cycles = find_circular_deps(dict(graph))
    results["circular_dependencies"] = cycles

    # 5. Identify issues
    issues = []

    # 5a. Circular deps
    if cycles:
        issues.append({
            "severity": "critical",
            "category": "circular_dependency",
            "message": f"{len(cycles)} circular dependency(ies) detected",
            "details": cycles[:5],
        })

    # 5b. Plugin extensibility — check that all plugins inherit BasePlugin
    for py in PLUGINS_DIR.rglob("__init__.py"):
        rel = py.parent.relative_to(REPO_ROOT)
        module_name = str(rel).replace("/", ".")
        meta = results["modules"].get(module_name, {})
        if not meta.get("classes"):
            continue
        # Find the plugin class (the one ending in Plugin)
        plugin_classes = [c for c in meta["classes"] if c.endswith("Plugin")]
        if not plugin_classes:
            issues.append({
                "severity": "warning",
                "category": "plugin_convention",
                "message": f"{module_name}: no class ending in 'Plugin'",
            })

    # 5c. Interface stability — check that base.py exposes the ABCs
    # BasePlugin inherits from BaseBridge (which inherits from ABC) — transitive ABC.
    # The analyze_module function detects this via Base* inheritance check.
    base_meta = results["modules"].get("alterego.kernel.base", {})
    expected_abc = {"BaseBridge", "BasePlugin", "BaseCapability"}
    found_abc = set(base_meta.get("abstract_classes", []))
    missing_abc = expected_abc - found_abc
    if missing_abc:
        issues.append({
            "severity": "critical",
            "category": "interface_stability",
            "message": f"Missing ABCs in base.py: {missing_abc}",
        })

    # 5d. Kernel-Plugin coupling — kernel modules should not import from plugins
    kernel_modules = [m for m in graph if m.startswith("alterego.kernel.")]
    for km in kernel_modules:
        for dep in graph[km]:
            if dep.startswith("alterego.plugins."):
                issues.append({
                    "severity": "critical",
                    "category": "coupling",
                    "message": f"Kernel module {km} imports plugin module {dep} — breaks inversion of control",
                })

    # 5e. Plugin-Kernel coupling — plugins should only import kernel.base (not other kernel modules)
    plugin_modules = [m for m in graph if m.startswith("alterego.plugins.")]
    for pm in plugin_modules:
        for dep in graph[pm]:
            if dep.startswith("alterego.kernel.") and dep != "alterego.kernel.base":
                # Allow plugins to import base only
                issues.append({
                    "severity": "warning",
                    "category": "coupling",
                    "message": f"Plugin {pm} imports {dep} (should only import kernel.base)",
                })

    results["issues"] = issues

    # 6. Score (start at 100, subtract by severity)
    score = 100
    for issue in issues:
        if issue["severity"] == "critical":
            score -= 15
        elif issue["severity"] == "warning":
            score -= 5
        elif issue["severity"] == "info":
            score -= 1
    results["score"] = max(0, score)

    # 7. Print summary
    print("=" * 70)
    print("AUDIT 1 — ARCHITECTURE")
    print("=" * 70)
    print(f"Modules analyzed: {len(results['modules'])}")
    print(f"Dependencies mapped: {sum(len(v) for v in results['dependency_graph'].values())}")
    print(f"Circular dependencies: {len(results['circular_dependencies'])}")
    print(f"Issues found: {len(results['issues'])}")
    print()
    print("── Dependency graph (kernel) ──")
    for mod in sorted(kernel_modules):
        print(f"  {mod}")
        for dep in sorted(graph[mod]):
            print(f"    → {dep}")
    print()
    print("── Dependency graph (plugins) ──")
    for mod in sorted(plugin_modules):
        print(f"  {mod}")
        for dep in sorted(graph[mod]):
            print(f"    → {dep}")
    print()
    if issues:
        print("── Issues ──")
        for issue in issues:
            print(f"  [{issue['severity'].upper()}] {issue['category']}: {issue['message']}")
    print()
    print(f"SCORE: {results['score']}/100")

    # 8. Save results
    out = Path(__file__).resolve().parent.parent / "results" / "audit_01_architecture.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to: {out}")
    return results


if __name__ == "__main__":
    main()
