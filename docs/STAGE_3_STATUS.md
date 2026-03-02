# Stage 3 Status

## Scope Implemented

Stage 3 (UI + Live updates) is implemented end-to-end.

1. Web UI served by FastAPI static hosting
2. Login + tenant session flow
3. Dashboard for package usage and weekly/monthly activity
4. Search and filtering by date
5. Conversation view with audio player + synchronized transcript
6. Word click-to-seek and current-word highlight
7. In-page word search highlight (separate color)
8. Conversation details panel
9. Export downloads: TXT, SRT, DOCX
10. Live tenant updates via WebSocket

## Backend Additions

1. `backend/app/api/routes_dashboard.py`
- `/dashboard/usage`
- `/dashboard/activity?period=week|month`

2. `backend/app/api/routes_ws.py`
- `/ws/tenant`

3. `backend/app/api/routes_jobs.py`
- date filtering (`date_from`, `date_to`)
- audio endpoints (`/audio`, `/audio-public`)
- export endpoint (`/export?format=txt|srt|docx`)

4. `backend/app/services/exports.py`
- TXT/SRT/DOCX rendering

5. DB extension
- tenant package quota field (`tenants.package_minutes_quota`)

## Frontend (Single Page)

1. `backend/app/static/index.html`
2. `backend/app/static/styles.css`
3. `backend/app/static/app.js`

Key UX behavior implemented:

- Player + transcript sync by word timestamp
- Active spoken word highlight
- Click on word seeks audio to word timestamp
- Search in transcript with separate highlight color
- Toggle between transcript view and details view
- Download export files from details view
- Realtime queue/live status indicator from WS

## Validation Results

1. `/` returns web app shell
2. `/dashboard/usage` and `/dashboard/activity` return valid payloads
3. `/jobs` date filtering works
4. `/jobs/{id}/audio` and `/jobs/{id}/audio-public` stream audio
5. `/jobs/{id}/export` works for TXT/SRT/DOCX
6. `/ws/tenant` sends live updates

## Model Policy Check

Stage 3 keeps the primary model unchanged:

- `ivrit-ai/whisper-large-v3`
