# Handoff: starting a new Claude Code session

Paste the block below as the first message of the new session (repo `realgrowthnexus/overthought-studio`).

```text
You are taking over Overthought Studio. First read docs/BRAIN.md completely (start at §0), then
docs/ARCHITECTURE.md, and skim docs/WEB.md and docs/SETUP.md. Reply to me only in Roman Urdu or
simple English. I am not a developer: give me short numbered steps.

Where we are: I took the studio down to redeploy it myself, step by step WITH you, so I
understand every part (BRAIN §0.0). Teach me as we go. Claude runs on my Claude Pro sign-in,
not an API key. No real video has been made yet.

What I want next:
1. Redeploy with me one step at a time (order in BRAIN §0.0), then my setup tasks in §0.2.
2. Then make the first real video (BRAIN §6 step 3). Ask me before you spend money.
3. Then the TikTok app (BRAIN §6 step 4).

Keep docs/BRAIN.md updated after every big step. Commit and push to main.
```

## Notes for the new Claude
- Pushing to `main` goes live on the VPS within ~10 minutes. Run the tests first (commands are in BRAIN §0.1).
- You cannot SSH to the VPS from a cloud session. The owner runs commands in Hostinger's Browser terminal and sends you
  the output. `infra/doctor.sh` output contains no secrets.
- Never log into the owner's real dashboard. For UI work, use the demo copy in `tools/demo`.
- Never ask for secrets in chat. Keys go in dashboard Settings. The Claude sign-in goes through
  `infra/connect-claude.sh` only.
