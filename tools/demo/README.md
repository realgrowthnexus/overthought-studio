# Demo copy (local only)

A full copy of the dashboard on a local Supabase with made-up data, for UI checks and the video guide.
It never touches the live project; `seed_demo.py` refuses any non-local Supabase URL.

    bash tools/demo/up.sh                 # Docker + local Supabase (real migrations) + dashboard on :3000
    python tools/demo/seed_demo.py        # demo data (idempotent)
    node tools/demo/login.cjs             # demo owner owner@demo.local, saves tools/demo/.state.json
    node tools/demo/ui-check.cjs          # layout / loading / console checks at 375 and 1280 px
    node tools/demo/hover-check.cjs [--theme dark]   # every clickable: hand cursor + visible hover (0 problems expected)
    node tools/demo/flow-check.cjs        # settings save, API fallback switch, channel voice, wizard steps
    python tools/demo/seed_demo.py red-bar on|off

Stop: `cd tools/demo/.supabase && npx supabase@2 stop` and `pkill -f "next start -p 3000"`.
Note: `apps/web/.next` is then built for localhost; the VPS builds its own, so this never ships.
