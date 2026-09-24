from __future__ import annotations
from pathlib import Path
from core.config import Config
from core.runtime.adapters.cli import CliAdapter
from core.runtime.orchestrator import Orchestrator


def run_loop(config: Config, *, cwd: str, input_fn=input, output_fn=print,
             orchestrator=None) -> None:
    adapter = CliAdapter(input_fn=input_fn, output_fn=output_fn)
    orch = orchestrator or Orchestrator(config, cwd=cwd)
    while True:
        msg = adapter.read()
        if msg is None:
            break
        adapter.write(orch.handle(msg))


def main() -> int:
    cwd = Path.cwd()
    config = Config.load(cwd / "config.yaml")
    run_loop(config, cwd=str(cwd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
