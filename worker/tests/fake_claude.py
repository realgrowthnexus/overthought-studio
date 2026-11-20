#!/usr/bin/env python3
"""Stand-in for the `claude` CLI in tests. Mode comes from FAKE_CLAUDE_MODE; argv + chosen env go to FAKE_CLAUDE_LOG."""
import json, os, sys

log = os.environ.get("FAKE_CLAUDE_LOG")
if log:
    with open(log, "a") as f:
        f.write(json.dumps({"argv": sys.argv[1:], "token": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"),
                            "api_key": os.environ.get("ANTHROPIC_API_KEY"), "home": os.environ.get("HOME")}) + "\n")
mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
if sys.argv[1:3] == ["auth", "status"]:
    print(json.dumps({"loggedIn": bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")), "authMethod": "oauth_token"}))
    sys.exit(0)
usage = {"input_tokens": 10, "output_tokens": 42}
if mode == "ok":
    out = {"type": "result", "subtype": "success", "is_error": False, "result": "hello there", "usage": usage,
           "modelUsage": {"claude-opus-5-5": {}}}
    if "--json-schema" in sys.argv:
        out["structured_output"] = json.loads(os.environ.get("FAKE_CLAUDE_STRUCTURED", "{}"))
elif mode == "limit":
    out = {"type": "result", "subtype": "success", "is_error": True,
           "result": "Claude AI usage limit reached|1900000000", "usage": usage}
elif mode == "limit_text":
    out = {"type": "result", "subtype": "success", "is_error": True,
           "result": "You've hit your session limit · resets 3pm (America/New_York)", "usage": usage}
elif mode == "auth":
    out = {"type": "result", "subtype": "success", "is_error": True,
           "result": "Invalid API key · Please run /login", "usage": usage}
elif mode == "error":
    out = {"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "boom"}
else:
    print("not json at all")
    sys.exit(1)
print(json.dumps(out))
