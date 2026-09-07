# Detasawy — Backend

Django backend for Detasawy, hosted on Railway with Railway PostgreSQL. Currently serves the reference-data API behind the onboarding wizard, the Django admin (superadmin surface), and OpenAPI/Swagger docs.

## Endpoints

| Path                          | What                                              |
| ----------------------------- | ------------------------------------------------- |
| `/api/health`                 | Health check (Railway healthcheck)                |
| `/api/auth/signup`            | POST — create account (name, email, password, consent) → token |
| `/api/auth/login`             | POST — email + password → token + profile         |
| `/api/auth/logout`            | POST — revoke the token                           |
| `/api/auth/me`                | GET — current user + profile (token auth)         |
| `/api/profile`                | PUT — save the contributor profile (token auth)   |
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
- `SECRET_KEY` — any long random string
- `ALLOWED_HOSTS` — optional, defaults to `*`; set to your domains when stable
- `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD` (+ optional `_EMAIL`) — one-time superuser creation for `/admin/`

CORS allows `detasawy.com`, `www.detasawy.com`, `localhost:3000`, and `*.vercel.app` previews (see `config/settings.py`).
