from __future__ import annotations

import ast
from dataclasses import dataclass, field

from hive_planner.config import RepoPaths
from hive_planner.map_sync import import_module_to_src_path


@dataclass
class PackageGraph:
    definitions: dict[str, set[str]] = field(default_factory=dict)
    imports: dict[str, set[str]] = field(default_factory=dict)
    imported_by: dict[str, set[str]] = field(default_factory=dict)
    callers: dict[str, set[str]] = field(default_factory=dict)


def _collect_definitions(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    names.add(f"{node.name}.{item.name}")
    return names


def _collect_import_maps(tree: ast.Module) -> tuple[set[str], dict[str, str]]:
    imported_paths: set[str] = set()
    name_to_def_key: dict[str, str] = {}

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("hive_planner"):
            module_src = import_module_to_src_path(node.module)
            if module_src:
                imported_paths.add(module_src)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                symbol_module = f"{node.module}.{alias.name}"
                symbol_src = import_module_to_src_path(symbol_module)
                if symbol_src:
                    imported_paths.add(symbol_src)
                    name_to_def_key[local] = f"{symbol_src}::{alias.name}"
                elif module_src:
                    name_to_def_key[local] = f"{module_src}::{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if not alias.name.startswith("hive_planner"):
                    continue
                module_src = import_module_to_src_path(alias.name)
                if module_src:
                    imported_paths.add(module_src)
                    local = alias.asname or alias.name.split(".")[-1]
                    name_to_def_key[local] = module_src

    return imported_paths, name_to_def_key


def _def_key_for_call(
    func: ast.expr,
    *,
    current_file: str,
    local_defs: set[str],
    name_to_def_key: dict[str, str],
    definitions: dict[str, set[str]],
) -> str | None:
    if isinstance(func, ast.Name):
        if func.id in name_to_def_key:
            key = name_to_def_key[func.id]
            if "::" in key:
                return key
            target_file = key
            if func.id in definitions.get(target_file, set()):
                return f"{target_file}::{func.id}"
        if func.id in local_defs:
            return f"{current_file}::{func.id}"
        return None

    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        base = func.value.id
        attr = func.attr
        if base in name_to_def_key:
            target = name_to_def_key[base]
            if "::" not in target:
                if attr in definitions.get(target, set()):
                    return f"{target}::{attr}"
        return None

    return None


def build_package_graph(paths: RepoPaths) -> PackageGraph:
    graph = PackageGraph()
    src_root = paths.root / "src" / "hive_planner"
    if not src_root.exists():
        return graph

    parsed: dict[str, tuple[ast.Module, set[str], dict[str, str]]] = {}
    for py_file in sorted(src_root.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        repo_path = py_file.relative_to(paths.root).as_posix()
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        if not isinstance(tree, ast.Module):
            continue
        local_defs = _collect_definitions(tree)
        imported_paths, name_to_def_key = _collect_import_maps(tree)
        graph.definitions[repo_path] = local_defs
        graph.imports[repo_path] = imported_paths
        parsed[repo_path] = (tree, local_defs, name_to_def_key)

    for importer, targets in graph.imports.items():
        for target in targets:
            graph.imported_by.setdefault(target, set()).add(importer)

    for caller_file, (tree, local_defs, name_to_def_key) in parsed.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            def_key = _def_key_for_call(
                node.func,
                current_file=caller_file,
                local_defs=local_defs,
                name_to_def_key=name_to_def_key,
                definitions=graph.definitions,
            )
            if def_key and not def_key.startswith(f"{caller_file}::"):
                graph.callers.setdefault(def_key, set()).add(caller_file)

    return graph


def secondary_call_targets(graph: PackageGraph, primary_repo_path: str) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    for importer in sorted(graph.imported_by.get(primary_repo_path, set())):
        if importer == primary_repo_path or importer in seen:
            continue
        seen.add(importer)
        results.append((importer, f"Imports {primary_repo_path} (dependency impact)"))

    prefix = f"{primary_repo_path}::"
    for def_key, caller_files in graph.callers.items():
        if not def_key.startswith(prefix):
            continue
        symbol = def_key.split("::", 1)[1]
        for caller in sorted(caller_files):
            if caller == primary_repo_path or caller in seen:
                continue
            seen.add(caller)
            results.append((caller, f"Call site for {symbol} in {primary_repo_path}"))

    return results
