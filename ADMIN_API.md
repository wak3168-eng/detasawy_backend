# Admin workspace API

All endpoints use HttpOnly cookie sessions. Fetch `/api/auth/csrf`, then send its `csrfToken` as `X-CSRFToken` for login and every unsafe request. Login rotates the CSRF token and returns the new value. The UI verifies the current role through `/api/auth/me`; each endpoint also enforces its own permission. Bearer tokens are no longer accepted.

| Endpoint | Access | Query / behaviour |
| --- | --- | --- |
| GET `/api/admin/overview` | Staff | Collection counts, excluding blank text and non-picture prompts from picture coverage |
| GET `/api/admin/prompts` | Superadmin, campaign manager | `page`, `pageSize` (1–50, default 20), `q` (English/Pashto caption), `kind`, `active=true/false` |
| POST `/api/admin/prompts` | Superadmin, campaign manager | Exactly one media file or HTTP(S) media URL; kind, captions, source URL, licence. Images for picture/scene; audio for voice. File limit 20 MB |
| POST `/api/admin/prompts/{id}` | Superadmin, campaign manager | Boolean `active` |
| GET `/api/admin/contributions` | Superadmin | `page`, `pageSize`, `q`, `kind`, `prompt`, `audio=yes/no`. Original text, audio URL or null, district, timestamps. No contributor emails in this response |
| GET `/api/admin/dataset` | Superadmin | `q`, `all=0/1`, `limit` (1–50), `offset`, `groupBy`, `group`, `minSample`. The combined prompt-and-answer collection, dynamically sliced by country, province, district, tehsil, tribe, clan or subclan. Includes usage shares and a conservative representative-word result |
| GET `/api/admin/users` | Superadmin | `page`, `pageSize`, `q` (name/email). Existing account creation and role routes remain supported |
| GET/POST `/api/admin/campaigns` | Superadmin, campaign manager | Existing list/create contract; validated date interval and canonical province/district scope |
| GET `/api/admin/suggestions` | Superadmin, reviewer | Existing reference-review contract; unrelated to contribution approval |

Paginated prompt, user and contribution responses contain `{items, total, page, pageSize}`. Prompt/user callers omitting `page` retain the old array response. Invalid pagination or create input returns HTTP 400. Contributions without audio return `audioUrl: null`.

Deploy this backend and the matching frontend together, following [SECURITY.md](SECURITY.md). Migrations preserve and snapshot contribution geography. The frontend uses a same-origin `/api/*` rewrite; its server-side `BACKEND_URL` must point to this backend. Browser code no longer uses `NEXT_PUBLIC_API_BASE`.

Audio uses the configured storage backend. On Railway, attach a persistent volume to the backend service and set `MEDIA_ROOT` to its mount path; the database volume alone does not preserve recordings. Authenticated owners and superadmins can stream `/api/private/contributions/{id}/audio`, including byte-range seeking. Other users cannot access the recording. Profile photos follow the same ownership rule at `/api/private/profiles/{userId}/photo`. Private responses are never cacheable. Legacy direct private media URLs return 404. Prompt images/audio remain public.

Run regression tests against an isolated database, e.g. PowerShell:

```powershell
$env:DEBUG='true'
$env:DATABASE_URL='sqlite:///:memory:'
.venv/Scripts/python.exe manage.py test --noinput
```
