from core.runtime.metering import turn_cost, log_usage, PRICING

def test_turn_cost_sonnet():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    cost = turn_cost(usage, "claude-sonnet-4-6")
    assert round(cost, 2) == round(PRICING["claude-sonnet-4-6"]["in"] +
                                   PRICING["claude-sonnet-4-6"]["out"], 2)

def test_turn_cost_unknown_model_falls_back():
    # unknown model bills at the default (Sonnet) tier
    assert turn_cost({"input_tokens": 1_000_000}, "made-up-model") == PRICING["claude-sonnet-4-6"]["in"]

def test_log_usage_appends_row(tmp_path):
    led = tmp_path / "usage.tsv"
    log_usage(led, "backend", "claude-sonnet-4-6", {"output_tokens": 5}, 0.001)
    log_usage(led, "security", "claude-haiku-4-5", {"output_tokens": 9}, 0.002)
    lines = led.read_text().strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("backend\t")
