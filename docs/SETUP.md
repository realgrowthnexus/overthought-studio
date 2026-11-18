# Overthought Studio: setup guide (VPS-only)

The setup happens once. After that the system runs itself.

## What runs where
| Part | Where | Job |
|---|---|---|
| Dashboard | Your Hostinger VPS (Docker) → `https://studio.getgrowthnexus.com` | You watch, approve and control everything here |
| Worker | Same VPS (Docker) | Researches, writes, draws, records, edits and uploads, 24/7 |
| Database and files | Supabase (`overthought-studio`, US East) | Channels, videos, stats and daily backups |

Everything lives in `/opt/overthought-studio` on the VPS. Your other app is never touched:
- The installer checks ports 80/443 first.
- It only adds a site for `studio.getgrowthnexus.com`.

**Moving to a new VPS:**
1. Copy `/opt/overthought-studio/.env` to the new VPS.
2. Run the installer there.
3. Stop the old VPS.

All data stays in Supabase.

---

## Step 1: DNS (once)
At your domain provider, add this record. If you're on Cloudflare, set it to "DNS only" (grey cloud).

| Type | Name | Value |
|---|---|---|
| A | `studio` | your VPS IP (Hostinger → VPS → Overview) |

## Step 2: Supabase auth settings (once, 1 minute)
Go to Supabase → project **overthought-studio** → **Authentication**:
- **Sign In / Providers**: turn **Allow new users to sign up** OFF.
- **URL Configuration**: set Site URL to `https://studio.getgrowthnexus.com`.

## Step 3: Two keys to have ready
1. **Supabase secret key**: Supabase → Project Settings → **API Keys** → Secret key (`sb_secret_...`).
2. **GitHub read-only token**: github.com → Settings → Developer settings → **Fine-grained tokens** → Generate.
   - Repository access: only `overthought-studio`.
   - Permissions: **Contents: Read-only**.
   - Expiry: 1 year.

## Step 4: Install on the VPS (about 10 minutes)
1. Hostinger → VPS → **Browser terminal**. Log in as root.
2. Paste the install command from your setup message.
   - It asks for the two keys above. Typing is hidden.
3. Wait for the build to finish. At the end it prints:
   - the **one-time setup token**, used to create your login;
   - your **MASTER_KEY**. Save it in a password manager.
4. Open `https://studio.getgrowthnexus.com/setup`, enter the setup token, and create your owner login.
   - Only one owner can ever be created.

**If ports 80/443 already belong to another panel** (Coolify, CapRover, Nginx Proxy Manager, Traefik…), the installer prints one line to add in that panel: `studio.getgrowthnexus.com → http://172.17.0.1:3100`.

## Step 5: API keys (dashboard → Settings)
| Key | Where to get it | Notes |
|---|---|---|
| Anthropic (Claude) | console.anthropic.com → API Keys | Add credit under Billing, then type the balance into Settings so the dashboard can count it down |
| ElevenLabs | elevenlabs.io → Developers → API Keys | Enable **Text to Speech**, **Voices: Read** and **User: Read**. User: Read is needed to show your balance |
| RunPod | runpod.io → Settings → API Keys | |
| TikTok client key and secret | Step 6 | |
| Resend (optional) | resend.com | Emails the weekly report |

Keys are encrypted (AES-256-GCM) before they are saved. The dashboard never shows them again; it only shows the last 4 characters.

## Step 6: TikTok developer app (once)
1. Go to developers.tiktok.com → **Manage apps** → **Connect an app**.
2. Fill in the app details:
   - **Name:** Overthought Studio
   - **Icon:** `assets/brand/tiktok_profile_1080.png`
   - **Category:** Entertainment
   - **Description:** "Publishes the owner's own educational videos to their own TikTok accounts."
   - **Terms URL:** `https://studio.getgrowthnexus.com/terms`
   - **Privacy URL:** `https://studio.getgrowthnexus.com/privacy`
   - **Platform:** Web, at `https://studio.getgrowthnexus.com`. Verify the domain if asked.
3. Add these products:
   - **Login Kit**, with redirect URI `https://studio.getgrowthnexus.com/api/tiktok/callback`
   - **Content Posting API**. Turn on **Direct Post**.
4. Add these scopes: `user.info.basic`, `user.info.profile`, `user.info.stats`, `video.list`, `video.upload`, `video.publish`.
5. Paste the **Client key** and **Client secret** into dashboard → Settings.
6. **Sandbox:** add your TikTok accounts as **target users**. Then connect each one in dashboard → **TikTok accounts**.
7. **Submit for review.** After approval, apply for the **Content Posting API audit**. That audit unlocks public posting.
   - Until it passes, videos arrive as **drafts in your TikTok inbox**, or post as private.

## Step 7: Go live
On each channel page, check the voice, schedule and posting mode, then press **Start**.

| Mode | What happens |
|---|---|
| draft | The video goes to your TikTok inbox and you tap Post. Use this until the audit passes |
| private | Posted, visible only to you |
| public | Needs the audit plus **Settings → Auto-publish** |

With **Approval** on, every video waits on the Videos page for you to approve it.

## Updates and logs
The VPS checks GitHub every 10 minutes and rebuilds itself when the code changes.

- Logs: `cd /opt/overthought-studio && docker compose logs -f`
- Force an update: `/opt/overthought-studio/update.sh --force`

## When something stops
The red bar at the top of the dashboard always says **what** stopped and **why**, for example "ElevenLabs quota used up". Work resumes **by itself** within 10 minutes of the fix, for example after a top-up.
