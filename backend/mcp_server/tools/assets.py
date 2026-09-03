"""Write tools for images and video.

No fetch-by-URL tool: the instance has no IPv4 route out, so one would work only
for hosts publishing an AAAA record.
"""
from __future__ import annotations

import base64
import binascii
import posixpath

from django.conf import settings
from django.core.files.base import ContentFile

from portfolio.models import Asset

from . import ToolError, tool
from . import common

_ASSET_FIELDS = {
    "kind": {"type": "string", "enum": common.CHOICES["asset_kind"]},
    "ratio": {"type": "string", "enum": common.CHOICES["asset_ratio"]},
    "caption": {"type": "string", "maxLength": 240},
    "alt": {"type": "string", "maxLength": 240,
            "description": "Alternative text. Falls back to the caption."},
    "ref": {"type": "string", "description": "Readable handles work well: architecture."},
    "order": {"type": "integer"},
    "language": {"type": "string"},
}

UPLOAD_TARGETS = {
    "asset_image": ("asset", "image"),
    "asset_video": ("asset", "video"),
    "asset_poster": ("asset", "poster"),
    "project_cover": ("project", "cover"),
    "profile_portrait": ("profile", "portrait"),
    "profile_cv": ("profile", "cv"),
}


@tool(
    name="create_asset",
    title="Create an asset slot",
    description="""
    Create the image or video slot on a project and return its shortcode. The row
    exists before the file does: an asset with nothing uploaded renders as a
    labelled placeholder of the right shape, so the layout can be judged first.
    Upload the file with upload_media.
    """,
    schema={
        "properties": {"project": {"type": "string", "description": "Project slug."},
                       **_ASSET_FIELDS},
        "required": ["project", "kind"],
    },
)
def create_asset(args, ctx):
    project = common.get_project(args["project"])
    common.check_language(args.get("language"))
    asset = Asset(
        project=project, **{k: v for k, v in args.items() if k in common.ASSET_WRITABLE}
    )
    asset.full_clean(exclude=["ref"])
    asset.save()
    return {
        "created": True,
        "project": project.slug,
        "ref": asset.ref,
        "shortcode": asset.shortcode,
        "kind": asset.kind,
        "ratio": asset.ratio,
        "has_file": False,
        "next": f"Upload the file with upload_media, then place it by putting "
                f"{asset.shortcode} on its own line in body_md.",
    }


@tool(
    name="update_asset",
    title="Update an asset",
    idempotent=True,
    description="Edit an asset's kind, ratio, caption, alt text, ref or order.",
    schema={
        "properties": {
            "project": {"type": "string"},
            "ref": {"type": "string"},
            "fields": {"type": "object", "properties": _ASSET_FIELDS,
                       "additionalProperties": False},
        },
        "required": ["project", "ref", "fields"],
    },
)
def update_asset(args, ctx):
    project = common.get_project(args["project"])
    asset = common.get_asset(project, args["ref"])
    fields = args.get("fields") or {}
    common.check_language(fields.get("language"))
    old_shortcode = asset.shortcode

    changed = common.apply_fields(asset, fields, common.ASSET_WRITABLE)
    if changed:
        asset.full_clean()
        asset.save()

    result = {"changed": changed, "ref": asset.ref, "shortcode": asset.shortcode}
    if "ref" in changed:
        result["warning"] = (
            f"The ref changed, so {old_shortcode} in any body no longer resolves. "
            f"Replace it with {asset.shortcode}."
        )
    return result


@tool(
    name="upload_media",
    title="Upload a file",
    description="""
    Store a base64 encoded file against an asset, a project cover, or the site
    portrait or CV. Limited to 6 MB decoded; for anything larger use
    presign_upload and PUT the bytes straight to storage.
    """,
    schema={
        "properties": {
            "target": {"type": "string", "enum": sorted(UPLOAD_TARGETS)},
            "filename": {"type": "string", "description": "Used for the extension."},
            "content_base64": {"type": "string"},
            "project": {"type": "string",
                        "description": "Required for asset_* and project_cover."},
            "ref": {"type": "string", "description": "Required for asset_*."},
        },
        "required": ["target", "filename", "content_base64"],
    },
)
def upload_media(args, ctx):
    kind, field = _target(args["target"])
    owner = _owner(kind, args)

    try:
        blob = base64.b64decode(args["content_base64"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ToolError(f"content_base64 is not valid base64: {exc}") from exc

    if not blob:
        raise ToolError("content_base64 decoded to zero bytes.")
    if len(blob) > common.MAX_UPLOAD_BYTES:
        raise ToolError(
            f"{len(blob)} bytes exceeds the {common.MAX_UPLOAD_BYTES} byte limit. "
            f"Use presign_upload instead."
        )

    name = posixpath.basename(args["filename"].replace("\\", "/")).strip()
    if not name or name.startswith("."):
        raise ToolError(f"{args['filename']!r} is not a usable filename.")

    getattr(owner, field).save(name, ContentFile(blob), save=True)

    return {
        "stored": True,
        "target": args["target"],
        "bytes": len(blob),
        "url": getattr(owner, field).url,
        "storage": "s3" if settings.USE_S3_MEDIA else "local",
    }


@tool(
    name="presign_upload",
    title="Presign a direct upload",
    description="""
    A presigned POST for uploading a file straight to S3, for anything too large
    to pass base64. Only works when media is configured to live in S3. The form
    fields must be sent as multipart with the file last.
    """,
    schema={
        "properties": {
            "filename": {"type": "string"},
            "content_type": {"type": "string"},
            "prefix": {"type": "string",
                       "description": "Storage folder. Defaults to projects/assets/."},
        },
        "required": ["filename"],
    },
)
def presign_upload(args, ctx):
    from portfolio.storages import media_storage

    if not settings.USE_S3_MEDIA:
        raise ToolError(
            "Media is on local disk, so there is nothing to presign. Use "
            "upload_media instead."
        )

    name = posixpath.basename(args["filename"].replace("\\", "/")).strip()
    if not name or name.startswith("."):
        raise ToolError(f"{args['filename']!r} is not a usable filename.")

    prefix = (args.get("prefix") or "projects/assets/").strip("/")
    storage = media_storage()
    key = f"{prefix}/{name}"
    post = storage.signed_upload(key, args.get("content_type"))

    return {
        "upload": post,
        "storage_name": key,
        "expires_in": storage.ttl,
        "note": "After uploading, the file is not attached to any row. Attaching "
                "an existing key is not supported; use upload_media for files "
                "that need to become an asset.",
    }


def _target(name):
    if name not in UPLOAD_TARGETS:
        raise ToolError(f"Unknown target {name!r}. One of: {sorted(UPLOAD_TARGETS)}")
    return UPLOAD_TARGETS[name]


def _owner(kind, args):
    if kind == "profile":
        return common.get_profile()

    if not args.get("project"):
        raise ToolError("This target needs a project slug.")
    project = common.get_project(args["project"])

    if kind == "project":
        return project
    if not args.get("ref"):
        raise ToolError("An asset target needs the asset's ref.")
    return common.get_asset(project, args["ref"])
