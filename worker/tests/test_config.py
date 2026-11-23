import importlib


def test_supabase_key_drops_stray_paste_characters(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sb_secret_abcDEF123-_x\r")
    from studio import config
    try:
        assert importlib.reload(config).SUPABASE_KEY == "sb_secret_abcDEF123-_x"
    finally:
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY")
        importlib.reload(config)


def test_legacy_jwt_key_keeps_dots(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", " eyJhbGc.eyJyb2xl.c2ln \n")
    from studio import config
    try:
        assert importlib.reload(config).SUPABASE_KEY == "eyJhbGc.eyJyb2xl.c2ln"
    finally:
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY")
        importlib.reload(config)
