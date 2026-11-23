# TikTok developer app: form answers (phase 1, drafts only)

**App name:** Overthought Studio · **Icon:** `app-icon-1024.png` · **Category:** Utility / Productivity (any "content tools" option)

**Description** (max 120):

Overthought Studio uploads our own short educational videos to our own TikTok accounts as drafts for us to post.

**Products:** Login Kit + Content Posting API (Upload to drafts). Direct Post OFF.
**Scopes (keep exactly these):** user.info.basic, user.info.profile, user.info.stats, video.list, video.upload.
Remove video.publish, video.manage, video.collab and any other scope.

**Explain how each scope is used** (max 1000):

Overthought Studio is a private web dashboard (studio.getgrowthnexus.com) used only by its owner to manage the owner's own TikTok accounts. The owner creates short educational videos in the dashboard, reviews and approves each one, then sends it to TikTok.
- user.info.basic: log in with TikTok and show which account is connected (avatar and display name).
- user.info.profile: show the account's username on the TikTok accounts page so each video goes to the right account.
- user.info.stats: show follower, like and video counts on the account card and in weekly reports.
- video.list: list the account's videos with their view, like, comment and share counts on the Analytics page.
- video.upload: send an approved video to the account's TikTok drafts (inbox). The owner then opens the TikTok app, checks the caption and posts it themselves.

**Demo video** (record the screen, mp4, under 50 MB, use the SANDBOX app + a sandbox target user):
1. Show the address bar: https://studio.getgrowthnexus.com, then log in.
2. TikTok accounts → Connect account → TikTok's login screen lists the 5 scopes → Authorize.
3. Back on the dashboard: the account card shows avatar, @username, followers/likes/videos (user.info.basic, profile, stats).
4. Open a ready video → Approve → Publish now (mode "TikTok drafts") → status changes to "Sent to drafts" (video.upload).
5. On the phone: TikTok notification/inbox → open the draft → it is our video → Post.
6. Back on the dashboard: Analytics → sync → the posted video appears with its views and likes (video.list).
