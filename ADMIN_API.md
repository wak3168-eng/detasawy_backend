# Admin workspace API

All endpoints use the existing `Authorization: Token ...` authentication. The UI verifies the current role through `/api/auth/me`; each endpoint also enforces its own permission.

| Endpoint | Access | Query / behaviour |
| --- | --- | --- |
| GET `/api/admin/overview` | Staff | Collection counts, excluding blank text and non-picture prompts from picture coverage |
| GET `/api/admin/prompts` | Superadmin, campaign manager | `page`, `pageSize` (1–50, default 20), `q` (English/Pashto caption), `kind`, `active=true/false` |
| POST `/api/admin/prompts` | Superadmin, campaign manager | Exactly one media file or HTTP(S) media URL; kind, captions, source URL, licence. Images for picture/scene; audio for voice. File limit 20 MB |
| POST `/api/admin/prompts/{id}` | Superadmin, campaign manager | Boolean `active` |
| GET `/api/admin/contributions` | Superadmin | `page`, `pageSize`, `q`, `kind`, `prompt`, `audio=yes/no`. Original text, audio URL or null, district, timestamps. No contributor emails in this response |
| GET `/api/admin/dataset` | Superadmin | `q`, `all=0/1`, `limit` (1–50), `offset`. Aggregated source records, not an approval system |
| GET `/api/admin/users` | Superadmin | `page`, `pageSize`, `q` (name/email). Existing account creation and role routes remain supported |
| GET/POST `/api/admin/campaigns` | Superadmin, campaign manager | Existing list/create contract; validated date interval and canonical province/district scope |
| GET `/api/admin/suggestions` | Superadmin, reviewer | Existing reference-review contract; unrelated to contribution approval |

Paginated prompt, user and contribution responses contain `{items, total, page, pageSize}`. Prompt/user callers omitting `page` retain the old array response. Invalid pagination or create input returns HTTP 400. Contributions without audio return `audioUrl: null`.

Deploy this backend before the new frontend. No model migration is required. The frontend uses a same-origin `/api/*` rewrite; its server-side `BACKEND_URL` must point to this backend. Existing explicit `NEXT_PUBLIC_API_BASE` deployments continue using that origin and require corresponding CORS configuration.

Audio uses the existing storage backend. Production must retain its S3 configuration or persistent media volume for uploaded recordings to survive redeploys. This redesign does not move audio storage or introduce dataset approval/export workflows.

Run regression tests against an isolated database, e.g. PowerShell:

```powershell
$env:DEBUG='true'
$env:DATABASE_URL='sqlite:///:memory:'
.venv/Scripts/python.exe manage.py test --noinput
```
