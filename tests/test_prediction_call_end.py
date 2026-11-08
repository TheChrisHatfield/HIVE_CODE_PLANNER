"""Ad hoc call-end capture for any composer tab in this repo. Local hook, not product bootstrap."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".cursor" / "hooks" / "prediction_bug_hunt_call_end.py"
COMPOSER = "b997d166-609a-4a86-a9e5-5b2bf07e325d"
SLOTS = ("slot",)


def _load():
    spec = importlib.util.spec_from_file_location("prediction_bug_hunt_call_end", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _db(
    path: Path,
    name: str,
    *,
    subagent: int = 0,
    workspace: str = "slot",
    composer: str = COMPOSER,
) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE composerHeaders (
            composerId TEXT,
            workspaceId TEXT,
            value TEXT,
            isSubagent INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO composerHeaders VALUES (?, ?, ?, ?)",
        (composer, workspace, json.dumps({"name": name}), subagent),
    )
    conn.commit()
    conn.close()


def _voice(
    path: Path,
    texts: list[str],
    *,
    composer: str = COMPOSER,
    call_id: str = "call-live",
    started: int = 100,
    ended: int | None = 200,
    assistants: tuple[str, ...] = (),
    chunk: int = 0,
) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS ItemTable (key TEXT PRIMARY KEY, value TEXT)")
    body: dict[str, object] = {
        "callId": call_id,
        "agentId": composer,
        "startedAtMs": started,
        "mode": "utterances",
        "turnCount": len(texts),
    }
    if ended is not None:
        body["endedAtMs"] = ended
    conn.execute(
        "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
        (f"glass.realtimeVoice.calls/{composer}/{call_id}", json.dumps(body)),
    )
    turns: list[dict[str, str]] = []
    for text in texts:
        turns.append({"speaker": "user", "text": text, "itemId": f"u{len(turns)}"})
    for text in assistants:
        turns.append({"speaker": "assistant", "text": text, "itemId": f"a{len(turns)}"})
    conn.execute(
        "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
        (f"glass.realtimeVoice.callTurns/{composer}/{call_id}/{chunk}", json.dumps(turns)),
    )
    conn.commit()
    conn.close()


def _transcript(projects: Path, repo: Path, text: str) -> None:
    slug = _load().project_slug(repo)
    folder = projects / slug / "agent-transcripts" / COMPOSER
    folder.mkdir(parents=True)
    row = {
        "role": "user",
        "message": {"content": [{"type": "text", "text": f"<user_query>\n{text}\n</user_query>"}]},
    }
    (folder / f"{COMPOSER}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_scope_bullet_stays_within_the_continual_memory_limit() -> None:
    hook = _load()
    bullet = hook.scope_bullet()
    assert bullet.startswith("- ")
    assert "any composer tab in this repo" in bullet
    assert "PREDICTION_BUG_HUNT" in bullet
    assert "not permanent" in bullet
    assert len(bullet) <= hook.MAX_BULLET_CHARS


def _end(payload: dict | None = None) -> dict:
    body = {"hook_event_name": "sessionEnd", "reason": "user_close"}
    if payload:
        body.update(payload)
    return body


def test_stop_without_a_call_status_does_not_write(tmp_path: Path) -> None:
    hook = _load()
    memory = tmp_path / "memory.md"
    memory.write_text("keep\n", encoding="utf-8")
    result = hook.run(
        {
            "hook_event_name": "stop",
            "conversation_id": COMPOSER,
        },
        repo=tmp_path / "repo",
        db_path=tmp_path / "missing.db",
        projects_root=tmp_path / "projects",
        memory_path=memory,
    )
    assert result == {"status": "skipped", "reason": "turn_completed"}
    assert memory.read_text(encoding="utf-8") == "keep\n"


def test_completed_stop_writes_the_memory_file(tmp_path: Path) -> None:
    hook = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    db = tmp_path / "state.vscdb"
    _db(db, "PREDICTION_BUG_HUNT")
    _voice(db, ["A completed stop is the hang-up."], assistants=("agent reply stays out",))
    projects = tmp_path / "projects"
    _transcript(projects, repo, "The agent jsonl is not the capture source.")
    memory = repo / "memory.md"
    result = hook.run(
        {
            "hook_event_name": "stop",
            "status": "completed",
            "conversation_id": COMPOSER,
        },
        repo=repo,
        db_path=db,
        workspace_ids=SLOTS,
        projects_root=projects,
        memory_path=memory,
    )
    assert hook.call_end_reason({"hook_event_name": "stop", "status": "completed"}) == ""
    assert result["status"] == "wrote"
    text = memory.read_text(encoding="utf-8")
    assert "A completed stop is the hang-up." in text
    assert "agent reply stays out" not in text
    assert "The agent jsonl is not the capture source." not in text
    assert "glass.realtimeVoice.callTurns/" in text
    assert "<!-- call-end-capture:start -->" in text
    assert "<!-- call-end-capture:end -->" in text


def test_missing_composer_id_does_not_write(tmp_path: Path) -> None:
    hook = _load()
    memory = tmp_path / "memory.md"
    memory.write_text("keep\n", encoding="utf-8")
    result = hook.run(
        _end(),
        repo=tmp_path / "repo",
        db_path=tmp_path / "missing.db",
        projects_root=tmp_path / "projects",
        memory_path=memory,
    )
    assert result == {"status": "skipped", "reason": "missing_composer_id"}
    assert memory.read_text(encoding="utf-8") == "keep\n"


def test_other_workspace_does_not_write(tmp_path: Path) -> None:
    hook = _load()
    db = tmp_path / "state.vscdb"
    _db(db, "UPDATE_BUTTON_BUG_HUNT", workspace="elsewhere")
    memory = tmp_path / "memory.md"
    memory.write_text("keep\n", encoding="utf-8")
    result = hook.run(
        _end({"conversation_id": COMPOSER}),
        repo=tmp_path / "repo",
        db_path=db,
        workspace_ids=SLOTS,
        projects_root=tmp_path / "projects",
        memory_path=memory,
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "other_workspace"
    assert memory.read_text(encoding="utf-8") == "keep\n"


def test_blank_workspace_id_is_not_another_workspace(tmp_path: Path) -> None:
    hook = _load()
    db = tmp_path / "state.vscdb"
    _db(db, "UNSCOPED_TAB", workspace="")
    assert hook.header_title(db, COMPOSER, SLOTS) == ("", "missing")


def test_newest_header_name_wins_when_rows_are_unordered(tmp_path: Path) -> None:
    hook = _load()
    db = tmp_path / "state.vscdb"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE composerHeaders (
            composerId TEXT,
            workspaceId TEXT,
            value TEXT,
            isSubagent INTEGER,
            lastUpdatedAt INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO composerHeaders VALUES (?, ?, ?, ?, ?)",
        (COMPOSER, "slot", json.dumps({"name": "STALE_TAB"}), 0, 10),
    )
    conn.execute(
        "INSERT INTO composerHeaders VALUES (?, ?, ?, ?, ?)",
        (COMPOSER, "", json.dumps({"name": "BLANK_SLOT"}), 0, 50),
    )
    conn.execute(
        "INSERT INTO composerHeaders VALUES (?, ?, ?, ?, ?)",
        (COMPOSER, "slot", json.dumps({"name": "CURRENT_TAB"}), 0, 20),
    )
    conn.commit()
    conn.close()
    assert hook.header_title(db, COMPOSER, SLOTS) == ("CURRENT_TAB", "ok")


def test_subagent_header_is_not_the_tab(tmp_path: Path) -> None:
    hook = _load()
    db = tmp_path / "state.vscdb"
    _db(db, "PREDICTION_BUG_HUNT", subagent=1)
    result = hook.run(
        _end({"composerId": COMPOSER}),
        repo=tmp_path / "repo",
        db_path=db,
        workspace_ids=SLOTS,
        projects_root=tmp_path / "projects",
        memory_path=tmp_path / "memory.md",
    )
    assert result == {"status": "skipped", "reason": "missing"}
    assert not (tmp_path / "memory.md").exists()


def test_confirmed_tab_preserves_curated_text_and_adds_scope(tmp_path: Path) -> None:
    hook = _load()
    repo = tmp_path / "DRIVE_DOWNLOADS" / "HIVE_CODE_PLANNER"
    repo.mkdir(parents=True)
    db = tmp_path / "state.vscdb"
    _db(db, "PREDICTION_BUG_HUNT")
    _voice(db, ["Record the fading twenty-vote anchor."])
    projects = tmp_path / "projects"
    _transcript(projects, repo, "Record the fading twenty-vote anchor.")
    memory = repo / "docs" / "specs" / "bug-hunt" / "TEMP-prediction-memory.md"
    memory.parent.mkdir(parents=True)
    memory.write_text(
        "# Temporary prediction memory\n\n## Learned User Preferences\n\n"
        "- Lookup and transcript search do not change files.\n\n"
        "## Design memory (behavioral — do not merge into AGENTS.md)\n\n"
        "- Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0. # behavioral\n",
        encoding="utf-8",
    )
    result = hook.run(
        _end({"conversation_id": COMPOSER}),
        repo=repo,
        db_path=db,
        workspace_ids=SLOTS,
        projects_root=projects,
        memory_path=memory,
    )
    assert result["status"] == "wrote"
    text = memory.read_text(encoding="utf-8")
    assert "Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0." in text
    assert "Lookup and transcript search do not change files." in text
    assert hook.scope_bullet() in text
    assert "Record the fading twenty-vote anchor." in text
    assert COMPOSER in text
    assert all(len(line) <= hook.MAX_BULLET_CHARS for line in text.splitlines() if line.startswith("- "))


def test_transcript_folder_without_jsonl_does_not_write(tmp_path: Path) -> None:
    hook = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    db = tmp_path / "state.vscdb"
    _db(db, "PREDICTION_BUG_HUNT")
    slug = hook.project_slug(repo)
    folder = tmp_path / "projects" / slug / "agent-transcripts" / COMPOSER
    folder.mkdir(parents=True)
    result = hook.run(
        _end({"conversation_id": COMPOSER}),
        repo=repo,
        db_path=db,
        workspace_ids=SLOTS,
        projects_root=tmp_path / "projects",
        memory_path=repo / "memory.md",
    )
    assert result == {"status": "skipped", "reason": "missing_transcript"}
    assert not (repo / "memory.md").exists()


def test_missing_transcript_does_not_create_a_file(tmp_path: Path) -> None:
    hook = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    db = tmp_path / "state.vscdb"
    _db(db, "prediction_bug_hunt")
    result = hook.run(
        _end({"conversation_id": COMPOSER}),
        repo=repo,
        db_path=db,
        workspace_ids=SLOTS,
        projects_root=tmp_path / "projects",
        memory_path=repo / "docs" / "specs" / "bug-hunt" / "TEMP-prediction-memory.md",
    )
    assert result == {"status": "skipped", "reason": "missing_transcript"}
    assert not (repo / "docs").exists()


def test_aborted_stop_still_writes(tmp_path: Path) -> None:
    hook = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    db = tmp_path / "state.vscdb"
    _db(db, "PREDICTION_BUG_HUNT")
    _voice(db, ["A dropped turn still belongs in memory."])
    projects = tmp_path / "projects"
    _transcript(projects, repo, "A dropped turn still belongs in memory.")
    memory = repo / "memory.md"
    result = hook.run(
        {
            "hook_event_name": "stop",
            "status": "aborted",
            "conversation_id": COMPOSER,
        },
        repo=repo,
        db_path=db,
        workspace_ids=SLOTS,
        projects_root=projects,
        memory_path=memory,
    )
    assert result["status"] == "wrote"
    assert "A dropped turn still belongs in memory." in memory.read_text(encoding="utf-8")


def test_path_escape_composer_id_does_not_write(tmp_path: Path) -> None:
    hook = _load()
    memory = tmp_path / "memory.md"
    memory.write_text("keep\n", encoding="utf-8")
    result = hook.run(
        _end({"conversation_id": "../not-a-composer"}),
        repo=tmp_path / "repo",
        db_path=tmp_path / "missing.db",
        projects_root=tmp_path / "projects",
        memory_path=memory,
    )
    assert result == {"status": "skipped", "reason": "missing_composer_id"}
    assert memory.read_text(encoding="utf-8") == "keep\n"


def test_second_write_does_not_duplicate_the_scope_bullet(tmp_path: Path) -> None:
    hook = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    db = tmp_path / "state.vscdb"
    _db(db, "PREDICTION_BUG_HUNT")
    _voice(db, ["Once is enough."])
    projects = tmp_path / "projects"
    _transcript(projects, repo, "Once is enough.")
    memory = repo / "memory.md"
    payload = _end({"conversation_id": COMPOSER})
    kwargs = {
        "repo": repo,
        "db_path": db,
        "workspace_ids": SLOTS,
        "projects_root": projects,
        "memory_path": memory,
    }
    assert hook.run(payload, **kwargs)["status"] == "wrote"
    assert hook.run(payload, **kwargs)["status"] == "wrote"
    text = memory.read_text(encoding="utf-8")
    assert text.count(hook.scope_bullet()) == 1
    assert text.count("Once is enough.") == 1


def test_truncated_requests_collapse_to_one_bullet() -> None:
    hook = _load()
    long_a = "A" * 300 + " one"
    long_b = "A" * 300 + " two"
    capture = hook.render_capture(COMPOSER, Path("C:/transcripts") / COMPOSER, [long_a, long_b])
    assert "any composer tab in this repo" in capture
    assert "tab only" not in capture
    bullets = [line for line in capture.splitlines() if line.startswith("- A")]
    assert len(bullets) == 1
    assert len(bullets[0]) <= hook.MAX_BULLET_CHARS


def test_last_twenty_keeps_the_latest_repeat(tmp_path: Path) -> None:
    hook = _load()
    requests = [f"request {index}" for index in range(25)]
    requests.append("request 0")
    capture = hook.render_capture(COMPOSER, Path("C:/transcripts") / COMPOSER, requests)
    bodies = [line for line in capture.splitlines() if line.startswith("- request")]
    assert len(bodies) == 20
    assert bodies[-1] == "- request 0"
    assert "- request 5" not in bodies
    assert bodies[0] == "- request 6"


def test_voice_capture_matches_the_existing_bullet_format(tmp_path: Path) -> None:
    hook = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    db = tmp_path / "state.vscdb"
    _db(db, "PREDICTION_BUG_HUNT")
    _voice(db, ["older call"], call_id="call-old", started=1)
    _voice(db, ["second chunk"], call_id="call-live", started=50, chunk=1)
    _voice(
        db,
        ["first chunk"],
        call_id="call-live",
        started=50,
        chunk=0,
        assistants=("assistant stays out",),
    )
    memory = repo / "memory.md"
    result = hook.run(
        _end({"conversation_id": COMPOSER}),
        repo=repo,
        db_path=db,
        workspace_ids=SLOTS,
        projects_root=tmp_path / "projects",
        memory_path=memory,
    )
    assert result["status"] == "wrote"
    source = f"glass.realtimeVoice.callTurns/{COMPOSER}/call-live"
    expected = hook.render_capture(COMPOSER, source, ["first chunk", "second chunk"])
    text = memory.read_text(encoding="utf-8")
    start = text.index(hook.CAPTURE_START)
    end = text.index(hook.CAPTURE_END) + len(hook.CAPTURE_END)
    assert text[start:end] == expected
    assert text[start:end].splitlines()[1] == "## Call-end capture"
    assert "older call" not in text
    assert "assistant stays out" not in text
    assert all(line.startswith("- ") and len(line) <= hook.MAX_BULLET_CHARS for line in text.splitlines() if line.startswith("- "))


def test_voice_read_is_inside_the_memory_lock(tmp_path: Path) -> None:
    hook = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    db = tmp_path / "state.vscdb"
    _db(db, "PREDICTION_BUG_HUNT")
    _voice(db, ["Read this while the lock is held."])
    memory = repo / "memory.md"
    seen: dict[str, bool] = {}
    original = hook.voice_user_requests

    def wrapped(*args, **kwargs):
        seen["locked"] = hook._lock_path(memory).is_file()
        return original(*args, **kwargs)

    hook.voice_user_requests = wrapped
    try:
        result = hook.run(
            _end({"conversation_id": COMPOSER}),
            repo=repo,
            db_path=db,
            workspace_ids=SLOTS,
            projects_root=tmp_path / "projects",
            memory_path=memory,
        )
    finally:
        hook.voice_user_requests = original
    assert result["status"] == "wrote"
    assert seen["locked"] is True
    assert not hook._lock_path(memory).exists()


def test_locked_voice_store_is_busy_not_missing(tmp_path: Path) -> None:
    hook = _load()
    db = tmp_path / "state.vscdb"
    _db(db, "PREDICTION_BUG_HUNT")
    _voice(db, ["A locked store must not look like an empty call."])
    holder = sqlite3.connect(db)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        reason, _call_id, requests = hook.voice_user_requests(db, COMPOSER, timeout=0.2)
    finally:
        holder.rollback()
        holder.close()
    assert reason == "busy"
    assert requests == []


def test_capture_temp_stays_beside_the_memory_file(tmp_path: Path, monkeypatch) -> None:
    hook = _load()
    memory = tmp_path / "docs" / "TEMP-prediction-memory.md"
    seen: dict[str, Path] = {}
    real = hook.os.replace

    def wrapped(src, dst):
        seen["src"] = Path(src)
        seen["dst"] = Path(dst)
        return real(src, dst)

    monkeypatch.setattr(hook.os, "replace", wrapped)
    hook._replace_capture(memory, hook.render_capture(COMPOSER, "voice", ["A hang-up still writes."]))
    assert seen["src"].parent == memory.parent
    assert seen["dst"] == memory
    assert "A hang-up still writes." in memory.read_text(encoding="utf-8")
    assert not memory.with_name(memory.name + ".tmp").exists()


def test_empty_or_bad_transcript_does_not_replace_the_log(tmp_path: Path) -> None:
    hook = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    db = tmp_path / "state.vscdb"
    _db(db, "PREDICTION_BUG_HUNT")
    _voice(db, [], assistants=("no user request",))
    projects = tmp_path / "projects"
    memory = repo / "memory.md"
    memory.write_text("Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0.\n", encoding="utf-8")
    result = hook.run(
        _end({"conversation_id": COMPOSER}),
        repo=repo,
        db_path=db,
        workspace_ids=SLOTS,
        projects_root=projects,
        memory_path=memory,
    )
    assert result == {"status": "skipped", "reason": "empty_transcript"}
    assert memory.read_text(encoding="utf-8") == "Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0.\n"
    memory.write_bytes(b"\xff\xfe")
    _voice(db, ["Keep the seed."])
    bad = hook.run(
        _end({"conversation_id": COMPOSER}),
        repo=repo,
        db_path=db,
        workspace_ids=SLOTS,
        projects_root=projects,
        memory_path=memory,
    )
    assert bad == {"status": "skipped", "reason": "unreadable"}
    assert memory.read_bytes() == b"\xff\xfe"


def test_transcript_outside_the_project_is_rejected(tmp_path: Path) -> None:
    hook = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    projects = tmp_path / "projects"
    outside = tmp_path / "outside"
    outside.mkdir()
    slug = hook.project_slug(repo)
    link = projects / slug / "agent-transcripts" / COMPOSER
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        return
    assert hook.transcript_dir_for(repo, COMPOSER, projects) is None


def test_broken_capture_marker_does_not_drop_the_preface() -> None:
    hook = _load()
    merged = hook.merge_memory("keep this\n\n" + hook.CAPTURE_START + "\norphan", "NEW")
    assert merged.startswith("keep this")
    assert "NEW" in merged
    assert "orphan" not in merged


def test_lock_file_is_outside_the_repo(tmp_path: Path) -> None:
    hook = _load()
    memory = tmp_path / "docs" / "TEMP-prediction-memory.md"
    lock = hook._lock_path(memory)
    assert lock.parent != memory.parent
    assert "TEMP-prediction-memory.md" not in lock.name


def test_recall_phrases_match_only_at_the_start() -> None:
    hook = _load()
    assert hook.is_recall_prompt("Hey, refresh your memory")
    assert hook.is_recall_prompt("hey refresh your memory please")
    assert hook.is_recall_prompt("Do you remember the six weights?")
    assert hook.is_recall_prompt("total recall")
    assert hook.is_recall_prompt("Recall the seed")
    assert hook.is_recall_prompt("do you recall the weights")
    assert hook.is_recall_prompt("do you recall?")
    assert hook.is_recall_prompt("total recall!")
    assert not hook.is_recall_prompt("Please do you remember")
    assert not hook.is_recall_prompt("Later, hey, refresh your memory")
    assert not hook.is_recall_prompt("recallable facts")
    assert not hook.is_recall_prompt("do you know the seed")


def test_wrapped_voice_prompt_reads_memory_and_does_not_write(tmp_path: Path) -> None:
    hook = _load()
    memory = tmp_path / "TEMP-prediction-memory.md"
    memory.write_text("Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0.\n", encoding="utf-8")
    before = memory.read_bytes()
    spoken = "do you recall where we last left off regarding the repo"
    result = hook.recall(
        {
            "hook_event_name": "beforeSubmitPrompt",
            "prompt": f'Trace the failure when the user said "{spoken}" in the tab.',
        },
        memory_path=memory,
    )
    assert result["additional_context"].startswith("ANSWER FROM THE FOLLOWING RECALLED MEMORY FIRST")
    assert memory.read_bytes() == before
    missed = hook.recall(
        {"prompt": 'The user said "yesterday do you recall the seed".'},
        memory_path=memory,
    )
    assert missed == {"continue": True}


def test_recall_reads_the_memory_file_and_does_not_write(tmp_path: Path) -> None:
    hook = _load()
    memory = tmp_path / "TEMP-prediction-memory.md"
    memory.write_text("Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0.\n", encoding="utf-8")
    before = memory.read_bytes()
    result = hook.recall(
        {
            "hook_event_name": "beforeSubmitPrompt",
            "prompt": "hey, refresh your memory",
        },
        memory_path=memory,
    )
    assert result["continue"] is True
    assert result["additional_context"].startswith("ANSWER FROM THE FOLLOWING RECALLED MEMORY FIRST")
    assert "Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0." in result["additional_context"]
    assert "SUPPORTING CHAT DETAIL" not in result["additional_context"]
    assert len(result["additional_context"]) <= hook._CONTEXT_LIMIT
    assert memory.read_bytes() == before


def test_recall_new_phrase_reads_and_does_not_write(tmp_path: Path) -> None:
    hook = _load()
    memory = tmp_path / "TEMP-prediction-memory.md"
    memory.write_text("Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0.\n", encoding="utf-8")
    before = memory.read_bytes()
    result = hook.recall(
        {"prompt": "total recall"},
        memory_path=memory,
    )
    assert "Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0." in result["additional_context"]
    assert memory.read_bytes() == before
    missed = hook.recall(
        {"prompt": "recallable facts"},
        memory_path=memory,
    )
    assert missed == {"continue": True}


def test_recall_ignores_composer_tab_and_workspace(tmp_path: Path) -> None:
    hook = _load()
    memory = tmp_path / "TEMP-prediction-memory.md"
    memory.write_text("Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0.\n", encoding="utf-8")
    before = memory.read_bytes()
    result = hook.recall(
        {"prompt": "do you recall the seed"},
        memory_path=memory,
    )
    assert result["additional_context"].startswith("ANSWER FROM THE FOLLOWING RECALLED MEMORY FIRST")
    assert "Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0." in result["additional_context"]
    assert memory.read_bytes() == before
    bare = hook.recall({"prompt": "do you remember"}, memory_path=memory)
    assert "Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0." in bare["additional_context"]


def test_new_tab_is_found_from_the_workspace_slot(tmp_path: Path) -> None:
    hook = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    slot = "fresh-slot"
    storage = tmp_path / "workspaceStorage" / slot
    storage.mkdir(parents=True)
    (storage / "workspace.json").write_text(
        json.dumps({"folder": str(repo)}),
        encoding="utf-8",
    )
    new_id = "c0ffee00-1111-2222-3333-444455556666"
    db = tmp_path / "state.vscdb"
    _db(db, "BRAND_NEW_TAB", workspace=slot, composer=new_id)
    _voice(db, ["A new tab still captures."], composer=new_id)
    projects = tmp_path / "projects"
    memory = repo / "memory.md"
    found = hook.repo_workspace_ids(repo, tmp_path / "workspaceStorage")
    assert found == [slot]
    result = hook.run(
        _end({"conversation_id": new_id}),
        repo=repo,
        db_path=db,
        projects_root=projects,
        memory_path=memory,
        storage_root=tmp_path / "workspaceStorage",
    )
    assert result["status"] == "wrote"
    assert result["tab"] == "BRAND_NEW_TAB"
    assert "A new tab still captures." in memory.read_text(encoding="utf-8")


def test_context_stays_within_the_hook_limit() -> None:
    hook = _load()
    marker = hook.CAPTURE_START
    text = ("Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0.\n" * 400) + marker + ("log line\n" * 800)
    fitted = hook.fit_context(text)
    assert len(fitted) <= hook._CONTEXT_LIMIT
    assert "Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0." in fitted


def test_slug_matches_the_cursor_project_folder() -> None:
    hook = _load()
    assert hook.project_slug(Path("d:/DRIVE_DOWNLOADS/HIVE_CODE_PLANNER")) == (
        "d-DRIVE-DOWNLOADS-HIVE-CODE-PLANNER"
    )
