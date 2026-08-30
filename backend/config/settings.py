"""Django settings. SQLite, one `portfolio` app, no other third-party apps."""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# A .env beside the project or beside manage.py, so runserver and docker run
# see the same config.
try:
    from dotenv import load_dotenv

    for _candidate in (BASE_DIR.parent / ".env", BASE_DIR / ".env"):
        if _candidate.exists():
            load_dotenv(_candidate, override=False)
except ImportError:  # python-dotenv is optional in production images
    pass

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver"
).split(",")

# Needs the scheme (https://example.com). Admin login fails without it.
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "portfolio",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "portfolio" / "templates"],
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

# timeout = how long a blocked writer waits before "database is locked".
# The 5s default is too short for a slow admin save.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH") or BASE_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TZ", "America/Caracas")
USE_I18N = True
USE_TZ = True

# Languages the CMS content is served in. UI chrome is translated in the React
# bundle instead; see portfolio/i18n.py.
CONTENT_LANGUAGES = ["en", "es"]
CONTENT_LANGUAGE_DEFAULT = os.environ.get("PORTFOLIO_DEFAULT_LANG", "en")

STATIC_URL = "/static/"
# Vite builds into portfolio/static/app/, so staticfiles finds it as-is.
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Media in S3. Set the bucket name and uploads go to S3 as presigned URLs, so
# the bucket stays private. Unset, Django writes to MEDIA_ROOT.
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_SESSION_TOKEN = os.environ.get("AWS_SESSION_TOKEN", "")
# Set for S3-compatible stores (MinIO, R2, B2).
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "")
AWS_S3_ADDRESSING_STYLE = os.environ.get("AWS_S3_ADDRESSING_STYLE", "virtual")
# Key prefix, so one bucket can hold several environments.
AWS_LOCATION = os.environ.get("AWS_S3_LOCATION", "media")
# Signature lifetime. URLs are cached for nearly this long, so it also bounds
# how stale a page's media links can be.
AWS_S3_SIGNATURE_TTL = int(os.environ.get("AWS_S3_SIGNATURE_TTL", "3600"))
# Only turn signing off when a public CDN fronts the bucket.
AWS_S3_SIGN_URLS = os.environ.get("AWS_S3_SIGN_URLS", "1") == "1"
AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "")
AWS_S3_FILE_OVERWRITE = os.environ.get("AWS_S3_FILE_OVERWRITE", "0") == "1"
AWS_S3_CACHE_CONTROL = os.environ.get("AWS_S3_CACHE_CONTROL", "max-age=86400")
# A private bucket wants no ACL; set one only for pre-Object-Ownership buckets.
AWS_DEFAULT_ACL = os.environ.get("AWS_DEFAULT_ACL", "") or None

USE_S3_MEDIA = bool(AWS_STORAGE_BUCKET_NAME)

STORAGES = {
    "default": {
        "BACKEND": "portfolio.storages.S3MediaStorage" if USE_S3_MEDIA
        else "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Which design direction the React app renders: a | b | c
PORTFOLIO_THEME = os.environ.get("PORTFOLIO_THEME", "a")


# Cloudflare terminates TLS, so requests arrive over plain HTTP and
# request.is_secure() is False until Django is told which header to trust.
# Without this, secure cookies are never set and HTTPS redirects can loop.
if os.environ.get("DJANGO_BEHIND_PROXY", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Off by default: Cloudflare already redirects. Only matters for requests
    # that reach the origin directly.
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SSL_REDIRECT", "0") == "1"

# With DEBUG off Django serves no static files; WhiteNoise does it instead of a
# second nginx container. Compressed rather than Manifest storage: Vite already
# content-hashes every filename, and re-hashing can fail on a url() Vite emitted.
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedStaticFilesStorage"
WHITENOISE_MAX_AGE = int(os.environ.get("DJANGO_STATIC_MAX_AGE", "31536000"))
