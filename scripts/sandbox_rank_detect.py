"""Read-only bug detector. Emits rank-rows.jsonl lines for H drive repos.

Does not modify the repos it scans. A defect row uses outcome review-failed.
A file with no defect uses outcome empty and six zero signals. The
rank-weights sandbox counts review-failed as a bug and empty as not a bug.

    py -3.11 scripts/sandbox_rank_detect.py
    py -3.11 scripts/sandbox_rank_detect.py --self-check
    py -3.11 scripts/sandbox_rank_detect.py --out rows.jsonl
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SIGNALS = (
    "recent_fix_commits",
    "thin_test",
    "wiring_hop",
    "dead_setting",
    "reverted",
    "split_stores",
)
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    ".vs",
    "__pycache__",
    "bin",
    "node_modules",
    "obj",
    "site-packages",
    "venv",
}
# Unity cache folders. Matched whole, so Templates is not skipped.
SKIP_DIR_EXACT = {"Library", "Temp", "Logs"}
MAX_BYTES = 400_000
GIT_COMMITS = 250
MIX_TARGET = 400
# Repos whose smoke test produced no defect rows. Empty rows are drawn here first.
CLEAN_FIRST = frozenset({"coleman", "BLUETTOOTH_SURROUND", "robust-weight-transfer"})

H_MATCHES = Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES")
DEFAULT_REPOS = (
    H_MATCHES / "HIVE_CODE_PLANNER",
    H_MATCHES / "STABLE_FLOW_SPZ_UVSEAM",
    H_MATCHES / "ROBUST_WEIGHT_TRANSFER" / "robust-weight-transfer",
    H_MATCHES / "LEITNER_LEARNING",
    H_MATCHES / "spec-kit",
    H_MATCHES / "ANDROID_MOVIE_APP",
    H_MATCHES / "UNITY_CHAIN_TOON_SHADER",
    H_MATCHES / "HIVE_CODE_DEV_1",
    H_MATCHES / "GEN_PBR",
    H_MATCHES / "zed",
    H_MATCHES / "BLUETTOOTH_SURROUND",
    Path(r"H:\DRIVE_DOWNLOADS\BUGHUNT_RANKING_REFERENCES\coleman"),
)

_FIX = re.compile(r"\b(fix|bug|bugfix|hotfix)\b", re.IGNORECASE)
_CATCH_PAREN = re.compile(r"catch\s*\(([^)]*)\)", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    line: int
    severity: str
    text: str


@dataclass
class Signals:
    recent_fix_commits: int = 0
    thin_test: int = 0
    wiring_hop: int = 0
    dead_setting: int = 0
    reverted: int = 0
    split_stores: int = 0

    def as_dict(self) -> dict[str, int]:
        return {name: int(getattr(self, name)) for name in SIGNALS}

    def weighted_sum(self) -> float:
        from hive_planner.bug_hunt import score_signals

        values = [float(getattr(self, name)) for name in SIGNALS]
        return score_signals(values)


def _skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name in SKIP_DIR_EXACT


def iter_source(root: Path) -> list[Path]:
    found: list[Path] = []
    if not root.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if not _skip_dir(name)]
        for name in filenames:
            lower = name.lower()
            if lower.endswith(".py") or lower.endswith(".cs"):
                found.append(Path(dirpath) / name)
    return found


def _read(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_mutable_default(node: ast.AST | None) -> bool:
    if node is None:
        return False
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    if isinstance(node, ast.Call):
        name = _call_name(node.func)
        return name in {"list", "dict", "set"}
    return False


def _return_in_body(nodes: list[ast.stmt]) -> ast.Return | None:
    """A return that runs in this body. Returns inside a nested function do not count."""
    for node in nodes:
        if isinstance(node, ast.Return):
            return node
        groups: list[list[ast.stmt]] = []
        if isinstance(node, ast.If):
            groups = [node.body, node.orelse]
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            groups = [node.body, node.orelse]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            groups = [node.body]
        elif isinstance(node, ast.Match):
            groups = [case.body for case in node.cases]
        elif isinstance(node, (ast.Try, ast.TryStar)):
            groups = [node.body, node.orelse, node.finalbody]
            groups.extend(handler.body for handler in node.handlers)
        for group in groups:
            found = _return_in_body(group)
            if found is not None:
                return found
    return None


def _body_is_noop(body: list[ast.stmt]) -> bool:
    """pass, or a bare ellipsis. Both swallow the exception."""
    if len(body) != 1:
        return False
    stmt = body[0]
    if isinstance(stmt, ast.Pass):
        return True
    # A literal, including `...`, does not handle the exception.
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)


def _is_broad_except(node: ast.AST | None) -> bool:
    names = {"Exception", "BaseException"}
    if node is None:
        return False
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Tuple) and node.elts:
        return all(isinstance(item, ast.Name) and item.id in names for item in node.elts)
    return False


def python_findings(source: str) -> list[Finding] | None:
    """Defects, or None when the file does not parse. None is not a clean file."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    found: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            defaults = list(node.args.defaults) + [
                item for item in node.args.kw_defaults if item is not None
            ]
            for default in defaults:
                if _is_mutable_default(default):
                    label = node.name if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "lambda"
                    found.append(
                        Finding(
                            getattr(default, "lineno", getattr(node, "lineno", 1)),
                            "high",
                            f"mutable default argument on {label}",
                        )
                    )
                    break
        elif isinstance(node, (ast.Try, ast.TryStar)):
            returned = _return_in_body(list(node.finalbody))
            if returned is not None:
                found.append(
                    Finding(
                        returned.lineno,
                        "high",
                        "return inside finally discards the pending exception",
                    )
                )
            for handler in node.handlers:
                if handler.type is None:
                    found.append(
                        Finding(handler.lineno, "high", "bare except catches every exception including interrupts")
                    )
                elif _is_broad_except(handler.type) and _body_is_noop(handler.body):
                    found.append(
                        Finding(handler.lineno, "medium", "broad except whose body does nothing")
                    )
    return found


def _verbatim_prefix_len(text: str, index: int) -> int:
    """Length of @\", $@\", or @$\" starting at index. Longer prefixes win."""
    for prefix in ('$@"', '@$"', '@"'):
        if text.startswith(prefix, index):
            return len(prefix)
    return 0


def _scan_verbatim(text: str, content_at: int) -> tuple[int, bool]:
    """Scan a verbatim string body. A doubled quote stays inside. Newlines stay inside."""
    index = content_at
    length = len(text)
    while index < length:
        if text[index] == '"':
            if index + 1 < length and text[index + 1] == '"':
                index += 2
                continue
            return index + 1, True
        index += 1
    return length, False


def _skip_cs_token(text: str, index: int) -> int | None:
    """If a comment or string starts here, return the index just past it."""
    length = len(text)
    if index >= length:
        return None
    char = text[index]
    if char == "/" and index + 1 < length and text[index + 1] == "/":
        newline = text.find("\n", index)
        return length if newline < 0 else newline + 1
    if char == "/" and index + 1 < length and text[index + 1] == "*":
        end = text.find("*/", index + 2)
        return length if end < 0 else end + 2
    prefix = _verbatim_prefix_len(text, index)
    if prefix:
        end, _closed = _scan_verbatim(text, index + prefix)
        return end
    if char in "'\"":
        quote = char
        index += 1
        while index < length and text[index] != quote:
            if text[index] == "\\":
                index += 2
                continue
            if text[index] == "\n":
                break
            index += 1
        return index + 1
    return None


def _brace_from(text: str, origin: int) -> str:
    """Catch body starting at origin. Braces inside strings and comments do not count."""
    index = max(0, origin)
    length = len(text)
    depth = 0
    started = False
    start = index
    while index < length:
        skipped = _skip_cs_token(text, index)
        if skipped is not None:
            index = skipped
            continue
        char = text[index]
        if char == "{":
            if not started:
                started = True
                start = index
            depth += 1
        elif char == "}" and started:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
        index += 1
    return text[start:] if started else ""


def _cs_code_only(text: str) -> str:
    """Source with comments and string contents removed, so they cannot look like code."""
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        skipped = _skip_cs_token(text, index)
        if skipped is not None:
            if text[index] == "/" and index + 1 < length and text[index + 1] == "*":
                out.append(" ")
            index = skipped
            continue
        out.append(text[index])
        index += 1
    return "".join(out)


def _mask_cs_line(line: str, in_block: bool, in_verbatim: bool) -> tuple[str, bool, bool]:
    """Blank comments and string contents. Indexes stay aligned with the raw line.

    Verbatim strings continue onto the next line. A catch inside one is not code.
    """
    chars = list(line)
    index = 0
    length = len(chars)
    while index < length:
        if in_verbatim:
            end, closed = _scan_verbatim(line, index)
            for blank in range(index, min(end, length)):
                chars[blank] = " "
            index = min(end, length)
            in_verbatim = not closed
            if not closed:
                break
            continue
        if in_block:
            if index + 1 < length and chars[index] == "*" and chars[index + 1] == "/":
                chars[index] = " "
                chars[index + 1] = " "
                index += 2
                in_block = False
                continue
            chars[index] = " "
            index += 1
            continue
        prefix = _verbatim_prefix_len(line, index)
        if prefix:
            end, closed = _scan_verbatim(line, index + prefix)
            for blank in range(index, min(end, length)):
                chars[blank] = " "
            index = min(end, length)
            in_verbatim = not closed
            if not closed:
                break
            continue
        skipped = _skip_cs_token(line, index)
        if skipped is None:
            index += 1
            continue
        if line[index] == "/" and index + 1 < len(line) and line[index + 1] == "*":
            in_block = "*/" not in line[index + 2 :]
            end = min(skipped, length)
            for blank in range(index, end):
                chars[blank] = " "
            index = end
            continue
        end = min(skipped, length)
        for blank in range(index + 1, max(index + 1, end - 1)):
            chars[blank] = " "
        index = end
    return "".join(chars), in_block, in_verbatim


def _cs_body_is_empty(compact: str) -> bool:
    """{} or a body of only semicolons. Comments and strings are already gone."""
    if len(compact) < 2 or compact[0] != "{" or compact[-1] != "}":
        return False
    return set(compact[1:-1]) <= {";"}


def csharp_findings(source: str) -> list[Finding]:
    found: list[Finding] = []
    lines = source.splitlines()
    in_block = False
    in_verbatim = False
    for index, line in enumerate(lines):
        masked, in_block, in_verbatim = _mask_cs_line(line, in_block, in_verbatim)
        cursor = 0
        while True:
            match = re.search(r"\bcatch\b", masked[cursor:])
            if match is None:
                break
            at = cursor + match.start()
            cursor = at + len("catch")
            # Anchor at this catch. A search would borrow the next catch's variable.
            paren = _CATCH_PAREN.match(masked, at)
            parts = paren.group(1).split() if paren else []
            variable = parts[-1] if len(parts) >= 2 else ""
            window = "\n".join(lines[index : index + 80])
            # origin is this catch keyword, so a try-block brace earlier on the line is ignored
            snippet = _brace_from(window, at)
            code = _cs_code_only(snippet)
            compact = "".join(code.split())
            if _cs_body_is_empty(compact):
                found.append(Finding(index + 1, "medium", "empty catch discards the exception"))
                continue
            if variable and re.search(rf"\bthrow\s+{re.escape(variable)}\s*;", code):
                found.append(
                    Finding(index + 1, "high", f"throw {variable} inside catch resets the stack trace")
                )
    return found


def findings_for(path: Path, source: str) -> list[Finding] | None:
    if path.suffix.lower() == ".py":
        return python_findings(source)
    if path.suffix.lower() == ".cs":
        return csharp_findings(source)
    return []


def _normalize_git_path(rel: str) -> str:
    """Posix path. Quoted names and rename arrows are reduced to the new path."""
    rel = rel.strip().replace("\\", "/")
    if len(rel) >= 2 and rel.startswith('"') and rel.endswith('"'):
        rel = rel[1:-1]
    while " => " in rel:
        renamed = re.search(r"\{([^{}]*) => ([^{}]*)\}", rel)
        if renamed is not None:
            rel = rel[: renamed.start()] + renamed.group(2).strip() + rel[renamed.end() :]
            continue
        rel = rel.split(" => ")[-1].strip()
        break
    if rel.startswith("./"):
        rel = rel[2:]
    return rel


def parse_git_log(stdout: str) -> tuple[dict[str, int], set[str]]:
    fixes: dict[str, int] = {}
    reverted: set[str] = set()
    for chunk in stdout.split("\x1e"):
        # \x1f separates the subject from the path list. Without it, an empty
        # subject would make the first path look like the subject, and a path
        # named fix.py would be counted as a fix commit.
        if "\x1f" in chunk:
            subject_raw, rest = chunk.split("\x1f", 1)
            subject = subject_raw.strip()
            paths = [line.strip() for line in rest.splitlines() if line.strip()]
        else:
            lines = [line.strip() for line in chunk.splitlines() if line.strip()]
            if not lines:
                continue
            subject = lines[0]
            paths = lines[1:]
        is_revert = subject.lower().startswith("revert")
        is_fix = bool(subject) and (is_revert or _FIX.search(subject) is not None)
        if not is_fix:
            continue
        for raw in paths:
            rel = _normalize_git_path(raw)
            if not rel or rel.endswith(":"):
                continue
            fixes[rel] = fixes.get(rel, 0) + 1
            if is_revert:
                reverted.add(rel)
    return fixes, reverted


def git_history(root: Path) -> tuple[dict[str, int], set[str]]:
    """Fix-commit counts and reverted paths. Does not write git config.

    ``safe.directory=*`` is a one-command override. The H drive copies are
    owned by another machine, and git otherwise refuses to read them.
    """
    if not (root / ".git").exists():
        return {}, set()
    try:
        completed = subprocess.run(
            [
                "git",
                "-c",
                "safe.directory=*",
                "-c",
                f"safe.directory={root.resolve().as_posix()}",
                "-C",
                str(root),
                "log",
                f"-n{GIT_COMMITS}",
                "--pretty=format:%x1e%s%x1f",
                "--name-only",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}, set()
    if completed.returncode != 0:
        return {}, set()
    return parse_git_log(completed.stdout)


def _names_loaded(tree: ast.AST) -> set[str]:
    loaded: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loaded.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            loaded.add(node.attr)
    return loaded


def python_signals(source: str, thin: int) -> Signals:
    signals = Signals(thin_test=1 if thin else 0)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return signals
    defined: list[str] = []
    module_assigns: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    module_assigns[target.id] = module_assigns.get(target.id, 0) + 1
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            module_assigns[node.target.id] = module_assigns.get(node.target.id, 0) + 1
    loaded = _names_loaded(tree)
    if any(name not in loaded for name in defined):
        signals.wiring_hop = 1
    if any(
        name.isupper() and count >= 1 and name not in loaded
        for name, count in module_assigns.items()
    ):
        signals.dead_setting = 1
    if any(count >= 2 for count in module_assigns.values()):
        signals.split_stores = 1
    return signals


_CS_CONTROL_CALLS = frozenset(
    {"if", "for", "foreach", "while", "switch", "catch", "using", "lock", "nameof"}
)
_CS_METHOD = re.compile(
    r"\b(?:public|private|protected|internal|static|virtual|override|abstract|async|sealed|partial|new|extern|\s)+"
    r"\b[\w<>,\[\]?]+\s+([A-Za-z_]\w*)\s*\("
)
_CS_ASSIGNMENT = re.compile(
    r"(?:(?:public|private|protected|internal|static|readonly|const)\s+)*"
    r"(?:[\w<>,\[\]?]+\s+)([A-Z][A-Za-z0-9_]*)\s*="
)


def csharp_signals(source: str, thin: int) -> Signals:
    """Extract the same wiring/settings/store signals for bounded C# scans."""
    signals = Signals(thin_test=1 if thin else 0)
    try:
        masked_lines: list[str] = []
        in_block = False
        in_verbatim = False
        for line in source.splitlines():
            masked, in_block, in_verbatim = _mask_cs_line(line, in_block, in_verbatim)
            masked_lines.append(masked)
        masked_source = "\n".join(masked_lines)
        methods = [match.group(1) for match in _CS_METHOD.finditer(masked_source)]
        calls = [
            match.group(1)
            for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", masked_source)
            if match.group(1) not in _CS_CONTROL_CALLS
        ]
        if any(calls.count(name) == 1 for name in methods):
            signals.wiring_hop = 1
        assignments = [match.group(1) for match in _CS_ASSIGNMENT.finditer(masked_source)]
        loaded = set(re.findall(r"\b([A-Z][A-Za-z0-9_]*)\b", masked_source))
        if any(name not in loaded - {name} for name in assignments):
            signals.dead_setting = 1
        if any(assignments.count(name) >= 2 for name in set(assignments)):
            signals.split_stores = 1
    except (MemoryError, RecursionError):
        return signals
    return signals


def _is_test_rel(rel: str) -> bool:
    """A test file by path segment or file name. `testimony.py` is not a test."""
    path = PurePosixPath(rel.replace("\\", "/").lower())
    stem = path.stem
    if stem in {"test", "tests"} or stem.startswith("test_") or stem.endswith("_test") or stem.endswith("tests"):
        return True
    for part in path.parts[:-1]:
        if part in {"test", "tests", "testing"} or part.startswith("test_") or part.endswith("_test") or part.endswith("_tests"):
            return True
    return False


def test_stems(paths: list[Path], root: Path) -> set[str]:
    stems: set[str] = set()
    for path in paths:
        rel = path.relative_to(root).as_posix()
        if _is_test_rel(rel):
            name = path.stem.lower()
            stems.add(name.removeprefix("test_").removesuffix("_test").removesuffix("tests"))
    return stems


def is_thin(path: Path, root: Path, stems: set[str]) -> bool:
    if _is_test_rel(path.relative_to(root).as_posix()):
        return False
    return path.stem.lower() not in stems


def _zero_signals() -> dict[str, int]:
    return {name: 0 for name in SIGNALS}


def empty_row(repo_name: str, rel: str) -> dict[str, object]:
    """A checked file with no defect. Every signal stays zero."""
    return {
        "file": f"{repo_name}/{rel}",
        "signals": _zero_signals(),
        "weighted_sum": 0,
        "scenario": f"{repo_name}: no static defect ({rel})",
        "outcome": "empty",
    }


def sample_empty(
    clean: list[tuple[str, str]],
    count: int,
    *,
    seed: int = 0,
) -> list[dict[str, object]]:
    """Draw `count` clean files. The three smoke-clean repos are used first."""
    if count <= 0 or not clean:
        return []
    first = [item for item in clean if item[0] in CLEAN_FIRST]
    rest = [item for item in clean if item[0] not in CLEAN_FIRST]
    first = list(dict.fromkeys(first))
    rest = list(dict.fromkeys(rest))
    first.sort()
    rest.sort()
    pool = first if len(first) >= count else first + rest
    if len(pool) > count:
        chosen = random.Random(seed).sample(pool, count)
        chosen.sort()
    else:
        chosen = pool
    return [empty_row(repo, rel) for repo, rel in chosen]


def interleave_rows(bugs: list, empties: list) -> list:
    """Spread both outcomes through the file.

    The weight sandbox cuts at 70 percent in file order. A block of defects
    followed by a block of empty rows puts one class in the holdout.
    """
    bug_count = len(bugs)
    empty_count = len(empties)
    mixed: list = []
    bug_index = 0
    empty_index = 0
    while bug_index < bug_count or empty_index < empty_count:
        if bug_index < bug_count and (
            empty_index >= empty_count or bug_index * empty_count <= empty_index * bug_count
        ):
            mixed.append(bugs[bug_index])
            bug_index += 1
        else:
            mixed.append(empties[empty_index])
            empty_index += 1
    return mixed


def scan_repo(root: Path) -> tuple[list[dict[str, object]], list[str]]:
    """Defect rows, and repo-relative paths that parsed and had no defect."""
    paths = iter_source(root)
    stems = test_stems(paths, root)
    fixes, reverted = git_history(root)
    fix_lookup: dict[str, int] = {}
    for key, value in fixes.items():
        folded = key.casefold()
        fix_lookup[folded] = fix_lookup.get(folded, 0) + value
    revert_lookup = {key.casefold() for key in reverted}
    rows: list[dict[str, object]] = []
    clean: list[str] = []
    repo_name = root.name
    for path in paths:
        source = _read(path)
        if source is None:
            continue
        rel = path.relative_to(root).as_posix()
        found = findings_for(path, source)
        if found is None:
            continue
        if not found:
            clean.append(rel)
            continue
        if path.suffix.lower() == ".py":
            signals = python_signals(source, 1 if is_thin(path, root, stems) else 0)
        else:
            signals = Signals(thin_test=1 if is_thin(path, root, stems) else 0)
        signals.recent_fix_commits = fix_lookup.get(rel.casefold(), 0)
        if rel.casefold() in revert_lookup:
            signals.reverted = 1
        for item in found:
            scenario = f"{repo_name}: {item.severity}: {item.text} ({rel}:{item.line})"
            rows.append(
                {
                    "file": f"{repo_name}/{rel}",
                    "signals": signals.as_dict(),
                    "weighted_sum": signals.weighted_sum(),
                    "scenario": scenario,
                    "outcome": "review-failed",
                }
            )
    return rows, clean


def self_check() -> None:
    mutable = python_findings("def build(items=[]):\n    return items\n")
    if not any("mutable default" in item.text for item in mutable):
        raise SystemExit("self-check missed a mutable default")
    swallowed = python_findings("def run():\n    try:\n        work()\n    except Exception:\n        pass\n")
    if not any("does nothing" in item.text for item in swallowed):
        raise SystemExit("self-check missed a swallowed exception")
    bare = python_findings("def run():\n    try:\n        work()\n    except:\n        work()\n")
    if not any("bare except" in item.text for item in bare):
        raise SystemExit("self-check missed a bare except")
    final = python_findings(
        "def run():\n    try:\n        work()\n    finally:\n        return 1\n"
    )
    if not any("finally" in item.text for item in final):
        raise SystemExit("self-check missed a return in finally")
    sharp = csharp_findings("void Run() {\n  try { Work(); }\n  catch (Exception ex) { throw ex; }\n}\n")
    if not any("stack trace" in item.text for item in sharp):
        raise SystemExit("self-check missed throw ex")
    empty = csharp_findings("void Run() {\n  try { Work(); }\n  catch (Exception ex) { }\n}\n")
    if not any("empty catch" in item.text for item in empty):
        raise SystemExit("self-check missed an empty catch")
    safe = python_findings("def build(items=None):\n    return items or []\n")
    if safe:
        raise SystemExit("self-check flagged a safe default")
    lam = python_findings("f = lambda items=[]: items\n")
    if not any("lambda" in item.text for item in lam):
        raise SystemExit("self-check missed a lambda mutable default")
    used = python_signals("def used():\n    return 1\n\ndef run():\n    return used()\n\nrun()\n", 0)
    if used.wiring_hop != 0:
        raise SystemExit("self-check marked a called function as unwired")
    unused = python_signals("VALUE = 1\n\ndef unused():\n    return 2\n", 0)
    if unused.wiring_hop != 1 or unused.dead_setting != 1:
        raise SystemExit("self-check missed an unused function or unread constant")
    split = python_signals("N = 1\nN = 2\n", 0)
    if split.split_stores != 1:
        raise SystemExit("self-check missed a split store")
    nested = python_findings(
        "def run():\n    try:\n        work()\n    finally:\n        if ready:\n            return 1\n"
    )
    if nested is None or not any("finally" in item.text for item in nested):
        raise SystemExit("self-check missed a nested return in finally")
    defined = python_findings(
        "def run():\n    try:\n        work()\n    finally:\n        def inner():\n            return 1\n"
    )
    if defined is None or any("finally" in item.text for item in defined):
        raise SystemExit("self-check treated a nested function return as finally")
    broad = python_findings("def run():\n    try:\n        work()\n    except (Exception, BaseException):\n        pass\n")
    if broad is None or not any("does nothing" in item.text for item in broad):
        raise SystemExit("self-check missed a tuple of broad exceptions")
    dots = python_findings("def run():\n    try:\n        work()\n    except Exception:\n        ...\n")
    if dots is None or not any("does nothing" in item.text for item in dots):
        raise SystemExit("self-check missed an ellipsis that swallows an exception")
    literal = python_findings("def run():\n    try:\n        work()\n    except Exception:\n        'ignored'\n")
    if literal is None or not any("does nothing" in item.text for item in literal):
        raise SystemExit("self-check missed a literal that swallows an exception")
    if python_findings("def (\n") is not None:
        raise SystemExit("self-check treated a syntax error as a clean file")
    quoted = csharp_findings(
        'void Run() {\n  catch (Exception ex) when (flag == "}") { throw ex; }\n}\n'
    )
    if not any("stack trace" in item.text for item in quoted):
        raise SystemExit("self-check let a quoted brace hide throw ex")
    comment = csharp_findings("void Run() {\n  // catch (Exception ex) { throw ex; }\n  Work();\n}\n")
    if comment:
        raise SystemExit("self-check flagged a catch that is only a comment")
    blocked = csharp_findings("/*\ncatch (Exception ex) { throw ex; }\n*/\nvoid Run() {}\n")
    if blocked:
        raise SystemExit("self-check flagged a catch inside a block comment")
    quoted_body = csharp_findings(
        'void Run() {\n  catch (Exception ex) { var s = "/*"; Log(); var t = "*/"; throw ex; }\n}\n'
    )
    if not any("stack trace" in item.text for item in quoted_body):
        raise SystemExit("self-check let a string comment marker hide throw ex")
    if any("empty catch" in item.text for item in quoted_body):
        raise SystemExit("self-check called a catch with code empty")
    same_line = csharp_findings(
        "void Run() { try { Work(); } catch (Exception ex) { throw ex; } }\n"
    )
    if not any("stack trace" in item.text for item in same_line):
        raise SystemExit("self-check missed a same-line catch")
    fixes, reverted = parse_git_log(
        '\x1efix the bug\n"src/a.py"\n\x1eRevert "oops"\nsrc/{old => new}/b.py\n'
    )
    if fixes.get("src/a.py") != 1 or "src/new/b.py" not in reverted:
        raise SystemExit("self-check misread a quoted path or a rename")
    blank = empty_row("coleman", "coleman/ok.py")
    if blank["outcome"] != "empty" or set(blank["signals"].values()) != {0} or blank["weighted_sum"] != 0:
        raise SystemExit("self-check empty row was not all zeros")
    hidden = csharp_findings('void Run() {\n  var s = @"\n  catch (Exception ex) { }\n  ";\n  Work();\n}\n')
    if hidden:
        raise SystemExit("self-check flagged a catch inside a verbatim string")
    kept = csharp_findings(
        'void Run() {\n  catch (Exception ex) {\n    var s = @$"\n    }\n    ";\n    throw ex;\n  }\n}\n'
    )
    if not any("stack trace" in item.text for item in kept):
        raise SystemExit("self-check let a multiline interpolated string hide throw ex")
    semis = csharp_findings("void Run() {\n  try { Work(); }\n  catch (Exception ex) { ; ; }\n}\n")
    if not any("empty catch" in item.text for item in semis):
        raise SystemExit("self-check missed a semicolon-only catch")
    two = csharp_findings("void Run() { catch (A a) { } catch (B b) { throw b; } }\n")
    if not any("empty catch" in item.text for item in two) or not any("stack trace" in item.text for item in two):
        raise SystemExit("self-check missed one of two catches on the same line")
    borrowed = csharp_findings(
        "void Run() { catch { throw ex; } catch (Exception ex) { Log(); } }\n"
    )
    if any("stack trace" in item.text for item in borrowed):
        raise SystemExit("self-check borrowed the next catch variable")
    if _is_test_rel("src/testimony.py") or _is_test_rel("src/testing.py"):
        raise SystemExit("self-check treated a non-test filename as a test")
    if not _is_test_rel("tests/helper.py") or not _is_test_rel("src/FooTests.cs"):
        raise SystemExit("self-check missed a tests directory or a FooTests file")
    empty_subject, _reverted_empty = parse_git_log("\x1e\x1f\nfix.py\n")
    if empty_subject:
        raise SystemExit("self-check counted a path as a fix subject")
    marked, _reverted_marked = parse_git_log("\x1efix it\x1f\nsrc/a.py\n")
    if marked.get("src/a.py") != 1:
        raise SystemExit("self-check missed a fix path after the subject marker")
    bugs = [{"outcome": "review-failed"} for _ in range(398)]
    empties = [{"outcome": "empty"} for _ in range(200)]
    mixed = interleave_rows(bugs, empties)
    cut = int(len(mixed) * 0.7)
    if len(mixed) != 598:
        raise SystemExit("self-check interleave dropped a row")
    for part in (mixed[:cut], mixed[cut:]):
        kinds = {row["outcome"] for row in part}
        if kinds != {"review-failed", "empty"}:
            raise SystemExit("self-check interleave left a split with one class")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit rank-rows for static defects. Does not edit scanned repos.")
    parser.add_argument("--root", action="append", type=Path, default=None, help="Repo to scan. Repeatable. Default is the H drive set.")
    parser.add_argument("--out", type=Path, default=None, help="Write JSONL here. Default is stdout.")
    parser.add_argument(
        "--mix-target",
        type=int,
        default=MIX_TARGET,
        help="Mixed row count to aim for. Empty rows fill the gap under the bug rows.",
    )
    parser.add_argument("--self-check", action="store_true", help="Run the in-memory detector checks and exit.")
    args = parser.parse_args(argv)
    if args.self_check:
        self_check()
        print("self-check ok", file=sys.stderr)
        return 0
    roots = list(args.root) if args.root else list(DEFAULT_REPOS)
    rows: list[dict[str, object]] = []
    missing: list[str] = []
    present = [root for root in roots if root.is_dir()]
    missing.extend(str(root) for root in roots if not root.is_dir())
    if args.out is not None:
        destination = args.out.resolve()
        for root in present:
            try:
                destination.relative_to(root.resolve())
            except ValueError:
                continue
            print(f"refusing to write inside a scanned repo: {destination}", file=sys.stderr)
            return 2
    bug_rows: list[dict[str, object]] = []
    clean: list[tuple[str, str]] = []
    for root in present:
        found_rows, clean_paths = scan_repo(root)
        bug_rows.extend(found_rows)
        clean.extend((root.name, rel) for rel in clean_paths)
    # Half the target keeps a real negative class when defect rows already fill the target.
    need = max(0, args.mix_target - len(bug_rows), args.mix_target // 2)
    empty_rows = sample_empty(clean, need)
    rows = interleave_rows(bug_rows, empty_rows)
    text = "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows)
    if args.out is None:
        sys.stdout.write(text)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    by_repo: dict[str, int] = {}
    for row in rows:
        name = str(row["file"]).split("/", 1)[0]
        by_repo[name] = by_repo.get(name, 0) + 1
    bugs = sum(1 for row in rows if row["outcome"] == "review-failed")
    empties = sum(1 for row in rows if row["outcome"] == "empty")
    print(
        f"rows={len(rows)} bug_rows={bugs} empty_rows={empties} "
        f"repos_with_rows={len(by_repo)} missing={len(missing)}",
        file=sys.stderr,
    )
    for name in sorted(by_repo):
        print(f"  {by_repo[name]:5}  {name}", file=sys.stderr)
    for path in missing:
        print(f"  missing {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
