# rates.swissblue.sa robot (v2)

Multi-page site: home (choose a hotel) → one page per hotel with 4 calendars, today + 30 nights:
1. All nearby places on **Booking.com** (map search around the hotel; rooms/studios/1BR with reviews, radius in `hotels.json`).
2. All nearby places on **Agoda** (area search; Agoda's own price before taxes; our listing id in `hotels.json`).
3. Hand-picked competitors on **Expedia** (read from Google Hotels; Expedia blocks robots on its own site; Hotels.com when Expedia has no price).
4. **Average of 5 platforms** for the hand-picked competitors: Booking.com, Agoda, Expedia, Hotels.com, Trip.com (Google Hotels, ÷ 1.17875).

Files: `collect.cjs` (one hotel, all sources, time budget per source), `build.py raw prev out` (tables + HTML; a source that failed keeps its last
good table), `hotels.json` (coordinates, radius, Agoda area/own id, Google entity ids of the hand-picked competitors),
`site/` (CSS/JS, `api/sync.js` + `api/status.js` for the **Sync now** button, `vercel.json` noindex).
Workflow: `.github/workflows/rates.yml` (4 hotels in parallel ~16 min, then publish to Vercel project `swissblue-rates`).

## Schedule
`.github/workflows/rates.yml`: every 8 hours (03:17, 11:17, 19:17 Riyadh) and on demand (Actions tab → rates → Run workflow,
or the Sync now button). This repo is public so GitHub Actions minutes are free and unlimited. No keys are stored in the code;
the Vercel token is the repository secret `VERCEL_TOKEN`.

## Sync now button
Vercel project `swissblue-rates` → Settings → Environment Variables (Production):
- `GH_TOKEN` = GitHub fine-grained token, only repository `swissblue-rates-bot`, permission **Actions: Read and write**.
- optional `GH_REPO` (default `dubaiincairo/swissblue-rates-bot`), `GH_WORKFLOW` (default `rates.yml`).
Redeploy. The button refuses a new sync while one runs or within 20 minutes of the last one.
