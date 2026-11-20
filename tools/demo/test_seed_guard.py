import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def test_only_exact_local_hosts_are_allowed():
    from seed_demo import is_local
    assert is_local("http://127.0.0.1:54321")
    assert is_local("http://localhost:54321")
    assert not is_local("https://localhost.example.com")
    assert not is_local("https://xkbgusqmdeocjwxaknjx.supabase.co")
    assert not is_local("https://evil.co/?u=127.0.0.1")
