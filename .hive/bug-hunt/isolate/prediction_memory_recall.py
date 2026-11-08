"""Monte Carlo tree + Thompson bandit recall for one memory file.

Ad hoc helper for any composer tab in this repo. Given a recall question, it
grows a few related query branches, treats those branches as bandit arms, and
samples which passages of docs/specs/bug-hunt/TEMP-prediction-memory.md to
return. It does not rank source files and it does not read rank-rows.

Run: py -3.11 .cursor/hooks/prediction_memory_recall.py "do you remember the seed"
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

MEMORY_REL = Path("docs/specs/bug-hunt/TEMP-prediction-memory.md")
CONTEXT_LIMIT = 10000
MAX_MEMORY_BYTES = 2_000_000
SIMULATIONS = 24
MAX_DEPTH = 2
BRANCHES = 4
DRAWS = 16
UCB_C = 1.2

_TOKEN = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*")
_RECALL_PREFIXES = (
    "hey, refresh your memory",
    "hey refresh your memory",
    "do you remember",
)
# Start-of-call only. Frozen after one capped expansion (depth 1, 4 walks,
# 2 branches). The trigger check is this list; it does not run the tree.
START_RECALL_PHRASES = (
    "hey, refresh your memory",
    "hey refresh your memory",
    "refresh your memory",
    "hey do you recall",
    "do you remember",
    "can you recall",
    "please recall",
    "refresh memory",
    "total recall",
    "do you recall",
    "full recall",
    "recall",
)
_STOP = frozenset(
    """
    a an the of to and or in on for is it this that with as by be not from at
    are was were be been being do does did if then than into over only own
    """.split()
)


@dataclass
class Part:
    text: str
    tokens: tuple[str, ...]


@dataclass
class Node:
    tokens: tuple[str, ...]
    parent: Node | None = None
    children: list[Node] = field(default_factory=list)
    untried: list[str] = field(default_factory=list)
    visits: int = 0
    reward: float = 0.0
    match: float = 0.0
    depth: int = 0

    @property
    def expanded(self) -> bool:
        return not self.untried


def question_body(query: str) -> str:
    """Drop a leading recall phrase so the search follows the subject, not the command.

    The phrase must end on a word boundary. Casefolding that changes length is
    left intact, because slicing the original text by the folded length would
    cut the subject in the wrong place.
    """
    text = " ".join(query.split())
    while True:
        folded = text.casefold()
        if len(folded) != len(text):
            return text
        rest = None
        for prefix in _RECALL_PREFIXES:
            if not folded.startswith(prefix):
                continue
            boundary = folded[len(prefix)] if len(folded) > len(prefix) else ""
            if boundary.isalnum() or boundary in "._-":
                continue
            rest = text[len(prefix) :].lstrip(" ,.!:;?-")
            break
        if rest is None or not rest:
            return text
        text = rest


_INNER_QUERY = re.compile(
    r"<user_query>((?:(?!</?user_query>).)*)</user_query>",
    re.DOTALL | re.IGNORECASE,
)
_TIMESTAMP = re.compile(r"<timestamp>.*?</timestamp>", re.DOTALL | re.IGNORECASE)
# Verbs the voice pipeline uses to introduce the spoken line. "wrote" and a bare
# quotation are not spoken-line labels.
_SPOKEN = re.compile(
    r"""(?<![\w])(?:the\s+)?(?:user|caller)\s+(?:said|asked|told|mentioned|replied|stated)\s+["“]([^"”]+)["”]""",
    re.IGNORECASE,
)
_RAW_TEXT_KEYS = ("spoken_text", "voice_transcript", "raw_prompt", "raw_user_text", "user_text")


_QUOTE_PAIRS = {'"': '"', "'": "'", "“": "”"}


def _unwrap_raw(value: object) -> str | None:
    """The first usable spoken field. Whitespace, quotes, and punctuation are empty."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) >= 2 and _QUOTE_PAIRS.get(text[0]) == text[-1]:
        text = text[1:-1].strip()
    if not any(ch.isalnum() for ch in text):
        return None
    return text


def _raw_fields(extra: object) -> list[str]:
    """Only the first non-empty raw field. A later field cannot override it."""
    if not isinstance(extra, dict):
        return []
    for key in _RAW_TEXT_KEYS:
        text = _unwrap_raw(extra.get(key))
        if text:
            return [text]
    return []


def _strip_timestamp(text: str) -> str:
    return _TIMESTAMP.sub(" ", text).strip()


def _innermost_queries(prompt: str) -> list[str]:
    """Innermost ``<user_query>`` bodies inside one message."""
    bodies: list[str] = []
    text = prompt
    while True:
        match = _INNER_QUERY.search(text)
        if match is None:
            return bodies
        bodies.append(match.group(1))
        text = text[: match.start()] + text[match.end() :]


def _read_query_body(text: str) -> str | None:
    """Body of a ``<user_query>`` at the start of ``text``, or None when unclosed."""
    open_tag = "<user_query>"
    close_tag = "</user_query>"
    if not text.lower().startswith(open_tag):
        return None
    depth = 1
    i = len(open_tag)
    folded = text.lower()
    while i < len(text):
        next_open = folded.find(open_tag, i)
        next_close = folded.find(close_tag, i)
        if next_close < 0:
            return None
        if next_open != -1 and next_open < next_close:
            depth += 1
            i = next_open + len(open_tag)
            continue
        depth -= 1
        if depth == 0:
            return text[len(open_tag) : next_close]
        i = next_close + len(close_tag)
    return None


def _first_wrapped_message(prompt: str) -> str | None:
    """The first non-empty ``<user_query>`` when the prompt itself is that wrapper.

    A tag mentioned later in a typed prompt is not a spoken line.
    """
    text = _strip_timestamp(prompt).lstrip()
    open_tag = "<user_query>"
    close_tag = "</user_query>"
    if not text.lower().startswith(open_tag):
        return None
    while text.lower().startswith(open_tag):
        body = _read_query_body(text)
        if body is None:
            remainder = text[len(open_tag) :].strip()
            return remainder or None
        if body.strip():
            return body
        end = text.lower().find(close_tag)
        text = text[end + len(close_tag) :].lstrip()
    return None


def _without_query_tags(text: str) -> str:
    return re.sub(r"</?user_query>", " ", text, flags=re.IGNORECASE)


def _first_spoken(text: str) -> str | None:
    """The first word-bearing quote after a spoken-line label.

    A blank or punctuation-only quote is not a spoken line, so a later label
    can still be that line. The first quote that contains a word ends the search.
    """
    for match in _SPOKEN.finditer(text):
        spoken = match.group(1).strip()
        if spoken and any(ch.isalnum() for ch in spoken):
            return spoken
    return None


def _sources_from_message(text: str) -> list[str]:
    wrapped = _first_wrapped_message(text)
    if wrapped is not None:
        sources = [_strip_timestamp(_without_query_tags(wrapped))]
        sources.extend(
            _strip_timestamp(body) for body in _innermost_queries(wrapped) if body.strip()
        )
        quote = _first_spoken(wrapped)
        if quote:
            sources.append(quote)
        return [item for item in sources if item.strip()]
    cleaned = _strip_timestamp(text)
    if not cleaned:
        return []
    sources = [cleaned]
    quote = _first_spoken(cleaned)
    if quote:
        sources.append(quote)
    return sources


def recall_sources(prompt: str, extra: object = None) -> list[str]:
    """Texts whose start may be the user's own words.

    The first raw field that contains a word is the whole source. Punctuation,
    blanks, and a later field do not override it. A raw field that is itself a
    ``<user_query>`` wrapper is unwrapped before the start check. A typed prompt
    is matched only at its own start, plus one spoken-line quotation
    ("the user said", "the user asked", or the same kind of label) when
    the voice rewrite has no wrapper.
    """
    raw = _raw_fields(extra)
    if raw:
        text = raw[0]
        if _first_wrapped_message(text) is not None:
            return _sources_from_message(text)
        stripped = _strip_timestamp(text).strip()
        if stripped:
            return [stripped]
    if not isinstance(prompt, str) or not prompt.strip():
        return []
    return _sources_from_message(prompt)


def opens_with_recall(prompt: str) -> bool:
    """True when the message starts with a recall phrase.

    A later mention does not match. The phrase must end on a word boundary,
    so ``recall`` does not match ``recallable``.
    """
    folded = " ".join(prompt.split()).casefold()
    phrases = sorted(START_RECALL_PHRASES, key=len, reverse=True)
    for prefix in phrases:
        if not folded.startswith(prefix):
            continue
        if _phrase_closed(folded, len(prefix)):
            return True
    return False


def _phrase_closed(folded: str, end: int) -> bool:
    """True when the phrase ends, including before a period that is not part of a token."""
    if end >= len(folded):
        return True
    nxt = folded[end]
    if nxt.isalnum() or nxt in "_-":
        return False
    if nxt == "." and folded[end + 1 : end + 2].isalnum():
        return False
    return True


def tokenize(text: str) -> tuple[str, ...]:
    """Keep words and single digits. The seed votes are one character each."""
    found = [
        tok
        for tok in _TOKEN.findall(text.casefold())
        if tok not in _STOP and (len(tok) >= 2 or tok.isdigit())
    ]
    return tuple(dict.fromkeys(found))


def parts_of(memory: str) -> list[Part]:
    """Bullets and paragraphs. HTML comments and blank lines are not passages."""
    if memory.startswith("\ufeff"):
        memory = memory[1:]
    parts: list[Part] = []
    paragraph: list[str] = []
    in_comment = False

    def flush_paragraph() -> None:
        if not paragraph:
            return
        text = " ".join(paragraph).strip()
        paragraph.clear()
        if text:
            tokens = tokenize(text)
            if tokens:
                parts.append(Part(text, tokens))

    for raw in memory.splitlines():
        line = raw.strip()
        if in_comment:
            if "-->" not in line:
                continue
            in_comment = False
            line = line.split("-->", 1)[1].strip()
            if not line:
                continue
        while line.startswith("<!--"):
            flush_paragraph()
            if "-->" not in line:
                in_comment = True
                line = ""
                break
            line = line.split("-->", 1)[1].strip()
        if not line or line.startswith("#"):
            flush_paragraph()
            continue
        if line.startswith("- "):
            flush_paragraph()
            text = line[2:].strip()
            tokens = tokenize(text)
            if text and tokens:
                parts.append(Part(text, tokens))
            continue
        paragraph.append(line)
    flush_paragraph()
    return parts


def _index(parts: list[Part]) -> dict[str, set[int]]:
    index: dict[str, set[int]] = {}
    for number, part in enumerate(parts):
        for token in part.tokens:
            index.setdefault(token, set()).add(number)
    return index


def f1(query: tuple[str, ...], part: tuple[str, ...]) -> float:
    if not query or not part:
        return 0.0
    overlap = len(set(query) & set(part))
    if overlap == 0:
        return 0.0
    recall = overlap / len(set(query))
    precision = overlap / len(set(part))
    return 2 * recall * precision / (recall + precision)


def related_tokens(query: tuple[str, ...], parts: list[Part], index: dict[str, set[int]]) -> list[str]:
    """Tokens that share a passage with the query, ranked by alignment then rarity."""
    if not query or not parts:
        return []
    qset = set(query)
    related_parts: set[int] = set()
    for token in qset:
        related_parts |= index.get(token, set())
    counts: dict[str, int] = {}
    for number in related_parts:
        seen = set(parts[number].tokens)
        aligned = len(seen & qset)
        if aligned == 0:
            continue
        for token in seen:
            if token in qset:
                continue
            counts[token] = counts.get(token, 0) + aligned
    total = max(1, len(parts))
    ranked = sorted(
        counts,
        key=lambda token: (counts[token] * math.log((total + 1) / (len(index[token]) + 1)), counts[token]),
        reverse=True,
    )
    return ranked


def _best_f1(query: tuple[str, ...], parts: list[Part]) -> float:
    if not parts:
        return 0.0
    return max(f1(query, part.tokens) for part in parts)


def _ucb(node: Node) -> float:
    if node.visits == 0 or node.parent is None:
        return math.inf
    parent_visits = max(1, node.parent.visits)
    exploit = node.reward / node.visits
    explore = UCB_C * math.sqrt(math.log(parent_visits) / node.visits)
    return exploit + explore


def search_branches(query: str, parts: list[Part], rng: random.Random) -> list[Node]:
    """Grow related query branches. Unrelated tokens are never added."""
    root = Node(tokens=tokenize(question_body(query)))
    index = _index(parts)
    root.match = _best_f1(root.tokens, parts)
    root.untried = related_tokens(root.tokens, parts, index)[:BRANCHES]
    if not root.tokens and not root.untried:
        return [root]

    for _ in range(SIMULATIONS):
        node = root
        while node.expanded and node.children:
            node = max(node.children, key=_ucb)
        if node.untried and node.depth < MAX_DEPTH:
            token = node.untried.pop(0)
            if token not in node.tokens:
                child_tokens = node.tokens + (token,)
                child = Node(
                    tokens=child_tokens,
                    parent=node,
                    depth=node.depth + 1,
                    match=_best_f1(child_tokens, parts),
                )
                child.untried = [
                    item
                    for item in related_tokens(child_tokens, parts, index)
                    if item not in child_tokens
                ][:BRANCHES]
                node.children.append(child)
                node = child
        reward = _best_f1(node.tokens, parts)
        while node is not None:
            node.visits += 1
            node.reward += reward
            node = node.parent

    branches = [node for node in _walk(root) if node.visits > 0]
    if not branches:
        branches = [root]
    rng.shuffle(branches)
    return branches


def _walk(node: Node) -> list[Node]:
    found = [node]
    for child in node.children:
        found.extend(_walk(child))
    return found


def _posterior(node: Node) -> tuple[float, float]:
    """Confidence comes from visits. The mean is this branch's own match.

    Backed-up reward is for tree selection. Using it here would score the
    original question as the average of its expansions.
    """
    if node.visits <= 0:
        return 1.0, 1.0
    mean = min(1.0, max(0.0, node.match))
    alpha = 1.0 + mean * node.visits
    beta = 1.0 + (1.0 - mean) * node.visits
    return alpha, beta


def select_parts(
    branches: list[Node],
    parts: list[Part],
    rng: random.Random,
    *,
    limit: int = CONTEXT_LIMIT,
) -> list[Part]:
    """Thompson-sample branches, then keep passages in proportion to those draws."""
    if not parts or not branches:
        return []
    wins = [0 for _ in branches]
    for _ in range(DRAWS):
        samples = [rng.betavariate(*_posterior(branch)) for branch in branches]
        wins[max(range(len(samples)), key=samples.__getitem__)] += 1
    mass = [count / DRAWS for count in wins]
    scores = [0.0 for _ in parts]
    for branch, probability in zip(branches, mass):
        if probability <= 0:
            continue
        raw = [f1(branch.tokens, part.tokens) for part in parts]
        total = sum(raw)
        if total <= 0:
            continue
        for number, raw_score in enumerate(raw):
            scores[number] += probability * (raw_score / total)
    order = sorted(range(len(parts)), key=lambda number: scores[number], reverse=True)
    best = scores[order[0]] if order else 0.0
    if best <= 0:
        return []
    chosen: list[Part] = []
    joined = 0
    seen: set[str] = set()
    for number in order:
        if scores[number] < best * 0.25:
            break
        text = parts[number].text
        if text in seen:
            continue
        separator = 1 if chosen else 0
        room = limit - joined - separator
        if room <= 0:
            break
        if len(text) > room:
            if chosen:
                continue
            text = text[:room]
        chosen.append(Part(text, parts[number].tokens))
        seen.add(parts[number].text)
        joined += separator + len(text)
    return chosen


def recall(query: str, memory: str, *, seed: int = 0, limit: int = CONTEXT_LIMIT) -> str:
    """Return memory passages for this question. Empty when nothing aligns."""
    text = " ".join(query.split())
    if not text:
        return ""
    parts = parts_of(memory)
    if not parts:
        return ""
    # Command words stay in the spoken line for the trigger check. The tree
    # follows the subject, so "total recall the seed" searches "seed".
    subject = _subject_tokens(text)
    search = " ".join(subject) if subject else text
    rng = random.Random(seed)
    branches = search_branches(search, parts, rng)
    chosen = select_parts(branches, parts, rng, limit=limit)
    return "\n".join(part.text for part in chosen)


# A passage covers the question only when every subject word is in it.
COVERAGE_THRESHOLD = 1.0
CHAT_READ_CAP = 1_000_000
PRIMARY_LEAD = (
    "ANSWER FROM THE FOLLOWING RECALLED MEMORY FIRST. "
    "These passages are the authoritative source for this turn. "
    "Conversation context is secondary: use it only when the recalled passages "
    "do not cover the question.\n\n"
)
CHAT_LEAD = (
    "\n\nSUPPORTING CHAT DETAIL. Searched because recalled memory did not cover "
    "the question. Not a competing answer. On a conflict, the memory file wins.\n"
)


def _trigger_tokens() -> frozenset[str]:
    return frozenset(tokenize(" ".join(START_RECALL_PHRASES)))


def _subject_tokens(query: str) -> tuple[str, ...]:
    """Words that name the subject, after the recall command is removed."""
    trigger = _trigger_tokens()
    return tuple(tok for tok in tokenize(question_body(query)) if tok not in trigger)


def question_text(prompt: str, extra: object = None) -> str:
    """The raw spoken line when the voice rewrite only quotes it.

    A prompt that already opens with a recall phrase keeps that subject. A
    shorter quotation inside it must not replace the question.
    """
    raw = [item for item in _raw_fields(extra) if opens_with_recall(item)]
    if raw:
        return raw[0]
    if opens_with_recall(prompt):
        return prompt
    spoken = [item for item in recall_sources(prompt) if opens_with_recall(item)]
    if not spoken:
        return prompt
    return min(spoken, key=len)


def coverage_score(query: str, memory: str, passages: str) -> float:
    """1 when a bare recall has no subject. 0 when the subject is missing from the file or the passages."""
    subject = _subject_tokens(query)
    if not subject:
        return 1.0
    if not set(subject) <= set(tokenize(memory)):
        return 0.0
    if not passages.strip():
        return 0.0
    return len(set(subject) & set(tokenize(passages))) / len(subject)


def memory_covers(query: str, memory: str, passages: str) -> bool:
    return coverage_score(query, memory, passages) >= COVERAGE_THRESHOLD


def _norm(text: str) -> str:
    return " ".join(_TOKEN.findall(text.casefold()))


def _same_fact(chat_line: str, memory_line: str) -> bool:
    chat_norm = _norm(chat_line)
    memory_norm = _norm(memory_line)
    if not chat_norm or not memory_norm:
        return False
    if chat_norm == memory_norm:
        return True
    chat_tokens = set(tokenize(chat_line))
    memory_tokens = set(tokenize(memory_line))
    if not chat_tokens or not memory_tokens:
        return False
    return len(chat_tokens & memory_tokens) / len(chat_tokens) >= 0.5


def _best_memory_line(chat_line: str, memory_lines: list[str]) -> str | None:
    """The memory line that restates this chat line. Ties prefer the closer wording."""
    best: str | None = None
    best_score = -1.0
    chat_norm = _norm(chat_line)
    chat_tokens = set(tokenize(chat_line))
    for item in memory_lines:
        if not _same_fact(chat_line, item):
            continue
        overlap = len(chat_tokens & set(tokenize(item)))
        score = overlap - abs(len(chat_norm) - len(_norm(item))) / 1000
        if score > best_score:
            best = item
            best_score = score
    return best


def merge_sources(chat_text: str, memory_text: str, shown: str) -> tuple[str, str]:
    """Collapse a repeated fact. A conflicting chat line loses to the memory line."""
    memory_lines = [line.strip() for line in memory_text.splitlines() if line.strip()]
    shown_norms = {_norm(line) for line in shown.splitlines() if _norm(line)}
    extra: list[str] = []
    kept: list[str] = []
    seen = set(shown_norms)
    for line in chat_text.splitlines():
        stripped = line.strip()
        if not _norm(stripped):
            continue
        match = _best_memory_line(stripped, memory_lines)
        if match is not None:
            folded = _norm(match)
            if folded and folded not in shown_norms:
                extra.append(match)
                shown_norms.add(folded)
            continue
        folded = _norm(stripped)
        if folded in seen:
            continue
        kept.append(stripped)
        seen.add(folded)
    body = shown.strip()
    if extra:
        body = (body + "\n" + "\n".join(extra)).strip()
    return body, "\n".join(kept)


def _json_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_json_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_json_text(item) for item in value)
    return ""


def search_chat(path: Path, query: str, *, limit: int = 2000) -> str:
    """Passages from a chat transcript that share a subject word. Empty when the file is missing."""
    if not path.is_file():
        return ""
    subject = set(_subject_tokens(query))
    if not subject:
        return ""
    try:
        blob = path.read_bytes()[-CHAT_READ_CAP:]
    except OSError:
        return ""
    text = blob.decode("utf-8", errors="ignore")
    if blob and not text.startswith("{") and "\n" in text:
        text = text.split("\n", 1)[1]
    hits: list[tuple[float, str]] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        chunk = raw.strip()
        if chunk.startswith("{"):
            try:
                chunk = _json_text(json.loads(chunk))
            except json.JSONDecodeError:
                pass
        for line in chunk.splitlines():
            stripped = " ".join(line.split())
            folded = _norm(stripped)
            if not folded or folded in seen:
                continue
            tokens = set(tokenize(stripped))
            if not tokens:
                continue
            score = len(subject & tokens) / len(subject)
            if score <= 0:
                continue
            seen.add(folded)
            hits.append((score, stripped))
    hits.sort(key=lambda item: item[0], reverse=True)
    chosen: list[str] = []
    used = 0
    for _score, line in hits:
        room = limit - used - (1 if chosen else 0)
        if room <= 0:
            break
        if len(line) > room:
            line = line[:room]
        chosen.append(line)
        used += len(line) + (1 if len(chosen) > 1 else 0)
    return "\n".join(chosen)


def _fit(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def present_recall(
    query: str,
    memory: str,
    transcript: str | Path | None = None,
    *,
    limit: int = CONTEXT_LIMIT,
    seed: int = 0,
    extra: object = None,
) -> str:
    """Memory passages first. The chat transcript is read only when they do not cover the question."""
    question = question_text(query, extra)
    subject = _subject_tokens(question)
    if not subject:
        body = memory.strip()
        chat = ""
    else:
        body = recall(question, memory, seed=seed, limit=limit).strip()
        chat = ""
        if not memory_covers(question, memory, body):
            if isinstance(transcript, str):
                path = Path(transcript) if transcript.strip() else None
            elif isinstance(transcript, Path):
                path = transcript
            else:
                path = None
            found = "" if path is None else search_chat(path, question)
            body, chat = merge_sources(found, memory, body)
    if not body:
        body = "No recalled passage covered this question."
    body_room = max(0, limit - len(PRIMARY_LEAD))
    if not chat.strip() or body_room <= len(CHAT_LEAD) + 1:
        return PRIMARY_LEAD + _fit(body, body_room)
    # A short chat keeps only the room it needs. A long chat stops at half,
    # so it cannot push the memory passage out.
    chat_text = chat.strip()
    chat_budget = min(len(chat_text), max(0, (body_room // 2) - len(CHAT_LEAD)))
    if chat_budget <= 0:
        return PRIMARY_LEAD + _fit(body, body_room)
    body_fit = _fit(body, body_room - len(CHAT_LEAD) - chat_budget)
    left = body_room - len(body_fit) - len(CHAT_LEAD)
    if left <= 0:
        return PRIMARY_LEAD + _fit(body, body_room)
    return PRIMARY_LEAD + body_fit + CHAT_LEAD + _fit(chat_text, left)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recall passages from the prediction memory file.")
    parser.add_argument("query", nargs="*", help="What to recall")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--memory", type=Path, default=None)
    args = parser.parse_args(argv)
    question = " ".join(args.query).strip()
    if not question:
        print("Pass a recall question.", file=sys.stderr)
        return 2
    repo = Path(__file__).resolve().parents[2]
    path = args.memory if args.memory is not None else repo / MEMORY_REL
    if not path.is_file():
        print(f"Memory file not found: {path}", file=sys.stderr)
        return 1
    try:
        with path.open("rb") as handle:
            blob = handle.read(MAX_MEMORY_BYTES + 1)
    except OSError as exc:
        print(f"Memory file could not be read: {exc}", file=sys.stderr)
        return 1
    if len(blob) > MAX_MEMORY_BYTES:
        print(f"Memory file is larger than {MAX_MEMORY_BYTES} bytes: {path}", file=sys.stderr)
        return 1
    try:
        raw = blob.decode("utf-8-sig")
    except UnicodeDecodeError:
        print(f"Memory file is not UTF-8: {path}", file=sys.stderr)
        return 1
    text = present_recall(question, raw, seed=args.seed)
    payload = (text + "\n").encode("utf-8", errors="replace")
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(payload.decode("utf-8"))
    else:
        buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
