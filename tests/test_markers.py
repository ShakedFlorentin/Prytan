from core.runtime.markers import parse_markers, Dispatch, SCAN_MODEL

def test_parse_run_and_runw_and_scan():
    reply = (
        "Sure, here's the plan.\n"
        "@@RUN: backend :: audit the auth flow\n"
        "@@RUNW: backend :: add a rate limiter\n"
        "@@SCAN: security :: grep for hardcoded secrets\n"
        "I'll relay the results."
    )
    cleaned, ds = parse_markers(reply)
    assert "@@RUN" not in cleaned and "@@SCAN" not in cleaned
    assert "here's the plan" in cleaned and "relay the results" in cleaned
    assert ds[0] == Dispatch(agent="backend", task="audit the auth flow", write=False, model=None, kind="run")
    assert ds[1].write is True and ds[1].kind == "run"
    assert ds[2].kind == "scan" and ds[2].model == SCAN_MODEL

def test_no_markers_returns_text_unchanged():
    cleaned, ds = parse_markers("just a chat reply, no dispatch")
    assert cleaned == "just a chat reply, no dispatch"
    assert ds == []
