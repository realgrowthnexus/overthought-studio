# TikTok API notes (verified from developers.tiktok.com, 2026-11-18)

- OAuth authorize: GET https://www.tiktok.com/v2/auth/authorize/ ?client_key&scope(comma)&response_type=code&redirect_uri&state  (PKCE not required for web)
- Token: POST https://open.tiktokapis.com/v2/oauth/token/ (x-www-form-urlencoded) client_key, client_secret, code, grant_type=authorization_code, redirect_uri
  -> access_token, expires_in, refresh_token, refresh_expires_in, open_id, scope. Refresh tokens ROTATE; read lifetimes from response.
- Refresh: same endpoint, grant_type=refresh_token.
- Scopes we need: user.info.basic,user.info.profile,user.info.stats,video.list,video.upload,video.publish
- User info: GET /v2/user/info/?fields=open_id,avatar_url,display_name,username,is_verified,follower_count,following_count,likes_count,video_count
- Creator info: POST /v2/post/publish/creator_info/query/ -> privacy_level_options, max_video_post_duration_sec, *_disabled
- Direct post: POST /v2/post/publish/video/init/ {post_info:{title,privacy_level,disable_duet,disable_comment,disable_stitch,video_cover_timestamp_ms,brand_content_toggle,brand_organic_toggle,is_aigc}, source_info:{source:FILE_UPLOAD,video_size,chunk_size,total_chunk_count}}
  Unaudited -> private only (unaudited_client_can_only_post_to_private_accounts). 6 req/min.
- Inbox draft: POST /v2/post/publish/inbox/video/init/ {source_info:{...}} ; max 5 pending shares / 24h. No caption field (user adds in app).
- Upload: PUT upload_url, headers Content-Type: video/mp4, Content-Length, Content-Range: bytes a-b/total. Chunks 5–64MB (last up to 128MB), files <5MB one chunk; total_chunk_count = floor(size/chunk). 206 more / 201 done.
- Status: POST /v2/post/publish/status/fetch/ {publish_id} -> status PROCESSING_UPLOAD|SEND_TO_USER_INBOX|PUBLISH_COMPLETE|FAILED, fail_reason, publicaly_available_post_id[]
- Video list: POST /v2/video/list/?fields=... {cursor,max_count<=20} public videos only.
- Video query: POST /v2/video/query/?fields=id,create_time,cover_image_url,share_url,title,duration,like_count,comment_count,share_count,view_count {filters:{video_ids:[..<=20]}}
- No watch-time / completion via API -> manual TikTok Studio CSV import.
- Video limits: H.264 MP4, 23–60fps, max 10 min via API.
