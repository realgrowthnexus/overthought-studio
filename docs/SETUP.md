# Overthought Studio: setup guide

Most of this is a one-time setup. After it, the system runs itself.

## What runs where
| Part | Where | What it does |
|---|---|---|
| Dashboard | Vercel → `studio.getgrowthnexus.com` | You watch, approve and control everything here |
| Worker | Your Hostinger VPS (Docker) | Researches, writes, draws, records, edits, uploads, 24/7 |
| Database and files | Supabase (`overthought-studio`, US East) | Channels, videos, stats, backups |

The VPS holds no data. If you change VPS, run the installer on the new one and stop the old one.

---

## Step 1: Dashboard on Vercel (one time, about 5 minutes)
1. Go to vercel.com → **Add New → Project** → import `realgrowthnexus/overthought-studio`.
2. Set **Root Directory** to `apps/web`. The framework is detected as Next.js.
3. Add these **Environment Variables**. Values that aren't shown here come from your setup message:
   - `NEXT_PUBLIC_SUPABASE_URL` = `https://xkbgusqmdeocjwxaknjx.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = `sb_publishable_YsB1YII7YQ3d1s3NRfs9MQ_1YzxWIfR`
   - `SUPABASE_URL` = `https://xkbgusqmdeocjwxaknjx.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY` = your Supabase **secret** key (Supabase → Project Settings → API Keys)
   - `MASTER_KEY` = (from your setup message; it must match the VPS exactly)
   - `SETUP_TOKEN` = (from your setup message)
   - `APP_URL` = `https://studio.getgrowthnexus.com`
4. Click **Deploy**. Then go to **Settings → Domains**, add `studio.getgrowthnexus.com` and create the DNS record Vercel shows you (usually `CNAME studio → cname.vercel-dns.com`) at your domain provider.
5. Open `https://studio.getgrowthnexus.com/setup`, enter the `SETUP_TOKEN`, and create your owner login. Only one owner can be created. After that, `/setup` stops working.

## Step 2: API keys (in the dashboard → Settings)
| Key | Where to get it | Notes |
|---|---|---|
| Anthropic (Claude) | console.anthropic.com → API Keys | Add credit under Billing, then type your balance into Settings so the dashboard can count it down |
| ElevenLabs | elevenlabs.io → Developers → API Keys | Turn on the **Text to Speech**, **Voices: Read** and **User: Read** permissions. User: Read lets the dashboard show your balance |
| RunPod | runpod.io → Settings → API Keys | Pay per image (about $0.012) |
| TikTok client key and secret | Step 4 below | |
| Resend (optional) | resend.com | Emails the weekly report to you |

Keys are encrypted (AES-256) before they are saved. Nobody can read them back, not even from the dashboard.

## Step 3: Worker on the VPS (one time, about 10 minutes)
1. **GitHub token** (lets the VPS download the code): github.com → Settings → Developer settings → **Fine-grained tokens** → Generate.
   - Repository access: only `overthought-studio`.
   - Permissions: **Contents: Read-only**.
   - Expiry: 1 year.
2. **Open the VPS terminal**: Hostinger → VPS → **Browser terminal**.
3. Paste the command block from your setup message. It sets three values and runs `infra/install.sh`.
4. Wait about 5 minutes for the first build. The dashboard's **Worker** light turns green.

Your other app on the VPS isn't affected. The worker runs in its own Docker container, opens no ports, and uses at most 3 CPU cores and 6 GB of RAM. It checks GitHub every 10 minutes and updates itself.

## Step 4: TikTok developer app (one time)
1. Go to developers.tiktok.com, log in, then **Manage apps → Connect an app**.
2. Fill in the app details:
   - **App name**: Overthought Studio.
   - **Icon**: `assets/brand/tiktok_profile_1080.png`.
   - **Category**: Entertainment.
   - **Description**: "Publishes the owner's own educational videos to their own TikTok accounts."
   - **Terms of Service URL**: `https://studio.getgrowthnexus.com/terms`.
   - **Privacy Policy URL**: `https://studio.getgrowthnexus.com/privacy`.
   - **Platform**: Web, with website `https://studio.getgrowthnexus.com`. Verify the domain if TikTok asks.
3. Add the products:
   - **Login Kit**. Redirect URI: `https://studio.getgrowthnexus.com/api/tiktok/callback`.
   - **Content Posting API**. Also switch on **Direct Post**.
4. Add these scopes: `user.info.basic`, `user.info.profile`, `user.info.stats`, `video.list`, `video.upload`, `video.publish`.
5. Copy the **Client key** and **Client secret** into the dashboard → Settings.
6. While the app is in **Sandbox**, add your 5 TikTok accounts as **target users**. Then go to the dashboard → **Accounts → Connect** for each channel.
7. Click **Submit for review**. Once it's approved, apply for the **Content Posting API audit** to unlock public posting.
   - Until the audit passes, videos arrive in your TikTok **inbox as drafts**, or post as private.

## Step 5: Go live
1. On each channel's page, check the voice, schedule and posting mode, then press **Start**.
2. **Posting modes:**
   - **draft**: the video goes to your TikTok inbox, and you tap Post. Use this until the audit passes.
   - **private**: posted, visible only to you.
   - **public**: posted publicly. This needs the audit, plus **Settings → Auto-publish** turned on.
3. **Approval**: while a channel's approval setting is on, every new video waits on the **Videos** page for your Approve. Turn it off only when you trust the output.

## Costs (5 channels × 1 video a day)
| Item | Per video | Per month |
|---|---|---|
| Claude | about $0.25–0.45 | about $40–70 |
| RunPod | about $0.08 | about $12 |
| ElevenLabs | about 1,400 characters | about 210k characters (Pro plan) |
| Supabase / Vercel | | free tiers to start |

Daily and monthly budget caps (Settings) stop production automatically, and the dashboard shows why.

## When something stops
The dashboard's top banner always says **what** stopped and **why**, for example "ElevenLabs quota used up". Work pauses and **resumes by itself** within 10 minutes of the problem being fixed, for example after a top-up.
