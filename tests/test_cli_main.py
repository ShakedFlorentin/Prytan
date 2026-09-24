from core.config import Config
from core.runtime import cli_main

def test_run_loop_relays_until_blank_line():
    cfg = Config.load("/nonexistent")
    inputs = iter(["hello", ""])
    written = []
    def adapter_inputs(_p=""):
        return next(inputs)
    # fake orchestrator: echo uppercased
    class FakeOrch:
        def handle(self, msg): return msg.upper()
    cli_main.run_loop(cfg, cwd="/tmp",
                      input_fn=adapter_inputs, output_fn=written.append,
                      orchestrator=FakeOrch())
    assert any("HELLO" in w for w in written)
