# Session, media and rate-limit rollout

## Implemented controls

- Database-backed HttpOnly, SameSite=Lax session cookies; Secure and `__Host-` prefix in production. No authentication tokens in frontend localStorage or JSON login responses.
- Fixed expiry: one hour for staff/superadmins, eight hours for contributors, including Django admin sign-in. Logout revokes the current session; password changes invalidate sessions through Django's session authentication hash.
- CSRF validation on all unsafe API requests, including anonymous login. GET `/api/auth/csrf` provides a masked token; send it in `X-CSRFToken`. Login rotates it. Cookie and authentication responses use `private, no-store`.
- Production startup rejects weak/missing secrets, wildcard hosts and insecure/wildcard trusted origins. HTTPS redirects, secure cookies, HSTS, frame denial and content-type sniffing protection are enabled.
- Recordings and profile photos require ownership or superadmin access. Photos stay in the database; recording files require a persistent Railway volume attached to the backend at `MEDIA_ROOT`. Storage paths and blob hashes do not grant access. Prompt media remains public. Audio supports authenticated range requests.
- Shared PostgreSQL counters lock rows inside transactions. Limits apply across workers and restarts, with HTTP 429 and Retry-After. Counter keys are keyed hashes rather than stored emails/IP addresses.

| Limit | Window |
| --- | --- |
| Login per IP (API and Django admin combined) | 10/minute and 100/hour |
| Login per normalized account | 10/minute and 30/hour |
| API per authenticated user / anonymous IP | 300 / 120 per minute |
| Unsafe API operations | 60/minute |
| Multipart uploads | 20/minute and 200/day |

Successful login attempts also count. These are application abuse controls, not protection against network-level denial of service; edge request/body limits remain necessary. Invalid requests rejected before throttling may not count.

## Required production configuration

1. Keep `DEBUG=false`. Set a unique random `SECRET_KEY` of at least 50 characters through Railway's secret variables. Do not put it in Git. Keep the existing PostgreSQL `DATABASE_URL`. Attach a persistent volume to the **backend** service and set `MEDIA_ROOT` to its mount path for recordings; a volume attached only to Postgres does not preserve backend uploads.
2. Set `ALLOWED_HOSTS` to exact actual backend/frontend hosts. Defaults are `detasawybackend-production.up.railway.app,detasawy.com,www.detasawy.com`. No wildcard hosts.
3. Set `CSRF_TRUSTED_ORIGINS` to exact HTTPS frontend and backend origins. `CORS_ALLOWED_ORIGINS` allows only exact frontend origins. Preview deployments must use a separate staging backend/configuration, or be explicitly authorized by exact origin.
4. Frontend `BACKEND_URL` must point to the intended backend. Browser requests and private media must use the same-origin `/api/*` rewrite. `NEXT_PUBLIC_API_BASE` is no longer used. Ensure the edge forwards Cookie/Set-Cookie and honors `Cache-Control: private, no-store`; do not cache authenticated APIs or private media.
5. `TRUSTED_PROXY_HOPS=0` ignores client-supplied X-Forwarded-For. Before live rollout, verify the real Vercel → Railway header chain and backend reachability. Only enable a positive hop count when those hops append/overwrite headers reliably and cannot be bypassed. A guessed value lets clients evade IP limits; leaving zero behind a proxy can group unrelated anonymous users under a single limit. Account/user limits remain separate. Do not trust a client-supplied Vercel header at a publicly reachable Railway origin.

## Deployment order and verification

This is a coordinated authentication change. An old frontend cannot log into the new backend; the new frontend cannot use the old backend. Prepare both builds and production configuration first, then use a short maintenance window for backend migration/deploy followed immediately by the frontend. All users must log in again.

- Apply migrations, including `identity.0004_ratelimitbucket`, before serving requests. The existing Railway start command runs migrations.
- Run `python manage.py check --deploy` with actual production settings. Verify the health probe and HTTPS proxy header behavior before opening traffic.
- Verify sign-in, `/api/auth/me`, a CSRF-protected write, logout, and failed replay of the logged-out cookie through the frontend domain. Check cookie flags and private cache headers at the public edge.
- Verify unauthenticated/direct old recording/photo links fail, while authorized audio playback and public prompt images work.
- Purge any previously cached contributor-media URLs from a CDN if used. Existing downloaded copies cannot be retracted. If optional external object storage is enabled, enforce private bucket/object access there as well; application authorization cannot revoke a public storage URL.
- Run `python manage.py clear_security_state` daily from a scheduled Railway maintenance job to remove expired sessions/counters. Expiry is enforced on requests even before cleanup. The command is provided; scheduling is a deployment operation.
- Monitor 401/403/429 rates after rollout and tune limits against real workload. Do not resolve proxy misconfiguration by disabling authentication or trusting arbitrary headers.

Rolling back only one repository breaks login. Restore both matching versions together if required. Do not restore public contributor-media routing as a workaround.

## Local verification

Use an isolated database for tests:

```powershell
$env:DEBUG='true'
$env:DATABASE_URL='sqlite:///:memory:'
.venv/Scripts/python.exe manage.py test --noinput
```

Run the backend locally with DEBUG=true and the frontend with `BACKEND_URL=http://127.0.0.1:8000`. Development cookies deliberately omit Secure so HTTP localhost works. Do not use DEBUG=true in production. PostgreSQL locking/concurrency and the public proxy chain need staging/production verification; SQLite tests do not establish those deployment properties.
