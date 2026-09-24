from core.knowledge.codegrapher.graph import build_graph
from core.knowledge.codegrapher.ts import build_ts_graph, is_ts_source
from pathlib import Path


def _ids(g):
    return {n["id"] for n in g["nodes"]}


def test_typescript_declarations_are_indexed(tmp_path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "time.ts").write_text(
        "import { z } from 'zod';\n"
        "/**\n"
        " * Server clock.\n"
        " */\n"
        "export function serverNow(): number {\n"
        "  return Date.now();\n"
        "}\n"
        "export const stopwatch = (s: number) => String(s);\n"
        "export interface Session { id: string }\n"
        "export type Side = 'left' | 'right';\n"
        "export class Clock {}\n"
    )
    g = build_graph(tmp_path)
    ids = _ids(g)
    assert "module:lib.time" in ids
    assert "function:lib.time.serverNow" in ids
    # arrow-function consts are functions, not opaque constants
    assert "function:lib.time.stopwatch" in ids
    assert "interface:lib.time.Session" in ids
    assert "type:lib.time.Side" in ids
    assert "class:lib.time.Clock" in ids
    assert any(e["kind"] == "imports" and "zod" in e["dst"] for e in g["edges"])
    assert ("module:lib.time", "function:lib.time.serverNow", "contains") in {
        (e["src"], e["dst"], e["kind"]) for e in g["edges"]
    }


def test_jsdoc_above_a_declaration_becomes_its_doc(tmp_path):
    (tmp_path / "a.ts").write_text(
        "/** Counts elapsed seconds from the server anchor. */\n"
        "export function elapsed() { return 0 }\n"
    )
    g = build_graph(tmp_path)
    node = next(n for n in g["nodes"] if n["id"] == "function:a.elapsed")
    assert "server anchor" in node["doc"]


def test_tsx_components_are_indexed(tmp_path):
    (tmp_path / "C.tsx").write_text(
        "export function SinceCounter({ at }: { at: number }) {\n"
        "  return <div>{at}</div>;\n"
        "}\n"
    )
    assert "function:C.SinceCounter" in _ids(build_graph(tmp_path))


def test_build_dirs_are_never_indexed(tmp_path):
    for d in ("node_modules", ".next", "dist"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "junk.ts").write_text("export function junk() {}\n")
    (tmp_path / "real.ts").write_text("export function real() {}\n")
    ids = _ids(build_graph(tmp_path))
    assert "function:real.real" in ids
    assert not any("junk" in i for i in ids)


def test_python_indexing_is_unchanged_by_the_ts_pass(tmp_path):
    (tmp_path / "m.py").write_text(
        '"""mod doc."""\n'
        "import os\n"
        "def greet(name):\n"
        "    return name\n"
    )
    g = build_graph(tmp_path)
    ids = _ids(g)
    assert "module:m" in ids and "function:m.greet" in ids
    # and a python-only tree yields nothing from the TS scanner
    assert build_ts_graph(tmp_path)["nodes"] == []


def test_mixed_language_tree_keeps_both(tmp_path):
    (tmp_path / "s.py").write_text("def py_fn():\n    return 1\n")
    (tmp_path / "s.ts").write_text("export function tsFn() {}\n")
    ids = _ids(build_graph(tmp_path))
    assert "function:s.py_fn" in ids
    assert "function:s.tsFn" in ids


def test_is_ts_source_rejects_non_source(tmp_path):
    assert is_ts_source(Path("src/a.ts"))
    assert is_ts_source(Path("src/a.tsx"))
    assert not is_ts_source(Path("src/a.css"))
    assert not is_ts_source(Path("node_modules/pkg/a.ts"))
