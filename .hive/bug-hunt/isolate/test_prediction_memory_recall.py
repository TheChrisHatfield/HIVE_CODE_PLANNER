"""Memory-recall tree and bandit. Not the bug-hunt file ranker."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".cursor" / "hooks" / "prediction_memory_recall.py"

MEMORY = """
# Notes

## Design memory

- Seed is 3, 5, 5, 4, 4, 4. It starts with 20 imaginary votes.
- Real-row decay is 0.9 by row order.
- Bluetooth surround uses dual bandits for speech.

## Other

- Archive copies live on the H drive.
"""


def _load():
    spec = importlib.util.spec_from_file_location("prediction_memory_recall", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_a_multiline_comment_is_not_a_passage() -> None:
    hook = _load()
    marked = "<!--\nBluetooth surround secret\n-->\n- Seed is 3, 5, 5, 4, 4, 4.\n"
    assert "Bluetooth" not in hook.recall("bluetooth", marked, seed=0)
    assert "3, 5, 5, 4, 4, 4" in hook.recall("seed", marked, seed=0)
    trailing = "<!--\nsecret\n--> - Seed is 3, 5, 5, 4, 4, 4.\n"
    assert "secret" not in hook.recall("secret", trailing, seed=0)
    assert "3, 5, 5, 4, 4, 4" in hook.recall("seed", trailing, seed=0)
    doubled = "<!-- a --> <!-- b --> - Seed is 3, 5, 5, 4, 4, 4.\n"
    found = hook.recall("seed", doubled, seed=0)
    assert "<!--" not in found
    assert "3, 5, 5, 4, 4, 4" in found


def test_a_byte_order_mark_does_not_become_a_passage() -> None:
    hook = _load()
    marked = "\ufeff# Temporary\n\n- Seed is 3, 5, 5, 4, 4, 4.\n"
    assert "Temporary" not in hook.recall("temporary", marked, seed=0)
    assert "3, 5, 5, 4, 4, 4" in hook.recall("seed", marked, seed=0)


def test_single_digit_seed_votes_are_searchable() -> None:
    hook = _load()
    text = hook.recall("3 5 5 4 4 4", MEMORY, seed=1)
    assert "3, 5, 5, 4, 4, 4" in text
    assert "Bluetooth" not in text


def test_seed_question_pulls_the_seed_passage() -> None:
    hook = _load()
    text = hook.recall("do you remember the seed votes", MEMORY, seed=1)
    assert "3, 5, 5, 4, 4, 4" in text
    assert "Bluetooth" not in text


def test_command_words_do_not_outrank_the_subject() -> None:
    hook = _load()
    memory = (
        "- Recall phrases must start the spoken line: do you recall, total recall.\n"
        "- Seed is 3, 5, 5, 4, 4, 4.\n"
        "- Real-row decay is 0.9 by row order.\n"
    )
    for question in (
        "do you recall the seed",
        "total recall the seed",
        "refresh your memory the decay",
    ):
        text = hook.present_recall(question, memory, seed=0)
        if "seed" in question:
            assert "3, 5, 5, 4, 4, 4" in text
            assert "0.9" not in text
        else:
            assert "0.9" in text
            assert "3, 5, 5, 4, 4, 4" not in text
        assert "Recall phrases must start" not in text


def test_same_seed_is_stable() -> None:
    hook = _load()
    assert hook.recall("decay by row", MEMORY, seed=3) == hook.recall("decay by row", MEMORY, seed=3)


def test_empty_question_returns_nothing() -> None:
    hook = _load()
    assert hook.recall("   ", MEMORY, seed=0) == ""


def test_unrelated_question_does_not_dump_the_file() -> None:
    hook = _load()
    text = hook.recall("xylophone quantum", MEMORY, seed=2)
    assert "Bluetooth" not in text
    assert "H drive" not in text


def test_output_stays_inside_the_source_and_the_limit() -> None:
    hook = _load()
    text = hook.recall("seed", MEMORY, seed=4, limit=80)
    assert len(text) <= 80
    for line in text.splitlines():
        assert line in MEMORY


def test_expansions_stay_inside_the_memory_vocabulary() -> None:
    hook = _load()
    parts = hook.parts_of(MEMORY)
    branches = hook.search_branches("seed votes", parts, hook.random.Random(0))
    vocab = {token for part in parts for token in part.tokens}
    for branch in branches:
        assert set(branch.tokens) <= vocab | set(hook.tokenize("seed votes"))


def test_bandit_scores_a_branch_by_its_own_match() -> None:
    hook = _load()
    node = hook.Node(tokens=("seed",), visits=4, reward=4.0, match=0.25)
    assert hook._posterior(node) == (2.0, 4.0)


def test_passages_that_fit_exactly_are_kept() -> None:
    hook = _load()
    parts = [
        hook.Part("abcde", ("seed",)),
        hook.Part("wxyz", ("seed",)),
    ]
    node = hook.Node(tokens=("seed",), visits=4, reward=4.0)
    chosen = hook.select_parts([node], parts, hook.random.Random(0), limit=10)
    assert [part.text for part in chosen] == ["abcde", "wxyz"]
    assert len("\n".join(part.text for part in chosen)) == 10


def test_a_long_middle_passage_does_not_block_a_shorter_one() -> None:
    hook = _load()
    parts = [
        hook.Part("seed alpha beta gamma", ("seed",)),
        hook.Part("seed delta epsilon zeta", ("seed",)),
        hook.Part("seed ok", ("seed",)),
    ]
    node = hook.Node(tokens=("seed",), visits=4, reward=4.0)
    chosen = hook.select_parts([node], parts, hook.random.Random(0), limit=32)
    assert [part.text for part in chosen] == ["seed alpha beta gamma", "seed ok"]


def test_start_phrases_match_only_at_the_start() -> None:
    hook = _load()
    assert hook.opens_with_recall("Hey, refresh your memory")
    assert hook.opens_with_recall("hey refresh your memory please")
    assert hook.opens_with_recall("Do you remember the six weights?")
    assert hook.opens_with_recall("total recall")
    assert hook.opens_with_recall("Recall the seed")
    assert hook.opens_with_recall("do you recall the weights")
    assert hook.opens_with_recall("do you recall")
    assert hook.opens_with_recall("do you recall?")
    assert hook.opens_with_recall("do you recall!")
    assert hook.opens_with_recall("total recall,")
    assert hook.opens_with_recall("hey, refresh your memory.")
    assert not hook.opens_with_recall("Please do you remember")
    assert not hook.opens_with_recall("Later, hey, refresh your memory")
    assert hook.opens_with_recall("Recall.")
    assert not hook.opens_with_recall("recallable facts")
    assert not hook.opens_with_recall("recall.json")
    assert not hook.opens_with_recall("do you rememberable facts")
    assert hook.question_body("total recall the seed") == "total recall the seed"
    assert hook.question_body("recall the seed") == "recall the seed"


def test_wrapped_voice_prompt_matches_the_raw_line() -> None:
    hook = _load()
    spoken = "do you recall where we last left off regarding the repo"
    assembled = (
        "Trace why the trigger did not fire when the user said "
        f'"{spoken}" in the tab.'
    )
    assert not hook.opens_with_recall(assembled)
    sources = hook.recall_sources(
        f"<timestamp>Monday</timestamp>\n<user_query>\n{assembled}\n</user_query>",
        {"spoken_text": spoken},
    )
    assert spoken in sources
    assert any(hook.opens_with_recall(text) for text in sources)
    quoted_only = hook.recall_sources(assembled)
    assert any(hook.opens_with_recall(text) for text in quoted_only)
    asked = hook.recall_sources(
        'Check the log when the user asked "Do you recall the Thompson sampling?"'
    )
    assert any(hook.opens_with_recall(text) for text in asked)
    wrote = hook.recall_sources('The user wrote "do you recall the seed".')
    assert not any(hook.opens_with_recall(text) for text in wrote)
    later = hook.recall_sources('The user said "yesterday do you recall the seed".')
    assert not any(hook.opens_with_recall(text) for text in later)
    bare = hook.recall_sources('Look for the phrase "do you recall" in the file.')
    assert not any(hook.opens_with_recall(text) for text in bare)
    second = hook.recall_sources(
        'The user said "hello there". The caller said "do you recall the seed".'
    )
    assert not any(hook.opens_with_recall(text) for text in second)
    overridden = hook.recall_sources(
        'The user said "do you recall the seed".',
        {"spoken_text": "fix the tests"},
    )
    assert overridden == ["fix the tests"]
    assert not any(hook.opens_with_recall(text) for text in overridden)
    nested = hook.recall_sources(
        "<user_query>Trace this <user_query>do you recall the seed</user_query></user_query>"
    )
    assert any(hook.opens_with_recall(text) for text in nested)
    stamped = hook.recall_sources(
        "<user_query>\n<timestamp>Monday</timestamp>\ndo you recall the seed\n</user_query>"
    )
    assert any(hook.opens_with_recall(text) for text in stamped)
    assert hook.opens_with_recall("do you recall the weights")
    assert not hook.opens_with_recall("Please do you remember")


def test_voice_trigger_edges() -> None:
    hook = _load()
    empty_wrap = hook.recall_sources(
        "<user_query>   </user_query><user_query>do you recall the seed</user_query>"
    )
    assert any(hook.opens_with_recall(text) for text in empty_wrap)
    later_line = hook.recall_sources(
        "<user_query>fix the tests</user_query><user_query>do you recall the seed</user_query>"
    )
    assert not any(hook.opens_with_recall(text) for text in later_line)
    buried = hook.recall_sources('Fix the handler in <user_query>do you recall</user_query>.')
    assert not any(hook.opens_with_recall(text) for text in buried)
    skipped = hook.recall_sources(
        'The user asked "???" The user said "   ". THE USER ASKED "DO YOU RECALL the seed".'
    )
    assert any(hook.opens_with_recall(text) for text in skipped)
    punct = hook.recall_sources('The user asked "?!.,"')
    assert not any(hook.opens_with_recall(text) for text in punct)
    split = hook.recall_sources('The user said "do you" "recall where we left off".')
    assert not any(hook.opens_with_recall(text) for text in split)
    one_quote = hook.recall_sources('The user said "hello. do you recall the seed".')
    assert not any(hook.opens_with_recall(text) for text in one_quote)
    typed = hook.recall_sources(
        "do you recall the weights",
        {"spoken_text": "   ", "voice_transcript": None, "raw_prompt": '""'},
    )
    assert typed == ["do you recall the weights"]
    assert hook.opens_with_recall(typed[0])
    quoted_field = hook.recall_sources("fix the tests", {"spoken_text": '"do you recall the seed"'})
    assert quoted_field == ["do you recall the seed"]
    first_field = hook.recall_sources(
        "do you recall the weights",
        {"spoken_text": "hello", "user_text": "do you recall the seed"},
    )
    assert first_field == ["hello"]
    assert not any(hook.opens_with_recall(text) for text in first_field)
    assert hook.opens_with_recall("do you recall the weights")
    assert not hook.opens_with_recall("Please do you remember")


def test_empty_prompt_and_raw_field_edges() -> None:
    hook = _load()
    assert hook.recall_sources("") == []
    assert hook.recall_sources(" \n\t") == []
    assert not any(hook.opens_with_recall(text) for text in hook.recall_sources(""))
    wrapped = "<user_query>DO YOU RECALL the seed</user_query>"
    punctuation = hook.recall_sources(wrapped, {"spoken_text": "?!.,"})
    assert any(hook.opens_with_recall(text) for text in punctuation)
    assert hook.opens_with_recall("HeY, ReFrEsH yOuR mEmOrY")
    long_hit = hook.recall_sources("fix the tests", {"spoken_text": "Do You Recall " + ("x" * 8000)})
    assert any(hook.opens_with_recall(text) for text in long_hit)
    long_miss = hook.recall_sources(wrapped, {"spoken_text": "hello " + ("y" * 8000)})
    assert not any(hook.opens_with_recall(text) for text in long_miss)
    raw_wrapper = hook.recall_sources(
        "<user_query>fix the tests</user_query>",
        {"spoken_text": "<user_query>do you recall the seed</user_query>"},
    )
    assert any(hook.opens_with_recall(text) for text in raw_wrapper)
    raw_plain = hook.recall_sources(wrapped, {"spoken_text": "fix the tests"})
    assert raw_plain == ["fix the tests"]
    assert not any(hook.opens_with_recall(text) for text in raw_plain)


def test_recall_phrase_does_not_eat_the_next_word() -> None:
    hook = _load()
    assert hook.question_body("do you rememberable facts") == "do you rememberable facts"
    assert hook.question_body("do you remember_seed") == "do you remember_seed"
    assert hook.question_body("do you remember the seed") == "the seed"
    assert hook.question_body("hey, refresh your memory do you remember the seed") == "the seed"
    assert hook.question_body("do you remember") == "do you remember"


def test_main_reads_a_memory_file_and_rejects_a_blank_question(tmp_path: Path, capsys) -> None:
    hook = _load()
    memory = tmp_path / "memory.md"
    memory.write_text(MEMORY, encoding="utf-8")
    assert hook.main(["--memory", str(memory), "--seed", "1", "do you remember the seed votes"]) == 0
    assert "3, 5, 5, 4, 4, 4" in capsys.readouterr().out
    assert hook.main(["--memory", str(memory)]) == 2


def test_main_rejects_a_missing_or_non_utf8_file(tmp_path: Path, capsys) -> None:
    hook = _load()
    missing = tmp_path / "missing.md"
    assert hook.main(["--memory", str(missing), "seed"]) == 1
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"\xff\xfe seed")
    assert hook.main(["--memory", str(bad), "seed"]) == 1
    err = capsys.readouterr().err
    assert "not found" in err
    assert "UTF-8" in err


def test_main_stops_reading_past_the_byte_cap(tmp_path: Path, capsys) -> None:
    hook = _load()
    memory = tmp_path / "memory.md"
    memory.write_bytes(b"seed votes\n" + (b"x" * 40))
    hook.MAX_MEMORY_BYTES = 8
    assert hook.main(["--memory", str(memory), "seed"]) == 1
    assert "larger" in capsys.readouterr().err


def test_covered_memory_skips_the_chat_file(tmp_path: Path) -> None:
    hook = _load()
    memory = "- Seed is 3, 5, 5, 4, 4, 4.\n"
    chat = tmp_path / "chat.jsonl"
    chat.write_text('{"text": "The firmware schedule is Tuesday only in chat."}\n', encoding="utf-8")
    calls: list[str] = []
    real = hook.search_chat

    def wrapped(path, query, *, limit=2000):
        calls.append(str(path))
        return real(path, query, limit=limit)

    hook.search_chat = wrapped
    text = hook.present_recall("do you recall the seed", memory, chat)
    assert text.startswith("ANSWER FROM THE FOLLOWING RECALLED MEMORY FIRST")
    assert "secondary" in text
    assert "3, 5, 5, 4, 4, 4" in text
    assert "Tuesday" not in text
    assert calls == []


def test_short_memory_searches_chat_and_dedups(tmp_path: Path) -> None:
    hook = _load()
    memory = "- Seed is 3, 5, 5, 4, 4, 4.\n"
    chat = tmp_path / "chat.jsonl"
    chat.write_text(
        "\n".join(
            [
                json.dumps({"text": "Seed is 3, 5, 5, 4, 4, 4."}),
                json.dumps({"text": "The firmware schedule is Tuesday."}),
                json.dumps({"text": "The firmware schedule is Tuesday."}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    text = hook.present_recall("do you recall the firmware schedule", memory, chat)
    assert "SUPPORTING CHAT DETAIL" in text
    assert text.index("ANSWER FROM THE FOLLOWING RECALLED MEMORY FIRST") < text.index("SUPPORTING CHAT DETAIL")
    assert text.count("Tuesday") == 1
    assert "Seed is 9" not in text


def test_chat_conflict_keeps_the_memory_wording(tmp_path: Path) -> None:
    hook = _load()
    memory = "- Seed is 3, 5, 5, 4, 4, 4.\n"
    chat = tmp_path / "chat.jsonl"
    chat.write_text(
        "\n".join(
            [
                json.dumps({"text": "Seed is 9, 9, 9, 9, 9, 9."}),
                json.dumps({"text": "The firmware schedule is Tuesday."}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    text = hook.present_recall("do you recall the seed firmware", memory, chat)
    assert "3, 5, 5, 4, 4, 4" in text
    assert "9, 9, 9" not in text
    assert "Tuesday" in text


def test_shorter_inner_quote_does_not_replace_the_question() -> None:
    hook = _load()
    prompt = 'do you recall the seed. The user said "recall".'
    assert hook.question_text(prompt) == prompt
    assert "seed" in hook._subject_tokens(hook.question_text(prompt))
    raw = hook.question_text(
        "Trace the failure in the tab.",
        {"spoken_text": "do you recall the firmware schedule"},
    )
    assert hook._subject_tokens(raw) == ("firmware", "schedule")


def test_normalization_collapses_case_and_punctuation() -> None:
    hook = _load()
    body, kept = hook.merge_sources(
        "SEED IS 3, 5, 5, 4, 4, 4!",
        "- Seed is 3, 5, 5, 4, 4, 4.\n",
        "",
    )
    assert "3, 5, 5, 4, 4, 4" in body
    assert kept == ""


def test_chat_search_stays_within_its_limit(tmp_path: Path) -> None:
    hook = _load()
    chat = tmp_path / "chat.jsonl"
    chat.write_text(
        json.dumps({"text": "The firmware schedule is " + ("later " * 80)}) + "\n",
        encoding="utf-8",
    )
    text = hook.search_chat(chat, "do you recall the firmware schedule", limit=120)
    assert len(text) <= 120
    assert "firmware" in text


def test_conflicting_chat_only_does_not_add_a_chat_section(tmp_path: Path) -> None:
    hook = _load()
    memory = "- Seed is 3, 5, 5, 4, 4, 4.\n"
    chat = tmp_path / "chat.jsonl"
    chat.write_text(json.dumps({"text": "Seed is 9, 9, 9, 9, 9, 9."}) + "\n", encoding="utf-8")
    text = hook.present_recall("do you recall the seed firmware", memory, chat)
    assert "3, 5, 5, 4, 4, 4" in text
    assert "9, 9, 9" not in text
    assert "SUPPORTING CHAT DETAIL" not in text


def test_short_chat_does_not_force_the_memory_down_to_half(tmp_path: Path) -> None:
    hook = _load()
    marker = "ENDMARKER"
    memory = "- Seed is 3, 5, 5, 4, 4, 4. " + (marker + " ") * 40
    chat = tmp_path / "chat.jsonl"
    chat.write_text(json.dumps({"text": "The firmware schedule is Tuesday."}) + "\n", encoding="utf-8")
    text = hook.present_recall("do you recall the seed firmware", memory, chat, limit=900)
    assert marker in text
    assert "Tuesday" in text
    assert len(text) <= 900


def test_multiple_conflicts_keep_the_closer_memory_lines() -> None:
    hook = _load()
    memory = "\n".join(
        [
            "- Seed notes for the archive.",
            "- Seed is 3, 5, 5, 4, 4, 4.",
            "- The archive is on the H drive.",
        ]
    )
    chat = "\n".join(
        [
            "Seed is 9, 9, 9, 9, 9, 9.",
            "The archive is on the Z drive.",
            "The firmware schedule is Tuesday.",
        ]
    )
    body, kept = hook.merge_sources(chat, memory, "")
    assert "3, 5, 5, 4, 4, 4" in body
    assert "Seed notes" not in body
    assert "H drive" in body
    assert "9, 9, 9" not in kept
    assert "Z drive" not in kept
    assert "Tuesday" in kept


def test_very_long_memory_stays_inside_the_limit_and_skips_chat(tmp_path: Path) -> None:
    hook = _load()
    memory = "START seed marker\n" + ("x" * 30000)
    chat = tmp_path / "chat.jsonl"
    chat.write_text(json.dumps({"text": "The firmware schedule is only in chat."}) + "\n", encoding="utf-8")
    calls: list[int] = []
    real = hook.search_chat

    def wrapped(path, query, *, limit=2000):
        calls.append(1)
        return real(path, query, limit=limit)

    hook.search_chat = wrapped
    text = hook.present_recall("total recall", memory, chat, limit=500)
    assert text.startswith("ANSWER FROM THE FOLLOWING RECALLED MEMORY FIRST")
    assert "START seed marker" in text
    assert len(text) <= 500
    assert calls == []
    assert "only in chat" not in text


def test_empty_chat_file_adds_no_chat_section(tmp_path: Path) -> None:
    hook = _load()
    memory = "- Seed is 3, 5, 5, 4, 4, 4.\n"
    chat = tmp_path / "chat.jsonl"
    chat.write_text("", encoding="utf-8")
    text = hook.present_recall("do you recall the firmware schedule", memory, chat)
    assert "SUPPORTING CHAT DETAIL" not in text
    assert "No recalled passage covered this question." in text


def test_long_chat_does_not_erase_the_memory_line(tmp_path: Path) -> None:
    hook = _load()
    memory = "- Seed is 3, 5, 5, 4, 4, 4.\n"
    chat = tmp_path / "chat.jsonl"
    chat.write_text(
        json.dumps({"text": "The firmware schedule is " + ("later " * 400)}) + "\n",
        encoding="utf-8",
    )
    text = hook.present_recall("do you recall the seed firmware", memory, chat, limit=700)
    assert "3, 5, 5, 4, 4, 4" in text
    assert len(text) <= 700


def test_script_does_not_import_the_file_ranker() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "hive_planner" not in source
    assert "rank-rows.jsonl" not in source
