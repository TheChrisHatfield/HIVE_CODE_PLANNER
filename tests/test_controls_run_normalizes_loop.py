"""Controls Run must accept the same typed loop aliases as Execute."""

from __future__ import annotations

from hive_planner.launcher.app import HivePlannerApp


class _Var:
    def __init__(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


def test_controls_run_maps_code_spec_alias_to_codespec_status() -> None:
    seen: list[bool] = []

    class Stub:
        controls_loop = _Var("code spec")
        controls_command = _Var("Status")
        normalize_controls_loop = staticmethod(HivePlannerApp.normalize_controls_loop)

        def resolved_loop_command(self, loop: str, command: str):
            return HivePlannerApp.resolved_loop_command(loop, command)

        def _sync_controls_command_choices(self) -> None:
            raise AssertionError("alias should resolve without a mismatch warning")

        def _on_implementation_loop_install(self, *, from_controls: bool = False) -> None:
            raise AssertionError("Status was selected")

        def _on_implementation_loop_peek_pack(self) -> None:
            raise AssertionError("Status was selected")

        def _on_implementation_loop_status(self, *, from_controls: bool = False) -> None:
            seen.append(from_controls)

        def _on_implementation_loop_start(self, *, from_controls: bool = False) -> None:
            raise AssertionError("Status was selected")

        def _on_implementation_loop_handoff(self, *, from_controls: bool = False) -> None:
            raise AssertionError("Status was selected")

        def _on_implementation_loop_check(self) -> None:
            raise AssertionError("Status was selected")

        def _on_implementation_loop_accept(self, *, from_controls: bool = False) -> None:
            raise AssertionError("Status was selected")

        def _on_implementation_loop_commit(self) -> None:
            raise AssertionError("Status was selected")

    HivePlannerApp._on_controls_run(Stub())
    assert seen == [True]
    assert Stub.controls_loop.get() == "CodeSpec"
