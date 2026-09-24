from core.runtime.adapters.cli import CliAdapter

def test_cli_adapter_reads_and_writes():
    inputs = iter(["hello", ""])  # second empty line ends the session
    written = []
    adapter = CliAdapter(input_fn=lambda _prompt="": next(inputs),
                         output_fn=written.append)
    assert adapter.read() == "hello"
    adapter.write("hi there")
    assert any("hi there" in w for w in written)
    assert adapter.read() is None   # empty input -> end of session
