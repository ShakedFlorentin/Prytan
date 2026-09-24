"""`python3 -m core.knowledge.memory eval LABELS.jsonl [--root DIR] [-n 3] [-v] [--semantic|--lexical]`
`python3 -m core.knowledge.memory warm [--root DIR]`   (pre-embed memory/ files)

Scores prompt-time recall against labeled prompts, one JSON object per line:
{"prompt": "...", "expect": ["memory/some-fact.md"]} — an empty expect means the
right answer is to inject nothing. Tune the gate against this, not by eye.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.knowledge.memory.sources import TIER_MEMORY, embedder, gather, semantic_enabled
from core.knowledge.relevance import embed_text, evaluate


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="memory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ev = sub.add_parser("eval", help="score prompt recall against labeled prompts")
    ev.add_argument("labels")
    ev.add_argument("--root", default=".")
    ev.add_argument("-n", type=int, default=3)
    ev.add_argument("-v", "--verbose", action="store_true")
    mode = ev.add_mutually_exclusive_group()
    mode.add_argument("--semantic", action="store_true", help="force the embedding check on")
    mode.add_argument("--lexical", action="store_true", help="force the word gate only")
    wm = sub.add_parser("warm", help="pre-embed memory files for semantic recall")
    wm.add_argument("--root", default=".")
    args = ap.parse_args(argv)

    if args.cmd == "warm":
        emb = embedder(args.root)
        texts = [embed_text(c) for c in gather(args.root) if c.tier == TIER_MEMORY]
        added = emb.warm(texts)
        state = "unavailable" if emb.dead else "ok"
        print(f"warm: {added} new embeddings, {len(texts)} memories, service {state}")
        if not semantic_enabled(args.root):
            print("note: semantic recall is off for this project — set `memory: {semantic: true}`"
                  " in config.yaml to use these embeddings")
        return 0

    labels = [json.loads(x) for x in Path(args.labels).read_text().splitlines() if x.strip()]
    use = args.semantic or (not args.lexical and semantic_enabled(args.root))
    emb = embedder(args.root, timeout=30, max_new=64) if use else None
    pool = [c for c in gather(args.root) if c.source != "conversation"]
    res = evaluate(labels, pool, n=args.n, embedder=emb)
    if args.verbose:
        for r in res["rows"]:
            if r["expect"]:
                mark = "HIT1" if r["ok"] and r["ok"][0] else ("HIT" if any(r["ok"]) else "MISS")
            else:
                mark = "CLEAN" if not r["picks"] else "NOISE"
            print(f"{mark:5} {r['prompt'][:70]}")
            for p, ok in zip(r["picks"], r["ok"] or [False] * len(r["picks"])):
                print(f"        {'+' if ok else '-'} {p}")
    print(f"hit@1 {res['hit@1']:.0%}  hit@{args.n} {res[f'hit@{args.n}']:.0%}  "
          f"(n={res['n_relevant']})  clean {res['clean']:.0%} (n={res['n_none']})  "
          f"off-target slots {res['off_target_slots']:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
