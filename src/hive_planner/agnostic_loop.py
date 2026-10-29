"""Pause-cycle work chooser — portable hive-loop-kit engine.

Install copies the kit (scripts, contract, lay-footnote skill) into a project.
Reward tables live in ``.hive/agnostic-loop/catalog.json`` so another tool can
replace them. State lives under ``.hive/agnostic-loop/``.
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOOP_DIR = Path(".hive") / "agnostic-loop"
COMMAND_PATH = Path(".cursor") / "commands" / "agnostic-loop.md"
RULE_PATH = Path(".cursor") / "rules" / "agnostic-loop.mdc"
KIT_SCRIPT = Path("scripts") / "agnostic_loop.py"
KIT_REMAP = Path("scripts") / "trajectory_remap.py"
KIT_CONTRACT = Path("scripts") / "trajectory-loop.md"
KIT_SKILL = Path("skills") / "lay-footnote" / "SKILL.md"
KIT_README = LOOP_DIR / "README.md"
CATALOG_NAME = "catalog.json"
CONTRACT_NAME = "loop.md"
SCRIPTS_FALLBACK = Path("scripts") / "agnostic-loop.md"

MAX_CYCLES = 30
PAUSE_SECONDS = 10
DISCOUNT = 0.85
JUMP_WEIGHT = 0.35
EMPTY_WEIGHT = 0.05
UCT_C = math.sqrt(2.0)

def _slots(prefix: str) -> tuple[str, ...]:
    return tuple(f"{prefix}.{index:02d}" for index in range(10))


def default_catalog_dict() -> dict[str, Any]:
    """Generic work kinds. Replace catalog.json for another tool or product."""
    tick = "Do only this hook's job. Then review and stop."
    return {
        "rewards": {
            "inspect": {
                "hooks": list(_slots("inspect")),
                "rule": f"Record what is known vs unknown on this hook. {tick}",
            },
            "fill": {
                "hooks": list(_slots("fill")),
                "rule": f"Add one missing fact for this hook. Note where it came from. {tick}",
            },
            "extend": {
                "hooks": list(_slots("fill")),
                "rule": f"Grow one already-filled item on this hook by one step. {tick}",
            },
            "method": {
                "hooks": list(_slots("fill")),
                "rule": f"Add one process step for this hook. {tick}",
            },
            "infer": {
                "hooks": list(_slots("infer")),
                "rule": f"Check one inference on this hook. Record confidence. {tick}",
            },
            "script": {
                "hooks": list(_slots("script")),
                "rule": f"Write one piece of a repeatable process for this hook. Do not execute it. {tick}",
            },
            "goal-infer": {
                "hooks": list(_slots("goal")),
                "rule": f"Infer one missing choice from the stated goal. Record the reasoning. {tick}",
            },
            "goal-extend": {
                "hooks": list(_slots("goal")),
                "rule": f"Evaluate the choice on this hook, then extend it by one step. {tick}",
            },
        },
        "refill": {
            "inspect": {"fill": 1, "infer": 1},
            "fill": {"extend": 1},
            "extend": {"method": 1, "goal-infer": 1},
            "method": {},
            "infer": {"goal-infer": 1, "fill": 1},
            "goal-infer": {"goal-extend": 1, "script": 1},
            "goal-extend": {"method": 1},
            "script": {},
        },
        "chain": {
            "inspect": ["inspect", "fill", "infer"],
            "fill": ["fill", "extend", "infer"],
            "extend": ["extend", "method", "goal-infer"],
            "method": ["method", "extend", "script"],
            "infer": ["infer", "goal-infer", "fill"],
            "goal-infer": ["goal-infer", "goal-extend", "script"],
            "goal-extend": ["goal-extend", "method", "script"],
            "script": ["script", "infer", "goal-extend"],
        },
    }


@dataclass
class LoopCatalog:
    rewards: dict[str, tuple[tuple[str, ...], str]]
    refill: dict[str, dict[str, int]]
    chain: dict[str, frozenset[str]]

    def names(self) -> tuple[str, ...]:
        return tuple(self.rewards)


def parse_catalog(data: dict[str, Any]) -> LoopCatalog:
    raw_rewards = data.get("rewards") or {}
    if not isinstance(raw_rewards, dict):
        raw_rewards = {}
    rewards: dict[str, tuple[tuple[str, ...], str]] = {}
    for name, body in raw_rewards.items():
        if not isinstance(body, dict):
            continue
        hooks_raw = body.get("hooks") or ()
        if not isinstance(hooks_raw, (list, tuple)):
            continue
        hooks = tuple(str(h) for h in hooks_raw if str(h).strip())
        rule = str(body.get("rule") or "Do only this hook's job. Then review and stop.")
        if hooks:
            rewards[str(name)] = (hooks, rule)
    refill: dict[str, dict[str, int]] = {}
    raw_refill = data.get("refill") or {}
    if not isinstance(raw_refill, dict):
        raw_refill = {}
    for name, kids in raw_refill.items():
        if name not in rewards or not isinstance(kids, dict):
            continue
        parsed_kids: dict[str, int] = {}
        for child, amount in kids.items():
            if str(child) not in rewards:
                continue
            try:
                value = int(amount)
            except (TypeError, ValueError):
                continue
            if value > 0:
                parsed_kids[str(child)] = value
        refill[str(name)] = parsed_kids
    for name in rewards:
        refill.setdefault(name, {})
    chain: dict[str, frozenset[str]] = {}
    raw_chain = data.get("chain") or {}
    if not isinstance(raw_chain, dict):
        raw_chain = {}
    for name, members in raw_chain.items():
        if name not in rewards:
            continue
        if isinstance(members, str):
            members = [members]
        if not isinstance(members, (list, tuple, set, frozenset)):
            continue
        chain[str(name)] = frozenset(str(m) for m in members if str(m) in rewards) or frozenset({str(name)})
    for name in rewards:
        chain.setdefault(name, frozenset({name}))
    return LoopCatalog(rewards=rewards, refill=refill, chain=chain)


def default_catalog() -> LoopCatalog:
    return parse_catalog(default_catalog_dict())


def _catalog_path(root: Path) -> Path:
    return _loop_dir(root) / CATALOG_NAME


def try_load_catalog(root: Path | None = None) -> tuple[LoopCatalog, str | None]:
    if root is None:
        return default_catalog(), None
    path = _catalog_path(root)
    if not path.is_file():
        return default_catalog(), None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return default_catalog(), "catalog.json could not be read"
    except json.JSONDecodeError:
        return default_catalog(), "catalog.json is not valid JSON"
    if not isinstance(data, dict):
        return default_catalog(), "catalog.json must be a JSON object"
    try:
        parsed = parse_catalog(data)
    except (TypeError, ValueError, AttributeError, KeyError):
        return default_catalog(), "catalog.json could not be parsed"
    if not parsed.rewards:
        return default_catalog(), "catalog.json has no rewards"
    return parsed, None


def load_catalog(root: Path | None = None) -> LoopCatalog:
    catalog, _err = try_load_catalog(root)
    return catalog


def catalog_problem(root: Path | None) -> str | None:
    _catalog, err = try_load_catalog(root)
    return err


def reward_tables(root: Path | None = None) -> dict[str, tuple[tuple[str, ...], str]]:
    """Installed or default reward tables."""
    return load_catalog(root).rewards


def hive_catalog(root: Path | None = None) -> dict[str, tuple[tuple[str, ...], str]]:
    return reward_tables(root)


class AgnosticLoopError(Exception):
    """Chooser or cycle gate failed."""

    def __init__(self, message: str, *, fields: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.fields = fields or {}


def rewards(root: Path | None = None) -> tuple[str, ...]:
    return load_catalog(root).names()


def _loop_dir(root: Path) -> Path:
    return root.resolve() / LOOP_DIR


def _state_path(root: Path) -> Path:
    return _loop_dir(root) / "state.json"


def _review_dir(root: Path) -> Path:
    return _loop_dir(root) / "reviews"


def _policy_path(root: Path) -> Path:
    return _loop_dir(root) / "policy.json"


def _fresh_state(root: Path) -> dict[str, Any]:
    catalog = load_catalog(root)
    first = catalog.names()[0]
    return {
        "completed": 0,
        "max_cycles": MAX_CYCLES,
        "status": "paused",
        "hook_index": 0,
        "hook": catalog.rewards[first][0][0],
        "reward": first,
    }


def _load_state(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        return _fresh_state(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return _fresh_state(root)
    if not isinstance(data, dict):
        return _fresh_state(root)
    try:
        data["completed"] = int(data.get("completed", 0) or 0)
        data["max_cycles"] = int(data.get("max_cycles") or MAX_CYCLES)
        data["hook_index"] = int(data.get("hook_index", 0) or 0)
    except (TypeError, ValueError):
        return _fresh_state(root)
    if data["max_cycles"] < 1:
        data["max_cycles"] = MAX_CYCLES
    if data["completed"] < 0:
        data["completed"] = 0
    return data


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(data, indent=2) + "\n")


def _save_state(root: Path, state: dict[str, Any]) -> None:
    _write_json(_state_path(root), state)


def _limit(state: dict[str, Any]) -> int:
    return int(state.get("max_cycles") or MAX_CYCLES)


def _reward(state: dict[str, Any], catalog: LoopCatalog | None = None) -> str:
    catalog = catalog or default_catalog()
    reward = state.get("reward")
    if reward in catalog.rewards:
        return str(reward)
    return catalog.names()[0]


def _hooks(state: dict[str, Any], catalog: LoopCatalog) -> tuple[str, ...]:
    return catalog.rewards[_reward(state, catalog)][0]


def _rule(state: dict[str, Any], catalog: LoopCatalog) -> str:
    return catalog.rewards[_reward(state, catalog)][1]


def _payload(ok: bool, **fields: Any) -> dict[str, Any]:
    data = {"ok": ok, **fields}
    return data


def _catalog_refuse(root: Path, action: str) -> tuple[dict[str, Any], int] | None:
    err = catalog_problem(root)
    if not err:
        return None
    return _payload(False, action=action, blocked_reason=err), 3


def arm(root: Path, reward: str, cycles: int) -> tuple[dict[str, Any], int]:
    refused = _catalog_refuse(root, "arm")
    if refused:
        return refused
    catalog = load_catalog(root)
    if reward not in catalog.rewards:
        return _payload(False, action="arm", blocked_reason=f"unknown reward {reward}"), 3
    if isinstance(cycles, bool) or not isinstance(cycles, int) or cycles < 1:
        return _payload(False, action="arm", blocked_reason="cycles must be a positive int"), 3
    state = _load_state(root)
    if state.get("status") == "running":
        return (
            _payload(
                False,
                action="arm",
                blocked_reason="already open — review first",
                hook=state.get("hook"),
                completed=state.get("completed"),
            ),
            3,
        )
    hooks, rule = catalog.rewards[reward]
    state.pop("redirect", None)
    state["reward"] = reward
    state["completed"] = int(state.get("completed", 0))
    state["max_cycles"] = state["completed"] + cycles
    state["hook_index"] = 0
    state["hook"] = hooks[0]
    state["status"] = "paused"
    _save_state(root, state)
    return (
        _payload(
            True,
            action="arm",
            reward=reward,
            completed=state["completed"],
            max_cycles=state["max_cycles"],
            hook=state["hook"],
            pause_seconds=PAUSE_SECONDS,
            rule=rule,
        ),
        0,
    )


def begin(root: Path) -> tuple[dict[str, Any], int]:
    refused = _catalog_refuse(root, "begin")
    if refused:
        return refused
    catalog = load_catalog(root)
    state = _load_state(root)
    if state.get("completed", 0) >= _limit(state):
        return (
            _payload(
                False,
                action="begin",
                blocked_reason=f"completed {_limit(state)}",
            ),
            2,
        )
    if state.get("status") == "running":
        return (
            _payload(
                False,
                action="begin",
                blocked_reason="already open — review first",
                hook=state.get("hook"),
                completed=state.get("completed"),
            ),
            3,
        )
    hooks = _hooks(state, catalog)
    redirect = state.pop("redirect", None)
    if redirect in hooks:
        state["hook_index"] = hooks.index(redirect)
    state["status"] = "running"
    state["hook"] = hooks[state.get("hook_index", 0) % len(hooks)]
    state["opened_at"] = datetime.now(timezone.utc).isoformat()
    _save_state(root, state)
    return (
        _payload(
            True,
            action="begin",
            cycle=state["completed"] + 1,
            max_cycles=_limit(state),
            pause_seconds=PAUSE_SECONDS,
            hook=state["hook"],
            rule=_rule(state, catalog),
            reward=_reward(state, catalog),
        ),
        0,
    )


def review(root: Path, note: str) -> tuple[dict[str, Any], int]:
    refused = _catalog_refuse(root, "review")
    if refused:
        return refused
    catalog = load_catalog(root)
    state = _load_state(root)
    if state.get("status") != "running":
        return _payload(False, action="review", blocked_reason="nothing is open — begin first"), 3
    cycle = int(state.get("completed", 0)) + 1
    folder = _review_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"cycle-{cycle:03d}.md"
    path.write_text(
        "\n".join(
            [
                f"# Cycle {cycle} of {_limit(state)}",
                "",
                f"Reward: `{_reward(state, catalog)}`",
                f"Hook: `{state.get('hook')}`",
                "",
                "Review:",
                (note or "").strip() or "(empty)",
                "",
                "Pause. The next tick starts from the following hook.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    hooks = _hooks(state, catalog)
    nxt = (int(state.get("hook_index", 0)) + 1) % len(hooks)
    state["completed"] = cycle
    state["hook_index"] = nxt
    state["hook"] = hooks[nxt]
    state["status"] = "paused"
    stored = path.relative_to(root.resolve()).as_posix()
    state["last_review"] = stored
    _save_state(root, state)
    payload = _payload(
        True,
        action="pause",
        completed=cycle,
        review=stored,
        next_hook=state["hook"] if cycle < _limit(state) else None,
        pause_seconds=PAUSE_SECONDS,
    )
    if cycle >= _limit(state):
        payload["blocked_reason"] = "sequence complete"
        return payload, 2
    return payload, 0


def _fresh(names: tuple[str, ...]) -> dict[str, Any]:
    return {
        "arms": {name: {"alpha": 1.0, "beta": 1.0} for name in names},
        "last_reward": None,
        "observations": 0,
    }


def load_policy(root: Path, names: tuple[str, ...] | None = None) -> dict[str, Any]:
    names = names or rewards(root)
    path = _policy_path(root)
    if not path.is_file():
        return _fresh(names)
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return _fresh(names)
    if not isinstance(policy, dict):
        return _fresh(names)
    arms = policy.setdefault("arms", {})
    if not isinstance(arms, dict):
        arms = {}
        policy["arms"] = arms
    for name in names:
        raw = arms.get(name)
        if not isinstance(raw, dict):
            raw = {}
        try:
            alpha = float(raw.get("alpha", 1.0) or 1.0)
            beta = float(raw.get("beta", 1.0) or 1.0)
        except (TypeError, ValueError):
            alpha, beta = 1.0, 1.0
        if alpha <= 0:
            alpha = 1.0
        if beta <= 0:
            beta = 1.0
        arms[name] = {"alpha": alpha, "beta": beta}
    try:
        policy["observations"] = int(policy.get("observations", 0) or 0)
    except (TypeError, ValueError):
        policy["observations"] = 0
    return policy


def save_policy(root: Path, policy: dict[str, Any]) -> None:
    _write_json(_policy_path(root), policy)


def _mean(arm: dict[str, float]) -> float:
    return arm["alpha"] / (arm["alpha"] + arm["beta"])


def parse_open(text: str | None, names: tuple[str, ...]) -> dict[str, int] | None:
    if text is None:
        return {name: 1 for name in names}
    counts = {name: 0 for name in names}
    if text.strip() == "":
        return counts
    seen = False
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        seen = True
        if "=" not in part:
            return None
        name, raw = part.split("=", 1)
        name = name.strip()
        if name not in counts:
            return None
        try:
            value = int(raw.strip())
        except ValueError:
            return None
        if value < 0:
            return None
        counts[name] = value
    if not seen:
        return None
    return counts


def expected_step(
    opens: dict[str, int], reward: str, arms: dict, refill: dict[str, dict[str, int]]
) -> tuple[dict[str, int], float]:
    nxt = dict(opens)
    if nxt.get(reward, 0) <= 0:
        return nxt, 0.0
    nxt[reward] -= 1
    for child, amount in refill.get(reward, {}).items():
        nxt[child] = nxt.get(child, 0) + amount
    return nxt, _mean(arms[reward])


def stochastic_step(
    opens: dict[str, int], reward: str, arms: dict, rng: random.Random, refill: dict[str, dict[str, int]]
):
    nxt = dict(opens)
    if nxt.get(reward, 0) <= 0:
        return nxt, 0.0
    theta = rng.betavariate(arms[reward]["alpha"], arms[reward]["beta"])
    if rng.random() > theta:
        return nxt, 0.0
    nxt[reward] -= 1
    for child, amount in refill.get(reward, {}).items():
        nxt[child] = nxt.get(child, 0) + amount
    return nxt, 1.0


def thompson_pick(
    opens: dict[str, int],
    last: str | None,
    arms: dict,
    rng: random.Random,
    chain: dict[str, frozenset[str]],
) -> str:
    best = None
    best_draw = -1.0
    for reward, arm in arms.items():
        theta = rng.betavariate(arm["alpha"], arm["beta"])
        if opens.get(reward, 0) <= 0:
            theta *= EMPTY_WEIGHT
        if last and reward not in chain.get(last, frozenset()):
            theta *= JUMP_WEIGHT
        if theta > best_draw:
            best = reward
            best_draw = theta
    return str(best)


def _rollout(opens, last, arms, depth, horizon, rng, refill, chain) -> float:
    total = 0.0
    discount = 1.0
    for _ in range(horizon - depth):
        reward = thompson_pick(opens, last, arms, rng, chain)
        opens, gain = stochastic_step(opens, reward, arms, rng, refill)
        total += discount * gain
        discount *= DISCOUNT
        last = reward
    return total


def _candidates(opens: dict[str, int], names: list[str]) -> list[str]:
    open_names = [name for name in names if opens.get(name, 0) > 0]
    return open_names or list(names)


class _Node:
    def __init__(self, opens, last, depth, action, edge_gain, parent):
        self.opens = opens
        self.last = last
        self.depth = depth
        self.action = action
        self.edge_gain = edge_gain
        self.parent = parent
        self.visits = 0
        self.value = 0.0
        self.children: dict[str, _Node] = {}
        self.untried: list[str] = []


def _uct(parent: _Node, child: _Node) -> float:
    if child.visits == 0 or parent.visits < 1:
        return math.inf
    exploit = child.value / child.visits
    explore = UCT_C * math.sqrt(math.log(parent.visits) / child.visits)
    return exploit + explore


def search(
    opens: dict[str, int],
    last: str | None,
    arms: dict,
    sims: int,
    horizon: int,
    rng: random.Random,
    refill: dict[str, dict[str, int]],
    chain: dict[str, frozenset[str]],
) -> _Node:
    names = list(arms)
    root = _Node(dict(opens), last, 0, None, None, None)
    root.untried = _candidates(root.opens, names)
    for _ in range(sims):
        node = root
        while not node.untried and node.children and node.depth < horizon:
            node = max(node.children.values(), key=lambda child: _uct(node, child))
        if node.depth < horizon and node.untried:
            action = node.untried.pop(rng.randrange(len(node.untried)))
            child_opens, gain = expected_step(node.opens, action, arms, refill)
            child = _Node(child_opens, action, node.depth + 1, action, gain, node)
            child.untried = _candidates(child_opens, names) if child.depth < horizon else []
            node.children[action] = child
            node = child
        tail = _rollout(dict(node.opens), node.last, arms, node.depth, horizon, rng, refill, chain)
        remaining = tail
        current = node
        while current is not None:
            if current.edge_gain is not None:
                remaining = current.edge_gain + DISCOUNT * remaining
            current.visits += 1
            current.value += remaining
            current = current.parent
    return root


def _score(child: _Node) -> tuple[float, int]:
    if child.visits == 0:
        return (-1.0, 0)
    return (round(child.value / child.visits, 6), child.visits)


def _best_child(node: _Node, arms: dict, rng: random.Random) -> _Node:
    top = max(_score(child) for child in node.children.values())
    tied = [child for child in node.children.values() if _score(child) == top]
    if len(tied) == 1:
        return tied[0]
    return max(tied, key=lambda child: rng.betavariate(arms[child.action]["alpha"], arms[child.action]["beta"]))


def principal_variation(root: _Node, arms: dict, rng: random.Random) -> list[str]:
    sequence = []
    node = root
    while node.children:
        node = _best_child(node, arms, rng)
        sequence.append(node.action)
    return sequence


def observe(root: Path, reward: str, hit: bool, names: tuple[str, ...] | None = None) -> tuple[dict[str, Any], int]:
    refused = _catalog_refuse(root, "observe")
    if refused:
        return refused
    names = names or rewards(root)
    if reward not in names:
        return _payload(False, action="observe", blocked_reason=f"unknown reward {reward}"), 3
    policy = load_policy(root, names)
    arm = policy["arms"][reward]
    if hit:
        arm["alpha"] += 1.0
    else:
        arm["beta"] += 1.0
    policy["last_reward"] = reward
    policy["observations"] = int(policy.get("observations", 0)) + 1
    save_policy(root, policy)
    return (
        _payload(
            True,
            action="observe",
            reward=reward,
            hit=hit,
            arm=arm,
            observations=policy["observations"],
        ),
        0,
    )


def choose(
    root: Path,
    opens: dict[str, int],
    *,
    sims: int = 64,
    horizon: int = 4,
    seed: int | None = None,
    do_arm: bool = False,
    cycles: int = 1,
    names: tuple[str, ...] | None = None,
) -> tuple[dict[str, Any], int]:
    if sims < 1 or horizon < 1 or cycles < 1:
        return _payload(False, action="choose", blocked_reason="sims, horizon, and cycles must be positive"), 3
    refused = _catalog_refuse(root, "choose")
    if refused:
        return refused
    catalog = load_catalog(root)
    names = names or catalog.names()
    policy = load_policy(root, names)
    arms = {name: policy["arms"][name] for name in names}
    rng = random.Random(seed)
    tree = search(
        opens,
        policy.get("last_reward"),
        arms,
        sims,
        horizon,
        rng,
        catalog.refill,
        catalog.chain,
    )
    if not tree.children:
        return _payload(False, action="choose", blocked_reason="no reward to choose"), 3
    plan = principal_variation(tree, arms, rng)
    reward = plan[0]
    child = tree.children[reward]
    payload = _payload(
        True,
        action="choose",
        reward=reward,
        plan=plan,
        visits=child.visits,
        value=round(child.value / child.visits, 4) if child.visits else 0.0,
        sims=sims,
        horizon=horizon,
        last_reward=policy.get("last_reward"),
        thompson={name: round(_mean(arms[name]), 4) for name in names},
        method="mcts-uct",
        rollout="thompson",
        tie_break="thompson",
        pause_seconds=PAUSE_SECONDS,
    )
    if not do_arm:
        return payload, 0
    armed, code = arm(root, reward, cycles)
    if code != 0:
        return armed, code
    policy["last_reward"] = reward
    save_policy(root, policy)
    payload["armed_cycles"] = cycles
    payload["arm"] = armed
    return payload, 0


def status(root: Path) -> dict[str, Any]:
    refused = _catalog_refuse(root, "status")
    if refused:
        return refused[0]
    catalog = load_catalog(root)
    names = catalog.names()
    state = _load_state(root)
    policy = load_policy(root, names)
    policy["chain"] = {key: sorted(value) for key, value in catalog.chain.items()}
    return _payload(
        True,
        action="status",
        **{k: v for k, v in state.items() if k != "ok"},
        pause_seconds=PAUSE_SECONDS,
        policy=policy,
        rewards=list(names),
    )


def is_agnostic_loop_request(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    if is_bug_or_impl_phrase(lowered):
        return False
    loop_named = (
        "agnostic loop" in lowered
        or "hive loop kit" in lowered
        or "/agnostic-loop" in lowered
    )
    about = re.search(
        r"\b(what is|what's|what are|where is|how do|how does|is it|does it|can i)\b",
        lowered,
    ) or (
        loop_named and re.search(r"\b(what|where|how|whether)\b", lowered)
    ) or (
        loop_named
        and re.search(r"\b(is|whether)\b.{0,80}\b(enabled|installed)\b", lowered)
    )
    run_phrases = (
        "run the agnostic loop",
        "start the agnostic loop",
        "/agnostic-loop",
    )
    if about and not any(p in lowered for p in run_phrases):
        return False
    phrases = [
        "agnostic loop",
        "hive loop kit",
        "run the agnostic loop",
        "start the agnostic loop",
        "/agnostic-loop",
    ]
    return any(p in lowered for p in phrases)


def is_bug_or_impl_phrase(lowered: str) -> bool:
    if "implementation loop" in lowered or "implement the spec" in lowered:
        return True
    if re.search(r"\bbu(?:g|ng|n)?\s*-?\s*hun", lowered):
        return True
    return False


def render_kit_readme() -> str:
    return """# Hive loop kit

Copy is already in this project (installed by Hive Planner). Python 3.10 or newer. No third-party packages.

The tool root is the parent of `scripts/`. State is `.hive/agnostic-loop/`. Reward names, hook ids, and tick rules are `.hive/agnostic-loop/catalog.json`. Replace that file for another tool. Keep `arm`, `begin`, `review`, `choose`, and `observe`.

## What to run

From the tool root:

```
py -3.11 scripts/agnostic_loop.py rewards
py -3.11 scripts/agnostic_loop.py choose --open inspect=4,fill=1
py -3.11 scripts/agnostic_loop.py observe --reward fill --hit
py -3.11 scripts/agnostic_loop.py choose --arm --cycles 1
py -3.11 scripts/agnostic_loop.py begin
py -3.11 scripts/agnostic_loop.py review --note "what this tick did"
py -3.11 scripts/agnostic_loop.py status
```

`scripts/trajectory_remap.py` starts the same script. One tick opens one hook, then pauses. Exit 2 means the cycle cap is reached.

Hive Planner CLI is the same gates: `py -3.11 -m hive_planner agnostic-loop ...`

## Lay footnote

After the rest of a reply, follow `skills/lay-footnote/SKILL.md`.
"""


def render_kit_entry() -> str:
    """Install the same engine as a portable scripts/agnostic_loop.py."""
    candidates = [Path(__file__)]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "hive_planner" / "agnostic_loop.py")
    for source in candidates:
        if source.is_file():
            return source.read_text(encoding="utf-8")
    raise OSError(
        "Agnostic loop script is not in this Hive Planner build "
        f"({candidates[0]}). Rebuild the portable app so that file is packaged."
    )


def render_kit_remap() -> str:
    return '''"""Start the unified loop script.

Behavior lives in ``scripts/agnostic_loop.py``. This path remains so older
commands keep working.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_TARGET = Path(__file__).with_name("agnostic_loop.py")

if __name__ == "__main__":
    sys.argv[0] = str(_TARGET)
    raise SystemExit(runpy.run_path(str(_TARGET), run_name="__main__"))
'''


def render_kit_skill() -> str:
    return """---
name: lay-footnote
description: After the rest of a reply is done, add one lay footnote that restates the complex details for a non-expert.
---

# Lay footnote

Run this last. Continual learning, spec edits, tool work, and the technical answer finish first.

## Footnote

End the user-facing reply with one short paragraph in plain language.

- Restate what was done or decided. Use everyday words for the jargon in that reply.
- Keep it to one paragraph, placed after the rest of the answer.
- When the turn requires an exact sentence, leave that sentence unchanged and put the footnote after it.
- Do not write the footnote into `AGENTS.md`, the spec, or a journal. The durable memory is the reply convention, not the footnote text.
"""


def render_cursor_command() -> str:
    return """---
description: Run the hive-loop-kit agnostic loop (pause-cycle work chooser)
---

# Agnostic loop

Read `scripts/trajectory-loop.md` and follow it.

Call the kit script or the Python coordinator. Do not edit `.hive/agnostic-loop/state.json` by hand.

```text
py -3.11 scripts/agnostic_loop.py rewards
py -3.11 scripts/agnostic_loop.py choose --open inspect=1,fill=1 --arm --cycles 1
py -3.11 scripts/agnostic_loop.py begin
py -3.11 scripts/agnostic_loop.py review --note "what this tick did"
py -3.11 scripts/agnostic_loop.py observe --reward fill --hit
py -3.11 scripts/agnostic_loop.py status
```

Same gates: `py -3.11 -m hive_planner agnostic-loop ...`

One tick opens one hook, then pauses (~10 seconds). Exit 2 means the cycle cap is reached.

Replace `.hive/agnostic-loop/catalog.json` to change rewards and hooks. This is not the implementation loop and not a bug hunt. Do not merge, push to trunk, force-push, or deploy.
"""


def render_cursor_rule() -> str:
    return """---
description: Start the agnostic loop when the user asks for the hive loop kit
alwaysApply: true
---

When the user asks to run the agnostic loop — including "agnostic loop", "hive loop kit", "run the agnostic loop", "start the agnostic loop", `/agnostic-loop` — read `.cursor/commands/agnostic-loop.md` and execute it in this turn. If that file is missing, report that the loop is not installed and stop.

A question about the loop is not a start signal. An implementation-loop or bug-hunt phrase is not a start signal.
"""


def render_loop_contract() -> str:
    return """# Trajectory loop contract

Shared procedure for every reward in `scripts/agnostic_loop.py`. `scripts/trajectory_remap.py` starts that same script. The reward-specific job is in the command that pointed here. Reward tables are `.hive/agnostic-loop/catalog.json`.

## Start

1. Read `.hive/agnostic-loop/state.json`.
2. If `status` is `running`, review that open hook under its current rule and stop the turn. Do not arm and do not begin a second cycle.
3. If `status` is `paused`, `reward` is already the requested reward, and `completed` is below `max_cycles`, do not arm. Begin the next hook.
4. Otherwise arm a new sequence, then begin its first hook in the same turn:

```
py -3.11 scripts/agnostic_loop.py arm --reward REWARD --cycles 30
py -3.11 scripts/agnostic_loop.py begin
```

`arm` refuses a running cycle. It sets the cap to the current completed count plus 30 and returns the cursor to the first hook of that reward.

## One tick

Do only the open hook's job. Then:

```
py -3.11 scripts/agnostic_loop.py review --note "..."
```

Exit 2 and sequence complete mean the cap is reached. That is success. `next_hook` is null. Do not arm another sequence and do not start a sleeper.

If several wake notifications arrive in one turn, run one cycle. Ignore a late tick from a sleeper that has already been replaced.

## Wake

After review, if the sleeper has exited and `completed` is below `max_cycles`, start the remaining waits. Do not start a second sleeper while one is running.

```
1..REMAINING | ForEach-Object { Start-Sleep -Seconds 10; Write-Output "AGENT_LOOP_TICK_REWARD $_" }
```

`REMAINING` is `max_cycles - completed`. Notify on `AGENT_LOOP_TICK_REWARD`, debounce 10000, and do not wait for the sleeper to finish.

## Bounds

Do not commit unless the same message asked for a commit. End the user-facing reply with a short plain-language footnote (`skills/lay-footnote/SKILL.md`). Do not write that footnote into AGENTS.md.
"""


def _write_if_changed(path: Path, text: str, root: Path, written: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    if path.is_file():
        try:
            previous = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            previous = None
    if previous == text:
        return
    _write_text_atomic(path, text)
    written.append(path.relative_to(root).as_posix())


def install_agnostic_loop(root: Path) -> list[str]:
    root = root.resolve()
    written: list[str] = []
    catalog_path = root / LOOP_DIR / CATALOG_NAME
    if not catalog_path.is_file() or catalog_problem(root):
        _write_json(catalog_path, default_catalog_dict())
        written.append(catalog_path.relative_to(root).as_posix())
    _write_if_changed(root / COMMAND_PATH, render_cursor_command(), root, written)
    _write_if_changed(root / RULE_PATH, render_cursor_rule(), root, written)
    contract = render_loop_contract()
    _write_if_changed(root / LOOP_DIR / CONTRACT_NAME, contract, root, written)
    _write_if_changed(root / KIT_CONTRACT, contract, root, written)
    _write_if_changed(root / KIT_SCRIPT, render_kit_entry(), root, written)
    _write_if_changed(root / KIT_REMAP, render_kit_remap(), root, written)
    _write_if_changed(root / KIT_SKILL, render_kit_skill(), root, written)
    _write_if_changed(root / KIT_README, render_kit_readme(), root, written)
    _write_if_changed(root / SCRIPTS_FALLBACK, render_cursor_command(), root, written)
    return written


def missing_agnostic_loop_artifacts(root: Path) -> list[str]:
    root = root.resolve()
    missing = []
    for rel in (
        COMMAND_PATH,
        RULE_PATH,
        LOOP_DIR / CONTRACT_NAME,
        LOOP_DIR / CATALOG_NAME,
        KIT_SCRIPT,
        KIT_REMAP,
        KIT_CONTRACT,
        KIT_SKILL,
        KIT_README,
        SCRIPTS_FALLBACK,
    ):
        if not (root / rel).is_file():
            missing.append(rel.as_posix())
    return missing


def preview_agent_prompt() -> str:
    return render_cursor_command()


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    import argparse

    root = (root or Path.cwd()).resolve()
    parser = argparse.ArgumentParser(description="Arm, run, and choose kit rewards.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("rewards")
    sub.add_parser("status")
    armed = sub.add_parser("arm")
    armed.add_argument("--reward", required=True)
    armed.add_argument("--cycles", type=int, default=MAX_CYCLES)
    sub.add_parser("begin")
    rev = sub.add_parser("review")
    rev.add_argument("--note", required=True)
    seen = sub.add_parser("observe")
    seen.add_argument("--reward", required=True)
    flag = seen.add_mutually_exclusive_group(required=True)
    flag.add_argument("--hit", action="store_true")
    flag.add_argument("--miss", action="store_true")
    for name in ("choose", "plan"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--open", default=None)
        cmd.add_argument("--sims", type=int, default=64)
        cmd.add_argument("--horizon", type=int, default=4)
        cmd.add_argument("--seed", type=int, default=None)
        cmd.add_argument("--arm", action="store_true")
        cmd.add_argument("--cycles", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        err = catalog_problem(root)
        if err and args.cmd in {"rewards", "status", "arm", "begin", "review", "observe", "choose", "plan"}:
            print(json.dumps({"ok": False, "action": args.cmd, "blocked_reason": err}))
            return 3
        names = rewards(root)
        if args.cmd == "rewards":
            print(json.dumps(sorted(names)))
            return 0
        if args.cmd == "arm":
            payload, code = arm(root, args.reward, args.cycles)
            print(json.dumps(payload))
            return code
        if args.cmd == "begin":
            payload, code = begin(root)
            print(json.dumps(payload))
            return code
        if args.cmd == "review":
            payload, code = review(root, args.note)
            print(json.dumps(payload))
            return code
        if args.cmd == "status":
            report = status(root)
            print(json.dumps(report))
            return 0 if report.get("ok") is not False else 3
        if args.cmd == "observe":
            payload, code = observe(root, args.reward, args.hit, names)
            print(json.dumps(payload))
            return code
        opens = parse_open(args.open, names)
        if opens is None:
            print(json.dumps({"ok": False, "action": "choose", "blocked_reason": "invalid --open"}))
            return 3
        payload, code = choose(
            root,
            opens,
            sims=args.sims,
            horizon=args.horizon,
            seed=args.seed,
            do_arm=args.arm,
            cycles=args.cycles,
            names=names,
        )
        print(json.dumps(payload))
        return code
    except OSError as exc:
        print(json.dumps({"ok": False, "action": args.cmd, "blocked_reason": str(exc)}))
        return 1


if __name__ == "__main__":
    here = Path(__file__).resolve()
    kit_root = here.parents[1] if here.parent.name == "scripts" else Path.cwd()
    raise SystemExit(main(None, root=kit_root))


@dataclass
class AgnosticLoopInstall:
    root: Path
    files_written: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "root": str(self.root),
            "files_written": list(self.files_written),
            "command": COMMAND_PATH.as_posix(),
            "rule": RULE_PATH.as_posix(),
        }
