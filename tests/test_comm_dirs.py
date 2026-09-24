from core.protocol.comm_dirs import COMM_DIRS, ensure_comm_dirs

def test_ensure_creates_all_comm_dirs(tmp_path):
    created = ensure_comm_dirs(tmp_path)
    for name in COMM_DIRS:
        assert (tmp_path / name).is_dir()
    assert len(created) == len(COMM_DIRS)

def test_ensure_is_idempotent(tmp_path):
    ensure_comm_dirs(tmp_path)
    # second call must not raise
    again = ensure_comm_dirs(tmp_path)
    assert all(p.is_dir() for p in again)
