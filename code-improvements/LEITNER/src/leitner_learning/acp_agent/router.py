"""Catalyst-backed turn planner for the ACP agent."""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from leitner_learning.inference.catalyst import InferenceCatalyst
from leitner_learning.inference.dream_transformers import create_dream_backend
from leitner_learning.inference.models import CatalystReward, InferenceArm, TaskClass
from leitner_learning.inference.qwen_backend import create_qwen_backend


SYSTEM_HINT = """You are the Leitner DualPath ACP agent inside Zed (Cursor-like coding agent).
Workspace rules: respect AGENTS.md; DualPath-local Host Fabric; never assume GPUDirect RDMA;
Dream/dLLM stays whole on primary GPU.

You may reply with plain text, OR emit ONE JSON action object:
  {"action":"read_file","path":"absolute or repo-relative path"}
  {"action":"write_file","path":"...","content":"..."}
  {"action":"shell","command":"py","args":["-3.11","-c","print(1)"]}
  {"action":"final","text":"answer to the user"}

Prefer read_file before editing. For flashcard refine tasks prefer Dream path.
Default structured extract uses Qwen. Keep answers concise.
"""


def classify_task(user_text: str) -> TaskClass:
    """Map user text → catalyst task class.

    Extract keywords use word boundaries so 'cardinal' / 'jsonl' do not
    force flashcard extract mode.
    """
    import re

    t = user_text.lower()
    if re.search(r"\b(hints?|short\s+hints?|one-liners?)\b", t):
        return TaskClass.SHORT_HINT
    if re.search(r"\b(refine|reword|dream|dllm|wording)\b", t):
        return TaskClass.WORDING_REFINE
    if re.search(r"\b(extract|flashcards?|flash\s*cards?)\b", t):
        return TaskClass.JSON_EXTRACT
    if re.search(r"\bjson\b", t) and re.search(r"\b(card|cards|extract|flash)\b", t):
        return TaskClass.JSON_EXTRACT
    # Default ACP chat: Qwen AR. Dream-7B denoise on the T10 is ~0.85s/step —
    # keep Dream for refine/hint only.
    return TaskClass.AGENT_CHAT


@dataclass
class TurnRouter:
    catalyst: InferenceCatalyst
    backend_kind: str = field(default_factory=lambda: os.environ.get("LEITNER_ACP_BACKEND", "stub"))
    preferred_gpu: int = 1
    repo_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[3])
    _qwen: Any = field(default=None, repr=False)
    _dream: Any = field(default=None, repr=False)
    # Serialize create/load so initialize warm_dream cannot double-create backends.
    _backend_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    # Serialize GPU/HTTP generate separately so a timed-out turn does not hold
    # the create-lock forever while torch keeps loading in a cancelled thread.
    _infer_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _ensure_backends(self) -> None:
        # Deprecated helper — generate() now lazy-loads only the needed path.
        with self._backend_lock:
            if self._qwen is None:
                self._qwen = create_qwen_backend(self.backend_kind, preferred_gpu=self.preferred_gpu)
            if self._dream is None:
                self._dream = create_dream_backend(self.backend_kind, preferred_gpu=self.preferred_gpu)

    def agents_md(self) -> str:
        path = self.repo_root / "AGENTS.md"
        if path.is_file():
            return path.read_text(encoding="utf-8")[:6000]
        return ""

    def dream_is_loaded(self) -> bool:
        dream = self._dream
        if dream is None:
            return False
        ready = getattr(dream, "ready", None)
        if callable(ready):
            return bool(ready())
        return getattr(dream, "_model", None) is not None

    def qwen_is_loaded(self) -> bool:
        qwen = self._qwen
        if qwen is None:
            return False
        return getattr(qwen, "_model", None) is not None

    def any_llm_loaded(self) -> bool:
        return self.qwen_is_loaded() or self.dream_is_loaded()

    def warm_dream(self) -> str:
        """Load Dream weights now (blocking). Safe to call from a worker thread.

        With ``LEITNER_DREAM_URL``, polls the launcher daemon until ready (or timeout)
        instead of loading a second copy of the model into the ACP process.
        """
        if self.backend_kind == "stub":
            return "stub-noop"
        with self._backend_lock:
            if self._dream is None:
                self._dream = create_dream_backend(
                    self.backend_kind, preferred_gpu=self.preferred_gpu
                )
            dream = self._dream

        # Daemon path: wait for pre-warm started by Open-Leitner-Zed-Patched.bat.
        # Warm gets its own (longer) budget: shard load legitimately takes 10-15 min
        # when ComfyUI batches hammer the other T10 + disk.
        ready_fn = getattr(dream, "ready", None)
        if callable(ready_fn):
            import time

            warm_s = float(os.environ.get("LEITNER_WARM_TIMEOUT_S", "900"))
            deadline = time.monotonic() + warm_s
            while time.monotonic() < deadline:
                if ready_fn():
                    return "ready"
                time.sleep(2.0)
            # Surface the daemon's own view instead of a generic "check CUDA".
            health_fn = getattr(dream, "health", None)
            health = health_fn() if callable(health_fn) else None
            if health is None:
                detail = "daemon unreachable — did the Dream Daemon window close?"
            elif health.get("error"):
                detail = f"daemon load failed: {health['error']}"
            else:
                detail = (
                    f"daemon still loading after {health.get('loading_s') or warm_s:.0f}s "
                    "(ComfyUI on the other T10 slows shard streaming a lot)"
                )
            raise TimeoutError(f"Dream warm timed out after {warm_s:.0f}s — {detail}")

        load = getattr(dream, "load", None)
        if callable(load):
            with self._infer_lock:
                load()
        return "ready" if self.dream_is_loaded() else "no-model"

    def plan_prompt(self, user_text: str, tool_trace: str = "") -> tuple[TaskClass, InferenceArm, str]:
        task = classify_task(user_text)
        decision = self.catalyst.decide(task)
        agents = self.agents_md()
        prompt = (
            f"{SYSTEM_HINT}\n\n--- AGENTS.md ---\n{agents}\n\n"
            f"--- tool_trace ---\n{tool_trace or '(none)'}\n\n"
            f"--- user ---\n{user_text}\n"
        )
        return task, decision.arm, prompt

    def generate(
        self,
        arm: InferenceArm,
        prompt: str,
        *,
        task_class: TaskClass = TaskClass.WORDING_REFINE,
        chunk_id: str = "acp",
    ) -> tuple[str, dict]:
        meta: dict = {"arm": arm.as_dict(), "backend": self.backend_kind, "task_class": task_class.value}
        # Hold create-lock only while resolving backends. Inference uses a separate
        # lock so a timed-out ACP turn does not deadlock the next prompt forever
        # (asyncio cancel cannot stop a torch load thread).
        with self._backend_lock:
            use_dream = arm.path != "qwen_q4"
            if use_dream:
                if self._dream is None:
                    self._dream = create_dream_backend(
                        self.backend_kind, preferred_gpu=self.preferred_gpu
                    )
                ready_fn = getattr(self._dream, "ready", None)
                if callable(ready_fn) and not ready_fn():
                    use_dream = False
                    meta["dream_fallback"] = "daemon_not_ready_qwen"
                elif self.backend_kind == "transformers" and not self.dream_is_loaded():
                    from leitner_learning.inference.dream_daemon_client import dream_daemon_url

                    if dream_daemon_url():
                        use_dream = False
                        meta["dream_fallback"] = "daemon_url_set_but_not_ready_qwen"

            if not use_dream:
                if self._qwen is None:
                    self._qwen = create_qwen_backend(
                        self.backend_kind, preferred_gpu=self.preferred_gpu
                    )
                runner = self._qwen
                qwen_arm = InferenceArm(
                    path="qwen_q4", steps=0, alg="entropy", cache_steps=0, early_exit=False
                )
                qwen_mode = "extract" if task_class is TaskClass.JSON_EXTRACT else "chat"
            else:
                runner = self._dream
                qwen_arm = None
                qwen_mode = None

        with self._infer_lock:
            if not use_dream:
                assert qwen_arm is not None and qwen_mode is not None
                result = runner.run(
                    qwen_arm, prompt, chunk_id=chunk_id, mode=qwen_mode
                )
                text = result.text
                if self.backend_kind == "stub":
                    text = self._stub_tools_overlay(prompt, text)
                reward = CatalystReward(
                    arm_key=arm.key() if arm.path == "qwen_q4" else qwen_arm.key(),
                    schema_ok=getattr(result, "schema_ok", True),
                    denoise_ms=getattr(result, "latency_ms", 0.0),
                    peak_vram_mb=getattr(result, "peak_vram_mb", 0.0),
                    meta={
                        "stage": "acp_qwen",
                        "qwen_mode": qwen_mode,
                        **(
                            {"fallback_from": arm.path}
                            if meta.get("dream_fallback")
                            else {}
                        ),
                    },
                )
            else:
                result = runner.run(arm, prompt, forbid_model_split=True)
                text = result.text
                if self.backend_kind == "stub":
                    text = self._stub_tools_overlay(prompt, text)
                reward = CatalystReward(
                    arm_key=arm.key(),
                    schema_ok=True,
                    denoise_ms=getattr(result, "denoise_ms", 0.0),
                    peak_vram_mb=getattr(result, "peak_vram_mb", 0.0),
                    meta={
                        "stage": "acp_dream",
                        "dkv_refreshes": getattr(result, "dkv_refreshes", 0),
                    },
                )

        from leitner_learning.inference.models import CatalystDecision

        # Reward the arm that actually ran. Dream→Qwen fallback must not
        # inflate Dream Thompson posteriors with Qwen latency/success.
        rewarded_arm = arm
        if meta.get("dream_fallback"):
            rewarded_arm = InferenceArm(
                path="qwen_q4", steps=0, alg="entropy", cache_steps=0, early_exit=False
            )
            reward.arm_key = rewarded_arm.key()
            reward.meta = {
                **dict(reward.meta),
                "fallback_from": arm.key(),
                "requested_arm": arm.as_dict(),
            }
        with self._backend_lock:
            self.catalyst.record_reward(
                CatalystDecision(task_class=task_class, arm=rewarded_arm),
                reward,
            )
        meta["reward"] = reward.as_dict()
        meta["rewarded_arm"] = rewarded_arm.as_dict()
        return text, meta

    def _stub_tools_overlay(self, prompt: str, base: str) -> str:
        """Make stub backend useful for agent demos without weights."""
        import json
        import re

        lower = prompt.lower()
        user = prompt.split("--- user ---")[-1] if "--- user ---" in prompt else prompt
        u = user.strip()
        trace = ""
        if "--- tool_trace ---" in prompt:
            trace = prompt.split("--- tool_trace ---")[-1].split("--- user ---")[0]

        # After tools ran, always finish the turn.
        if "READ " in trace or "WRITE " in trace or "SHELL " in trace:
            summary = trace.strip()[:1500] or "done"
            return '{"action":"final","text":%s}' % json.dumps(
                f"Tool results:\n{summary}"
            )

        if u.lower().startswith("read ") or "read file" in lower:
            m = re.search(r"read\s+(?:file\s+)?([^\s]+)", u, re.I)
            if m:
                return '{"action":"read_file","path":"%s"}' % m.group(1).strip('"')
        if u.lower().startswith("write ") and " to " in u.lower():
            return (
                '{"action":"final","text":"Specify write as: WRITE path <<<\\ncontent\\n>>>"}'
            )
        if "list tools" in lower or "what can you do" in lower:
            return (
                '{"action":"final","text":"Tools: read_file, write_file, shell. '
                'Backends: Qwen extract / Dream refine via DualPath catalyst."}'
            )
        cleaned = base
        if cleaned.startswith("[stub-dream"):
            cleaned = cleaned.split("]", 1)[-1].strip()
        if cleaned.startswith("[stub-qwen"):
            cleaned = cleaned.split("]", 1)[-1].strip()
        # Stub backends used to echo the system preamble; after the user-turn
        # extract they often return only the user's words — both are not answers.
        leaks_system = cleaned.startswith("You are the Leitner") or (
            "--- AGENTS.md ---" in cleaned[:500]
        )
        echoes_user = bool(u) and cleaned.strip().lower() == u.strip().lower()
        stub_placeholder = cleaned.startswith("(stub) reply to:")
        # Default ACP chat is Qwen now; stub Qwen returns flashcard JSON — not a chat reply.
        user_l = u.lower()
        wants_extract = bool(
            re.search(r"\b(extract|flashcards?|flash\s*cards?)\b", user_l)
            or (
                re.search(r"\bjson\b", user_l)
                and re.search(r"\b(card|cards|extract|flash)\b", user_l)
            )
        )
        mistyped_extract = (not wants_extract) and (
            cleaned.lstrip().startswith('{"cards"') or '"source_chunk_id"' in cleaned[:300]
        )
        if (
            leaks_system
            or echoes_user
            or stub_placeholder
            or mistyped_extract
            or not cleaned.strip()
        ):
            reply = (
                f"(Leitner Stub / no GPU) Heard you: {u[:800] or '(empty message)'}\n\n"
                "I can read/write files and run shell when you ask "
                "(e.g. `read AGENTS.md` or `list tools`). "
                "Use **Leitner Dream** (Ctrl+Alt+D) for real Dream/Qwen answers."
            )
            return '{"action":"final","text":%s}' % json.dumps(reply)
        # Stub chat mode already emits ACP action JSON — don't double-wrap.
        if cleaned.lstrip().startswith("{") and '"action"' in cleaned[:80]:
            return cleaned
        return '{"action":"final","text":%s}' % json.dumps(cleaned[:2000])
