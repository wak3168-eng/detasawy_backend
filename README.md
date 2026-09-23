# Detasawy — Backend

Django backend for Detasawy, hosted on Railway with Railway PostgreSQL. Currently serves the reference-data API behind the onboarding wizard, the Django admin (superadmin surface), and OpenAPI/Swagger docs.

## Endpoints

| Path                          | What                                              |
| ----------------------------- | ------------------------------------------------- |
| `/api/health`                 | Health check (Railway healthcheck)                |
| `/api/auth/csrf`              | GET — masked CSRF token and HttpOnly CSRF cookie |
| `/api/auth/signup`            | POST — disabled during the invitation-only pilot |
| `/api/auth/login`             | POST — email + password + CSRF → session cookie, user, profile |
| `/api/auth/logout`            | POST — revoke the current session (requires CSRF) |
| `/api/auth/me`                | GET — current user + profile (cookie session)    |
| `/api/profile`                | PUT — save contributor profile (session + CSRF)  |
| `/api/ref/provinces?country=` | Provinces of a country (`pk`, `af`, `overseas`)   |
| `/api/ref/districts?province=`| Districts of a province (+ `hasTehsils`, language)|
| `/api/ref/tehsils?district=`  | Tehsils of a district                             |
| `/api/ref/tribes?district=`   | Root tribes, dominant-in-district first           |
| `/api/ref/tribes?parent=`     | Children of a tribe node                          |
| `/api/docs`                   | Swagger UI (`/api/redoc`, `/api/schema` too)      |
| `/admin/`                     | Django admin                                      |

Responses use the frontend's `RefOption` shape: `{id, name, ps?, aliases?, hasChildren?, hasTehsils?, language?}`.

## Structure

```
config/         settings, urls, wsgi
apps/ref/       models, views, urls, admin, seed + superuser commands
data/           geography.json, tribes.json (seed source, from the community data drops)
```

Modular rule: each future plane gets its own app (`identity`, `corpus`, `portal`, `analytics`) beside `apps/ref`.

## Run locally

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
set DEBUG=true
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_ref
.venv\Scripts\python manage.py runserver
```

Without `DATABASE_URL` and with `DEBUG=true` it uses a local SQLite file.

## Deploy on Railway

The service builds from `requirements.txt` automatically; `railway.json` runs collectstatic → migrate → seed_ref → ensure_superuser → gunicorn, with `/api/health` as the healthcheck.

Required service variables:

- `DATABASE_URL` — add a variable reference to the Postgres service
- `SECRET_KEY` — unique, cryptographically random value of at least 50 characters; missing/weak values prevent production startup
- `ALLOWED_HOSTS` — comma-separated exact production hosts; wildcard hosts are rejected
- `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD` (+ optional `_EMAIL`) — one-time superuser creation for `/admin/`

CORS and CSRF allow the exact production origins in `config/settings.py`; arbitrary Vercel previews are not trusted. Localhost is allowed only in development. Browser API calls must use the frontend's same-origin `/api/*` proxy.

Read [SECURITY.md](SECURITY.md) before deploying the session migration. Both repositories must be deployed together; old bearer tokens no longer authenticate requests.
