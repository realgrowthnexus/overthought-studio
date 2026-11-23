-- 0004: ElevenLabs replaced by the free Kokoro voice that runs inside the worker.
-- * services: 'elevenlabs' row → 'voice'
-- * channels still on an ElevenLabs voice get their Kokoro voice (by slug; anything else gets the default)
-- * the ElevenLabs key is not used any more
-- * dashboard previews are kept 7 days after posting (keeps Supabase inside the free plan)
insert into public.services(name) values ('voice') on conflict (name) do nothing;
delete from public.services where name = 'elevenlabs';

update public.channels set voice = jsonb_build_object(
  'provider', 'kokoro',
  'voice', case slug
    when 'overthought' then 'am_michael+am_fenrir'
    when 'money-brain' then 'am_onyx'
    when 'tiny-history' then 'bm_george'
    when 'how-it-works' then 'af_heart'
    when 'myth-busted' then 'af_bella'
    else 'am_michael+am_fenrir' end,
  'speed', 1.0)
where coalesce(voice->>'provider', 'elevenlabs') <> 'kokoro';

delete from public.secrets where key = 'elevenlabs_api_key';

update public.settings
   set value = jsonb_set(value, '{video_retention_days}', '7'::jsonb)
 where key = 'global' and coalesce((value->>'video_retention_days')::int, 21) > 7;
