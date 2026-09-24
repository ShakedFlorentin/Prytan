"""
relevance.py — shared tokenizer + the relevance gate for prompt-time memory recall.

The memo hook used to inject the top-N memories on EVERY prompt, ranked by
recency/category with no floor: one shared word (or none) was enough, so
unrelated memories rode along with every question. The gate here decides
whether a memory is about the prompt at all before it is ranked:

  • coverage — the memory must contain >= MIN_COVERAGE of the prompt's content
    words, IDF-weighted over the candidate pool, so a rare token ("argon2",
    "auth_v2") counts far more than a common one ("fix", "report").
  • at least MIN_MATCHES distinct prompt words must match.
  • whole-word matching: "fix" does not match "prefix". A word may be part of an
    identifier ("retry" in MAX_RETRY, "python" in python3.13) and may
    carry a common ending ("block" matches "blocked").
  • at least one matched word must be rare in the pool, so a memory that only
    shares everyday words with the prompt never passes.

tokenize() is the one tokenizer shared by prompt-time recall and explicit
`recall()` (core/knowledge/memory/store.py), so both agree on what a "word"
and a stopword are.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

MIN_COVERAGE = 0.6
MIN_MATCHES = 2
# Ranking (not gating) penalty per tier, so a curated memory that covers a bit
# less of the prompt still outranks a long log that happens to mention it all.
TIER_PENALTY = 0.05
# Ranking bonus for the share of prompt weight found in the title/description:
# a memory ABOUT the topic names it up front; a log that merely mentions it doesn't.
TITLE_BONUS = 0.3
# Long, uncurated text (logs, handoffs, chatter: tier >= UNCURATED_TIER) mentions
# many everyday words in passing. It must name a prompt word in its title or
# cover UNCURATED_COVERAGE of the prompt to pass.
UNCURATED_TIER = 2
UNCURATED_COVERAGE = 0.75
# Long prompts carry incidental words, so the coverage bar drops by LONG_STEP per
# content word beyond LONG_FROM, never below LONG_FLOOR.
LONG_FROM = 5
LONG_STEP = 0.03
LONG_FLOOR = 0.45
# At least one matched word must be rare: in no more than this share of the pool
# (floor RARE_MIN_DF docs). Two common words ("write", "report") both appearing
# in a memory is coincidence, not topic.
RARE_FRACTION = 0.04
RARE_MIN_DF = 3

# Unicode-aware so non-English prompts tokenize too. Hyphens and punctuation split
# words; underscores stay inside identifiers (auth_v2, MAX_RETRIES).
_TOKEN = re.compile(r"[^\W_][\w]*", re.UNICODE)
# Ticket-style ids (GATE-1, JIRA-39, DEV-36) are kept whole as well: split, they
# degrade to "gate"/"jira" — common words — and the number is dropped.
_FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n?", re.DOTALL)
_APOSTROPHE = re.compile(r"(?<=[^\W\d_])['’](?=[^\W\d_])")
_TICKET = re.compile(r"(?<![\w-])[^\W\d_]+-\d+(?![\w-])", re.UNICODE)

STOPWORDS = frozenset(
    {
        # English function words
        "a", "an", "the", "and", "or", "but", "if", "then", "else", "of", "to", "in", "on",
        "at", "by", "for", "with", "from", "into", "onto", "over", "under", "about", "as",
        "is", "are", "was", "were", "be", "been", "being", "am", "do", "does", "did", "done",
        "have", "has", "had", "having", "will", "would", "should", "could", "can", "may",
        "might", "must", "shall", "not", "no", "yes", "so", "too", "very", "just", "also",
        "than", "that", "this", "these", "those", "there", "here", "it", "its", "it's",
        "i", "me", "my", "we", "us", "our", "you", "your", "he", "she", "his", "her",
        "they", "them", "their", "what", "which", "who", "whom", "whose", "when", "where",
        "why", "how", "all", "any", "some", "each", "every", "both", "either", "neither",
        "one", "two", "now", "out", "up", "down", "off", "again", "still", "only", "own",
        "same", "other", "such", "more", "most", "less", "much", "many", "few", "like",
        "let", "get", "got", "make", "made", "need", "want", "don't", "dont", "doesn't",
        "can't", "cant", "won't", "isn't", "im", "i'm", "ok", "okay", "please", "thanks",
        "thank", "hi", "hey", "well", "really", "actually", "maybe", "via", "etc", "per",
        # chat filler that carries no topic
        "tell", "show", "look", "see", "check", "think", "know", "thing", "things", "stuff",
        "something", "anything", "everything", "way", "use", "using", "used",
        "continue", "resume", "left", "where", "back", "go", "going", "keep", "start",
        "again", "next", "last", "yet", "already", "sure", "right", "good", "great",
        "him", "lets", "later", "leave", "order", "ones", "gonna", "wanna", "yo", "once",
        "until",
        # contractions, after tokenize() drops the apostrophe
        "dont", "didnt", "doesnt", "isnt", "wasnt", "arent", "werent", "wont", "cant",
        "shouldnt", "couldnt", "wouldnt", "havent", "hasnt", "ive", "youre", "thats",
        "whats", "theres", "hes", "shes", "theyre", "weve", "ill", "youll", "id",
    }
)


def tokenize(text: str, min_len: int = 2) -> list[str]:
    """Lower-cased content words: punctuation and stopwords stripped. Numbers stay
    ("48 files" is specific); IDF already discounts common ones like years.
    Order and repeats are preserved (callers that want a set take one)."""
    # "don't" / "don’t" → "dont": one stopword, not a stray "don" content word.
    low = _APOSTROPHE.sub("", text.lower())
    out = _TICKET.findall(low)
    for w in _TOKEN.findall(low):
        if len(w) < min_len or w in STOPWORDS:
            continue
        out.append(w)
    return out


@dataclass
class Candidate:
    """One recallable memory, whatever its source."""

    id: str
    text: str  # searchable body (already capped by the loader)
    source: str  # memory | handoffs | inbox | proposals | logs | conversation
    title: str = ""
    path: str = ""
    author: str = ""
    tier: int = 5  # tie-break: lower = more curated
    lower: str = field(default="", repr=False)
    title_lower: str = field(default="", repr=False)
    _passages: list = field(default=None, repr=False)

    def __post_init__(self):
        self.title_lower = self.title.lower()
        self.lower = (self.title + "\n" + self.text).lower()

    def passages(self) -> list[str]:
        """The body cut into ~PASSAGE_CHARS chunks on paragraph/line boundaries.
        Fixed per document (not per prompt) so their embeddings can be cached."""
        if self._passages is None:
            self._passages = _chunk(_FRONTMATTER.sub("", self.text, count=1))
        return self._passages


PASSAGE_CHARS = 600


HEADING_CHARS = 150  # a paragraph this short (a heading, a label) joins the next


def _chunk(text: str) -> list[str]:
    """Passages = paragraphs. Separate paragraphs are separate entries (a journal's
    days, a log's steps), so they are never merged — merging would let words from
    unrelated entries count as "together" again. A short paragraph (heading) is
    glued to the paragraph after it; a paragraph over PASSAGE_CHARS is split on
    line boundaries."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, carry = [], ""
    for para in paras:
        para = f"{carry}\n{para}" if carry else para
        carry = ""
        if len(para) < HEADING_CHARS:
            carry = para
            continue
        if len(para) <= PASSAGE_CHARS:
            chunks.append(para)
            continue
        cur = ""
        for line in para.splitlines():
            line = line[:PASSAGE_CHARS]
            if cur and len(cur) + len(line) + 1 > PASSAGE_CHARS:
                chunks.append(cur)
                cur = line
            else:
                cur = f"{cur}\n{line}" if cur else line
        if cur:
            chunks.append(cur)
    if carry:
        chunks.append(carry)
    return chunks or [""]


_SUFFIXES = "(?:s|es|e|ed|d|ing|er|ers|ion|ions)?"


def stem(term: str) -> str:
    """Light suffix stripping so "blocked"/"blocking"/"blocks" share "block".
    Deliberately crude: it only has to make a prompt word and a memory word meet;
    _pattern() re-adds the common endings on the document side. Words of four
    letters or fewer are kept whole (_pattern still lets them take a plural)."""
    if not term.isalpha() or len(term) <= 4:
        return term
    if term.endswith("ies") and len(term) > 5:
        return term[:-3] + "y"  # retries → retry
    if term.endswith("ied") and len(term) > 5:
        return term[:-3] + "y"  # retried → retry
    for suf in ("ing", "ed", "es", "s"):
        if term.endswith(suf) and len(term) - len(suf) >= 3:
            if suf == "s" and term.endswith(("ss", "us", "is")):
                return term
            base = term[: -len(suf)]
            if suf in ("ing", "ed") and len(base) > 3 and base[-1] == base[-2]:
                base = base[:-1]  # running → run, stopped → stop
            return base
    if term.endswith("e") and len(term) > 4:
        return term[:-1]  # save → sav, matches save/saved/saving
    return term


def _literal(term: str) -> str:
    """The fixed prefix every form of `term` starts with (substring pre-screen)."""
    if not term.isalpha():
        return term
    st = stem(term) if len(term) > 4 else term
    return st[:-1] if len(term) > 4 and st.endswith("y") and len(st) > 3 else st


def _pattern(term: str) -> re.Pattern:
    """Whole-word match for one prompt word, with two relaxations:

    • identifier parts: a word may sit inside an identifier as long as it does
      not continue into more LETTERS — "python" matches "python3.13", "retry"
      matches "max_retry", "auth" matches "auth_v2"; "fix" still never
      matches "prefix" or "fixture".
    • word forms: alphabetic words match with common endings ("block" matches
      "blocked", "blocks", "blocking").
    """
    first, last = term[0], term[-1]
    before = r"(?<![^\W\d_])" if not first.isdigit() else r"(?<![^\W_])"
    if term.isalpha() and len(term) > 4:
        st = stem(term)
        if st.endswith("y") and len(st) > 3:  # retry ~ retries, retried, retrying
            body = re.escape(st[:-1]) + "(?:y|ies|ied|ying|ys)"
        else:
            body = re.escape(st) + _SUFFIXES
        after = r"(?![^\W\d_])"
    elif term.isalpha() and len(term) >= 3:  # short words: plural only (cap ~ caps)
        body = re.escape(term) + "(?:s|es)?"
        after = r"(?![^\W\d_])"
    else:
        body = re.escape(term)
        after = r"(?![^\W\d_])" if not last.isdigit() else r"(?!\d)"
    return re.compile(before + body + after)


def _matches(pool: list[Candidate], terms: set[str]) -> list[set[str]]:
    """Prompt words found in each candidate (see _pattern for what counts). A plain
    substring test on the stem screens first (cheap); only substring hits pay for
    the regex, so documents are never tokenized at prompt time."""
    pats = {t: _pattern(t) for t in terms}
    keys = {t: _literal(t) for t in terms}
    found = []
    for c in pool:
        found.append({t for t in terms if keys[t] in c.lower and pats[t].search(c.lower)})
    return found


def idf_weights(terms: set[str], found: list[set[str]]) -> tuple[dict, dict]:
    """(idf, df) of each prompt term over the pool. A term that appears in no
    candidate still gets the maximum weight — it is part of what the prompt is
    about, so a memory that lacks it has not covered the prompt."""
    n = len(found)
    df = {t: 0 for t in terms}
    for hit in found:
        for t in hit:
            df[t] += 1
    return {t: math.log((n + 1) / (df[t] + 1)) + 1.0 for t in terms}, df


def score(
    prompt: str,
    pool: list[Candidate],
    min_coverage: float = MIN_COVERAGE,
    min_matches: int = MIN_MATCHES,
) -> list[tuple[float, Candidate, list[str]]]:
    """Candidates that pass the lexical gate, best first, as (coverage, candidate,
    matched)."""
    return [(r.coverage, r.c, r.matched) for r in _ranked(prompt, pool, min_coverage, min_matches)
            if r.strict]


# Candidate generation for the semantic check is looser than the lexical gate:
# the embedding decides relevance, so words only have to make a memory plausible.
CANDIDATE_COVERAGE = 0.35


@dataclass
class _Ranked:
    coverage: float
    c: Candidate
    matched: list[str]
    rank: float
    passage: str
    strict: bool  # passes the full lexical gate on its own


def _ranked(
    prompt: str,
    pool: list[Candidate],
    min_coverage: float = MIN_COVERAGE,
    min_matches: int = MIN_MATCHES,
    loose: bool = False,
) -> list[_Ranked]:
    """Lexically plausible candidates, best first.

    Coverage is measured on the candidate's best PASSAGE (plus its title), not on
    the whole document: a 4000-char journal "covers" any everyday prompt if its
    words may be scattered across unrelated entries. `strict` marks candidates
    that pass the full lexical gate; with loose=True, weaker candidates (for the
    semantic check to judge) are returned too.

    Rank orders the passes: coverage, plus a bonus for prompt words in the title,
    minus a small per-tier penalty so a curated memory file outranks a standup or
    sprint plan with the same words.
    """
    terms = set(tokenize(prompt))
    floor_matches = 1 if loose else min_matches
    if len(terms) < floor_matches or not pool:
        return []
    found = _matches(pool, terms)
    weights, df = idf_weights(terms, found)
    rare_df = max(RARE_MIN_DF, int(len(pool) * RARE_FRACTION))
    total = sum(weights.values())
    bar = max(min(min_coverage, LONG_FLOOR),
              min_coverage - LONG_STEP * max(0, len(terms) - LONG_FROM))
    floor = min(bar, CANDIDATE_COVERAGE) if loose else bar
    pats = {t: _pattern(t) for t in terms}
    out = []
    for c, doc_matched in zip(pool, found):
        if len(doc_matched) < floor_matches:
            continue
        if sum(weights[t] for t in doc_matched) / total < floor:
            continue  # even the whole document can't reach the floor
        in_title = {t for t in doc_matched if pats[t].search(c.title_lower)}
        best, passage = set(in_title), ""
        for p in c.passages():
            low = p.lower()
            m = in_title | {t for t in doc_matched - in_title if pats[t].search(low)}
            if sum(weights[t] for t in m) > sum(weights[t] for t in best) or not passage:
                best, passage = m, p
        coverage = sum(weights[t] for t in best) / total
        if len(best) < floor_matches or coverage < floor:
            continue
        title_share = sum(weights[t] for t in in_title) / total
        strict = (
            len(best) >= min_matches
            and coverage >= bar
            and any(df[t] <= rare_df for t in best)
            and not (c.tier >= UNCURATED_TIER and not in_title and coverage < UNCURATED_COVERAGE)
        )
        if not strict and not loose:
            continue
        rank = coverage + TITLE_BONUS * title_share - TIER_PENALTY * c.tier
        out.append(_Ranked(coverage, c, sorted(best, key=lambda t: -weights[t]), rank, passage,
                           strict))
    out.sort(key=lambda r: (-round(r.rank, 3), r.c.tier, r.c.id))
    return out


# A pick after the first must rank within this much of the first; far weaker
# matches are padding, not context.
RELATIVE_FLOOR = 0.25


def _family(c: Candidate) -> str:
    """Candidates from one family repeat each other (three of one agent's logs on
    the same topic); only the best of a family is injected. Curated memory files
    are each a distinct fact, so every one is its own family."""
    if c.tier == 0:
        return c.id
    if c.source == "conversation":
        return "conversation"
    return f"{c.source}/{c.author}" if c.author else c.id


# Semantic check (used when an embedder is available — see semantic.py).
# Thresholds were swept on a labeled prompt set (`python3 -m core.knowledge.memory eval`): chatty prompts
# peak around 0.3-0.46 cosine against everything, so meaning alone needs a high
# bar; a candidate that ALSO passes the strict word gate needs less.
SEM_K = 12  # lexical candidates sent to the semantic check
SEM_WITH_WORDS = 0.40  # cosine needed when the strict word gate also passes
SEM_ALONE = 0.50  # cosine needed on meaning alone (loose or no word overlap)
WORDS_BONUS = 0.10  # ranking bonus for also passing the strict word gate
DOC_CHARS = 1200  # curated memories are embedded whole (up to this)


def embed_text(c: Candidate, passage: str | None = None) -> str:
    """The exact text embedded for a candidate. Curated memories (tier <= 1) are
    embedded whole, so their vectors are prompt-independent and can be warmed
    ahead of time; longer sources are embedded per fixed passage."""
    from .semantic import doc_text

    if c.tier <= 1 or passage is None:
        body = _FRONTMATTER.sub("", c.text, count=1)[:DOC_CHARS]
    else:
        body = passage
    return doc_text(c.title, body)


def _diverse(scored, n: int, floor: float):
    picked, families, top = [], set(), None
    for key, item in scored:
        if top is None:
            top = key
        elif key < top - floor:
            break
        fam = _family(item[1])
        if fam in families:
            continue
        families.add(fam)
        picked.append(item)
        if len(picked) == n:
            break
    return picked


def select(
    prompt: str, pool: list[Candidate], n: int = 3, embedder=None
) -> list[tuple[float, Candidate, list[str]]]:
    """What the prompt hook injects: at most n, best first, one per family.

    Without an embedder (or when it is unavailable): the lexical gate decides.
    With one, words only PROPOSE candidates and meaning decides: a candidate is
    injected when its embedding is close to the prompt's. Curated memories are
    also searched by meaning alone, so a paraphrase with no shared words still
    finds them. The first element of each pick is the cosine (semantic) or the
    coverage (lexical).
    """
    if embedder is None:
        return _select_lexical(prompt, pool, n)
    ranked = _ranked(prompt, pool, loose=True)
    lexical = ranked[:SEM_K]
    by_id = {r.c.id: r for r in lexical}
    curated = [c for c in pool if c.tier == 0 and c.id not in by_id]
    docs = {r.c.id: embed_text(r.c, r.passage) for r in lexical}
    docs.update({c.id: embed_text(c) for c in curated})
    sims = embedder.similarity(prompt, docs)
    if sims is None:
        return _select_lexical(prompt, pool, n)
    scored = []
    for r in lexical:
        sim = sims.get(r.c.id)
        if sim is None:  # not embedded within the time budget: words must decide
            if r.strict:
                scored.append((SEM_WITH_WORDS, (SEM_WITH_WORDS, r.c, r.matched)))
            continue
        if (r.strict and sim >= SEM_WITH_WORDS) or sim >= SEM_ALONE:
            rank = sim + (WORDS_BONUS if r.strict else 0.0) - TIER_PENALTY / 5 * r.c.tier
            scored.append((rank, (sim, r.c, r.matched)))
    for c in curated:
        sim = sims.get(c.id)
        if sim is not None and sim >= SEM_ALONE:
            scored.append((sim, (sim, c, [])))
    scored.sort(key=lambda x: -x[0])
    return _diverse(scored, n, floor=1.0)


def _select_lexical(prompt: str, pool: list[Candidate], n: int):
    scored = [(r.rank, (r.coverage, r.c, r.matched)) for r in _ranked(prompt, pool)]
    return _diverse(scored, n, RELATIVE_FLOOR)


def best_line(c: Candidate, matched: list[str], width: int = 180) -> str:
    """The line of the memory that carries most of the matched words (or, for a
    meaning-only pick, its first body line) — the fact itself, so the reader
    rarely has to open the file."""
    pats = [_pattern(t) for t in matched]
    best, best_hits, first = "", 0, ""
    for line in _FRONTMATTER.sub("", c.text, count=1).splitlines():
        line = line.strip().lstrip("#-*> ").strip()
        if len(line) < 12 or line == c.title:
            continue
        first = first or line
        low = line.lower()
        hits = sum(1 for p in pats if p.search(low))
        if hits > best_hits:
            best, best_hits = line, hits
    if not matched:  # found by meaning alone: the opening line states the fact
        best = first
    if not best or best == c.title:
        return ""
    return best if len(best) <= width else best[: width - 1] + "…"


def evaluate(labels: list[dict], pool: list[Candidate], n: int = 3, embedder=None) -> dict:
    """Score select() against labeled prompts.

    Each label is {"prompt", "expect": [path substrings]}; an empty expect means
    the right answer is to inject nothing. A pick is correct when its path (or id)
    contains any expected substring.
    """
    rows = []
    for lab in labels:
        picks = select(lab["prompt"], pool, n, embedder)
        exp = lab.get("expect") or []
        ok = [any(e in (c.path or c.id) for e in exp) for _, c, _ in picks]
        rows.append({"prompt": lab["prompt"], "expect": exp, "ok": ok,
                     "picks": [c.path or c.id for _, c, _ in picks]})
    rel = [r for r in rows if r["expect"]]
    none = [r for r in rows if not r["expect"]]
    injected = sum(len(r["ok"]) for r in rel)
    return {
        "hit@1": sum(bool(r["ok"]) and r["ok"][0] for r in rel) / max(1, len(rel)),
        f"hit@{n}": sum(any(r["ok"]) for r in rel) / max(1, len(rel)),
        "clean": sum(not r["picks"] for r in none) / max(1, len(none)),
        "off_target_slots": (injected - sum(sum(r["ok"]) for r in rel)) / max(1, injected),
        "n_relevant": len(rel),
        "n_none": len(none),
        "rows": rows,
    }


def render(hits: list[tuple[float, Candidate, list[str]]]) -> str:
    """The context block the prompt hook injects ("" when nothing passed)."""
    if not hits:
        return ""
    lines = [f"## Remembered context (top {len(hits)}, relevance-gated)"]
    for cov, c, matched in hits:
        who = f"/{c.author}" if c.author else ""
        where = f" — {c.path}" if c.path else ""
        words = f": {', '.join(matched[:5])}" if matched else ""
        lines.append(f"- [{c.source}{who}] {c.title}{where}  (relevance {cov:.2f}{words})")
        line = best_line(c, matched)
        if line:
            lines.append(f"    > {line}")
    return "\n".join(lines)
