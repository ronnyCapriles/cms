"""S3-backed media storage that hands out presigned URLs.

The bucket stays private: nothing is public-read, and every URL the API returns
is a short-lived signature. Signatures are cached for just under their lifetime,
so repeated renders reuse one instead of busting the browser cache each reload.

Configured entirely from the environment (see config.settings). With no bucket
set Django uses FileSystemStorage, so runserver needs no AWS account.
"""
from __future__ import annotations

import mimetypes
import posixpath
import threading
from datetime import timezone
from io import BytesIO
from urllib.parse import quote

from django.conf import settings
from django.core.cache import caches
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import File
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

# Retire a cached signature this long before it expires, so a URL handed out at
# the edge of the window is still valid when it is used.
_SIGNATURE_SKEW = 60


def _setting(name: str, default=None):
    return getattr(settings, name, default)


@deconstructible
class S3MediaStorage(Storage):
    """Django storage over one S3 bucket/prefix, serving presigned GET URLs."""

    def __init__(self, bucket=None, location=None, ttl=None, sign=None):
        self.bucket_name = bucket or _setting("AWS_STORAGE_BUCKET_NAME", "")
        self.location = (location if location is not None
                         else _setting("AWS_LOCATION", "media")).strip("/")
        self.ttl = int(ttl or _setting("AWS_S3_SIGNATURE_TTL", 3600))
        self.sign = _setting("AWS_S3_SIGN_URLS", True) if sign is None else sign
        self.custom_domain = (_setting("AWS_S3_CUSTOM_DOMAIN", "") or "").strip("/")
        self.file_overwrite = _setting("AWS_S3_FILE_OVERWRITE", False)
        self.default_acl = _setting("AWS_DEFAULT_ACL", None)
        self.cache_control = _setting("AWS_S3_CACHE_CONTROL", "max-age=86400")
        self._client = None
        self._lock = threading.Lock()

    @property
    def client(self):
        """Lazy and shared: creating a boto3 client is not cheap."""
        if self._client is None:
            with self._lock:
                if self._client is None:
                    import boto3
                    from botocore.config import Config

                    self._client = boto3.client(
                        "s3",
                        region_name=_setting("AWS_S3_REGION_NAME") or None,
                        endpoint_url=_setting("AWS_S3_ENDPOINT_URL") or None,
                        aws_access_key_id=_setting("AWS_ACCESS_KEY_ID") or None,
                        aws_secret_access_key=_setting("AWS_SECRET_ACCESS_KEY") or None,
                        aws_session_token=_setting("AWS_SESSION_TOKEN") or None,
                        config=Config(
                            # v4 is required for presigned URLs in any region
                            # opened since 2014, harmless in the older ones.
                            signature_version="s3v4",
                            s3={"addressing_style": _setting("AWS_S3_ADDRESSING_STYLE", "virtual")},
                            retries={"max_attempts": 3, "mode": "standard"},
                        ),
                    )
        return self._client

    def _key(self, name: str) -> str:
        """Django file name -> bucket key, refusing to escape the prefix."""
        clean = posixpath.normpath(name.replace("\\", "/")).lstrip("/")
        if clean.startswith("../") or clean == "..":
            raise SuspiciousFileOperation(f"Detected path traversal attempt in '{name}'")
        return posixpath.join(self.location, clean) if self.location else clean

    def get_available_name(self, name, max_length=None):
        # Overwriting is opt-in; Django's suffixing keeps history by default.
        if self.file_overwrite:
            return name
        return super().get_available_name(name, max_length)

    def _open(self, name, mode="rb"):
        if "w" in mode:
            raise ValueError("S3MediaStorage opens files read-only; use _save to write.")
        obj = self.client.get_object(Bucket=self.bucket_name, Key=self._key(name))
        return File(BytesIO(obj["Body"].read()), name)

    def exists(self, name):
        if not name:
            return False
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=self._key(name))
            return True
        except Exception as exc:  # botocore.ClientError, but importing it here is noise
            if getattr(exc, "response", {}).get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            if exc.__class__.__name__ == "ClientError":
                return False
            raise

    def size(self, name):
        head = self.client.head_object(Bucket=self.bucket_name, Key=self._key(name))
        return head["ContentLength"]

    def get_modified_time(self, name):
        head = self.client.head_object(Bucket=self.bucket_name, Key=self._key(name))
        stamp = head["LastModified"]
        return stamp if settings.USE_TZ else stamp.astimezone(timezone.utc).replace(tzinfo=None)

    # S3 keeps no created/accessed time; report the one timestamp it has.
    get_created_time = get_modified_time
    get_accessed_time = get_modified_time

    def listdir(self, path):
        prefix = self._key(path) if path not in ("", ".", "/") else self.location
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        dirs, files = [], []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix, Delimiter="/"):
            dirs += [p["Prefix"][len(prefix):].rstrip("/") for p in page.get("CommonPrefixes", [])]
            files += [o["Key"][len(prefix):] for o in page.get("Contents", []) if o["Key"] != prefix]
        return dirs, files

    def _save(self, name, content):
        key = self._key(name)
        extra = {"CacheControl": self.cache_control}
        guessed = mimetypes.guess_type(name)[0]
        if guessed:
            extra["ContentType"] = guessed
        if self.default_acl:
            extra["ACL"] = self.default_acl

        content.seek(0)
        self.client.upload_fileobj(content, self.bucket_name, key, ExtraArgs=extra)
        return name

    def delete(self, name):
        if not name:
            return
        self.client.delete_object(Bucket=self.bucket_name, Key=self._key(name))
        self._cache().delete(self._cache_key(name))

    def _cache(self):
        return caches["default"]

    def _cache_key(self, name: str) -> str:
        return f"s3url:{self.bucket_name}:{self.location}:{name}"

    def url(self, name, expire=None):
        """A presigned GET URL, cached until shortly before it expires. With
        AWS_S3_SIGN_URLS=0 (bucket behind a public CDN), the plain URL."""
        if not name:
            return ""
        key = self._key(name)

        if not self.sign:
            base = (f"https://{self.custom_domain}" if self.custom_domain
                    else f"https://{self.bucket_name}.s3.amazonaws.com")
            return f"{base}/{quote(key)}"

        ttl = int(expire or self.ttl)
        cache_key = self._cache_key(name)
        cached = self._cache().get(cache_key)
        if cached:
            return cached

        signed = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": key},
            ExpiresIn=ttl,
        )
        self._cache().set(cache_key, signed, max(ttl - _SIGNATURE_SKEW, _SIGNATURE_SKEW))
        return signed

    def signed_upload(self, name, content_type=None, expire=None) -> dict:
        """A presigned POST for uploading straight from a browser. Unused by the
        admin, but here so a client-side uploader can keep the bucket private."""
        fields = {"Content-Type": content_type} if content_type else None
        conditions = [{"Content-Type": content_type}] if content_type else None
        return self.client.generate_presigned_post(
            Bucket=self.bucket_name,
            Key=self._key(name),
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=int(expire or self.ttl),
        )


def media_storage() -> Storage:
    """The storage the media fields actually use, S3 or local."""
    from django.core.files.storage import default_storage
    return default_storage


def is_remote(storage: Storage | None = None) -> bool:
    """True when media lives in S3 — i.e. when URLs are already absolute."""
    return isinstance(storage or media_storage(), S3MediaStorage)


__all__ = ["S3MediaStorage", "media_storage", "is_remote"]
