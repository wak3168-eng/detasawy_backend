import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY and DEBUG:
    SECRET_KEY = "local-development-only-not-for-production"
if not DEBUG and (
    len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5
    or SECRET_KEY.startswith("django-insecure-")
    or SECRET_KEY == "dev-insecure-key-change-me"
):
    raise ImproperlyConfigured("Production requires a unique SECRET_KEY of at least 50 characters.")

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get(
        "ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]" if DEBUG else
        "detasawybackend-production.up.railway.app,detasawy.com,www.detasawy.com"
    ).split(",") if h.strip()
]
if not DEBUG and (not ALLOWED_HOSTS or any(h == "*" or h.startswith(".") for h in ALLOWED_HOSTS)):
    raise ImproperlyConfigured("ALLOWED_HOSTS must list exact production hostnames.")

# Railway terminates TLS at its edge and forwards plain HTTP inside, so Django
# has to be told what the browser actually asked for. Without this every media
# URL it builds says http://, and the https site reports mixed content.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        "https://detasawy.com,https://www.detasawy.com,https://detasawybackend-production.up.railway.app",
    ).split(",")
    if o.strip()
]
if DEBUG:
    CSRF_TRUSTED_ORIGINS += ["http://localhost:3000", "http://localhost:3010", "http://127.0.0.1:8000"]
if not DEBUG and any("*" in o or not o.startswith("https://") for o in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must contain exact HTTPS origins.")

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "detasawy_session" if DEBUG else "__Host-detasawy_session"
SESSION_COOKIE_AGE = 8 * 60 * 60
ADMIN_SESSION_AGE = 60 * 60
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_SAVE_EVERY_REQUEST = False  # Fixed lifetime, not extended by background requests.
CSRF_COOKIE_NAME = "detasawy_csrf" if DEBUG else "__Host-detasawy_csrf"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True  # A masked token is supplied by /api/auth/csrf.
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = not DEBUG
SECURE_REDIRECT_EXEMPT = [r"^api/health$"]  # Railway's internal health probe.
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# Set only after verifying how many trusted proxies append to X-Forwarded-For.
# Zero ignores client-supplied forwarding headers and uses REMOTE_ADDR.
TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS", "0"))
if TRUSTED_PROXY_HOPS < 0:
    raise ImproperlyConfigured("TRUSTED_PROXY_HOPS cannot be negative.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "corsheaders",
    "apps.identity",
    "apps.ref",
    "apps.corpus",
    "apps.portal",
]

AUTH_USER_MODEL = "identity.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.identity.middleware.PrivateResponseMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.config(conn_max_age=600),
    }
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "dev.sqlite3",
        },
    }
else:
    raise ImproperlyConfigured(
        "DATABASE_URL is required in production. On Railway, add a variable "
        "reference to the Postgres service on the backend service.",
    )

# SQLite has no row locks. Acquire its write lock at transaction entry so
# concurrent local requests cannot deadlock while upgrading read transactions.
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {}).update(
        transaction_mode="IMMEDIATE", timeout=20,
    )

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

# S3-compatible media (R2 etc.) when configured; local disk otherwise —
# attach a Railway volume and set MEDIA_ROOT for the local mode to persist.
USE_S3_MEDIA = bool(os.environ.get("S3_BUCKET"))

STORAGES = {
    "default": (
        {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": os.environ.get("S3_BUCKET", ""),
                "endpoint_url": os.environ.get("S3_ENDPOINT", ""),
                "access_key": os.environ.get("S3_ACCESS_KEY_ID", ""),
                "secret_key": os.environ.get("S3_SECRET_ACCESS_KEY", ""),
                "region_name": os.environ.get("S3_REGION", "auto"),
                "default_acl": None,
                "querystring_auth": False,
                "custom_domain": os.environ.get("S3_PUBLIC_DOMAIN") or None,
            },
        }
        if USE_S3_MEDIA
        else {"BACKEND": "django.core.files.storage.FileSystemStorage"}
    ),
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.identity.authentication.CookieSessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": ["apps.identity.throttles.ApiThrottle"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Detasawy API",
    "DESCRIPTION": "Reference-data API for Detasawy, the community-built data portal for the Pashto language.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "https://detasawy.com,https://www.detasawy.com",
    ).split(",")
    if o.strip()
]
CORS_ALLOWED_ORIGIN_REGEXES = []
if not DEBUG and any("*" in o or not o.startswith("https://") for o in CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must contain exact HTTPS origins.")
if DEBUG:
    # the local dev server picks a free port when 3000 is taken
    CORS_ALLOWED_ORIGIN_REGEXES.append(r"^http://localhost:\d+$")
