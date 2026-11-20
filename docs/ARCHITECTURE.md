# Overthought Studio — Architecture

Self-running studio that produces and posts 60s+ TikTok explainers for up to N channels.

```
apps/web     Next.js 15 dashboard (Docker on the VPS)        ──┐
worker/      Python worker (Docker on VPS)                      ├── Supabase (Postgres + Auth + Storage + Realtime)
supabase/    SQL migrations                                   ──┘
infra/       docker-compose, install.sh, doctor.sh
assets/      brand kit, fonts, base scenes
```

The dashboard never talks to the worker directly. Both read/write Supabase:
- Dashboard → inserts rows in `jobs`, edits `channels`, `settings`, `secrets`, approves `videos`.
- Worker → claims jobs via RPC `claim_job(p_worker, p_types)` (FOR UPDATE SKIP LOCKED), updates `videos`,
  `services`, `events`, `spend`, `worker_heartbeats`. No inbound port on the VPS is needed.

## Secrets
`public.secrets(key, ciphertext, hint)` — written only by dashboard server code (service role), read by worker.
Encryption: AES-256-GCM. `MASTER_KEY` env = 32 random bytes, base64. Web and worker containers share it via `/opt/overthought-studio/.env`.
Ciphertext format: `v1:` + base64( iv[12] || ciphertext || tag[16] ).
(Node: `createCipheriv('aes-256-gcm')`, append `getAuthTag()`. Python: `cryptography` AESGCM, which already returns ct||tag.)
Keys: `anthropic_api_key`, `elevenlabs_api_key`, `runpod_api_key`, `tiktok_client_key`, `tiktok_client_secret`, `resend_api_key`.
TikTok tokens in `tiktok_accounts.access_token_enc/refresh_token_enc` use the same format.
Worker falls back to env vars `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `RUNPOD_API_KEY`, … if a secret row is missing.

## Job types (`jobs.type`)
| type | payload | who enqueues |
|---|---|---|
| `plan_channel` | `{channel_id, force?}` | scheduler (keeps buffer full) / dashboard "Make a video now" |
| `produce_video` | `{video_id, from_stage?}` | plan_channel / dashboard "Regenerate" |
| `research_ideas` | `{channel_id, count?}` | scheduler when idea bank < 10 / dashboard |
| `publish_video` | `{video_id}` | scheduler at slot time / dashboard "Publish now" |
| `check_publish` | `{video_id}` | publish_video (polls status) |
| `sync_stats` | `{channel_id?}` | scheduler every 6h / dashboard |
| `import_stats` | `{storage_path, channel_id}` | dashboard CSV upload (bucket `videos`, prefix `imports/`) |
| `weekly_review` | `{channel_id?}` | scheduler Monday 09:00 ET / dashboard |
| `health_check` | `{}` | scheduler every 10 min / dashboard |
| `refresh_tokens` | `{}` | scheduler hourly |
| `backup_db` | `{}` | scheduler daily 04:00 UTC |
| `cleanup_storage` | `{}` | scheduler daily |

`jobs.status='waiting'` + `waiting_on='elevenlabs'` means the job is parked because that service is out of credits
or down; the worker re-queues it automatically when `services.status` returns to `ok`.

## Video lifecycle (`videos.status`)
`queued → researching → scripting → fact_checking → visuals → voice → rendering → ready`
→ (`require_approval` ? wait for dashboard approve → `approved`) → `scheduled` → `uploading` → `sent_to_drafts` | `posted`
Side states: `rejected`, `failed` (error text), `blocked` (dependency down, see `channels.blocked_reason`).

`posting_mode`: `draft` = inbox upload (user taps Publish in TikTok), `private` = direct post SELF_ONLY,
`public` = direct post PUBLIC_TO_EVERYONE (requires audited TikTok app). Global `settings.global.auto_publish`
must be true AND channel `require_approval=false` for zero-touch public posting.

## Storage (bucket `videos`, private)
`{channel_slug}/{video_id}/final.mp4`, `thumb.jpg`, `voice.mp3`, `scenes/{n}.jpg`. Dashboard plays via signed URLs.
Bucket `backups`: `db/{yyyy-mm-dd}.json.gz` (nightly logical export of all public tables except secrets ciphertext is included — still encrypted).

## Service status (`services`)
`anthropic` — no balance API; worker sums `spend` and compares with `settings.anthropic_credit.balance_usd` (owner enters
after top-up). Any `credit balance is too low` error → `out_of_credits`.
`elevenlabs` — `GET /v1/user/subscription` → `character_count/character_limit`; quota errors → `out_of_credits`.
`runpod` — GraphQL `myself { clientBalance }`; `balance < 0.5` → `warning`, insufficient funds → `out_of_credits`.
`tiktok` — app keys present + account tokens valid. `storage` — bucket usage. `worker` — heartbeat age.

## Channel JSON shapes
```jsonc
style:   { "preset": "charcoal", "bg": "#111111", "ink": "#F6F1E6", "accent": "#FFD60A",
           "body_font": "Kalam-Bold.ttf", "key_font": "CaveatBrush-Regular.ttf",
           "figure_prompt": "classic stick figure made of single thin white lines…", "seed": 7, "bug_text": "overthought" }
voice:   { "provider": "elevenlabs", "voice_id": "…", "model_id": "eleven_multilingual_v2",
           "stability": 0.45, "similarity_boost": 0.8, "style": 0.15, "speed": 1.0 }
content: { "audience": "US, 16–34", "tone": "…", "pillars": [{"name":"Why you do that","weight":0.7}, …],
           "hook_styles": ["you-callout","myth-bust","number","question","pov"], "hashtags_core": ["#psychology"],
           "rules": ["Every claim cites a real study", …], "banned": ["medical advice"] }
strategy:{ "week_of": "2026-11-23", "pillar_weights": {…}, "hook_weights": {…}, "test": {"variable":"hook","variant":"question"},
           "notes": "…" }
```
