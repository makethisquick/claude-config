"""Image and text assets.

Assets are the shared prerequisite for Display, Performance Max, and Demand Gen:
those campaign types reference `Asset` resources rather than carrying creative
inline. Images must be uploaded as raw bytes — you cannot point a campaign at an
image URL — so this reads from a local path or fetches a URL and pushes the bytes.

Google Drive: ADC here holds only the adwords and cloud-platform scopes, so this
module cannot read Drive directly. Pull the file with the Drive MCP first, save
it locally, then pass that path.

Videos are different again: they are referenced by YouTube video ID and are never
uploaded through this API.
"""

import os
import urllib.request
from typing import Any

from ..client import get_client, normalize_customer_id
from ..safety import apply

# Google rejects images over 5MB.
_MAX_BYTES = 5 * 1024 * 1024

_MAGIC = {
    b"\x89PNG\r\n\x1a\n": "PNG",
    b"\xff\xd8\xff": "JPEG",
    b"GIF87a": "GIF",
    b"GIF89a": "GIF",
}


def _detect_format(data: bytes) -> str | None:
    for magic, name in _MAGIC.items():
        if data.startswith(magic):
            return name
    return None


def _read_source(source: str) -> tuple[bytes | None, str | None]:
    """Returns (data, error). Accepts a local path or an http(s) URL."""
    if source.startswith(("http://", "https://")):
        try:
            request = urllib.request.Request(
                source, headers={"User-Agent": "gads-write/0.1"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read(_MAX_BYTES + 1), None
        except Exception as exc:  # noqa: BLE001 - surface any fetch failure verbatim
            return None, f"could not fetch {source}: {exc}"

    path = os.path.expanduser(source)
    if not os.path.isfile(path):
        return None, f"no such file: {path}"
    with open(path, "rb") as handle:
        return handle.read(_MAX_BYTES + 1), None


def upload_image_asset(
    customer_id: str,
    source: str,
    name: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Uploads an image as a reusable Asset.

    source: a local file path, or an http(s) URL to fetch.
    name:   asset name shown in the Google Ads UI. Must be unique in the account.

    Returns the asset resource name on confirm=true — that is what Display and
    Performance Max campaigns reference.
    """
    data, error = _read_source(source)
    if error:
        return {"status": "rejected", "applied": False, "errors": [error]}

    problems = []
    if len(data) > _MAX_BYTES:
        problems.append(
            f"image is over the 5MB limit ({len(data) / 1024 / 1024:.1f}MB)"
        )
    image_format = _detect_format(data)
    if image_format is None:
        problems.append("not a PNG, JPEG, or GIF — Google Ads rejects other formats")
    if problems:
        return {"status": "rejected", "applied": False, "errors": problems}

    client = get_client()
    cid = normalize_customer_id(customer_id)

    op = client.get_type("MutateOperation")
    asset = op.asset_operation.create
    asset.name = name
    asset.type_ = client.enums.AssetTypeEnum.IMAGE
    asset.image_asset.data = data

    return apply(
        cid,
        [op],
        confirm,
        {
            "action": "upload_image_asset",
            "name": name,
            "source": source,
            "format": image_format,
            "size": f"{len(data) / 1024:.0f} KB",
        },
    )


def create_text_asset(
    customer_id: str,
    text: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Creates a reusable text asset, for Performance Max asset groups."""
    client = get_client()
    cid = normalize_customer_id(customer_id)

    op = client.get_type("MutateOperation")
    asset = op.asset_operation.create
    asset.type_ = client.enums.AssetTypeEnum.TEXT
    asset.text_asset.text = text

    return apply(
        cid,
        [op],
        confirm,
        {"action": "create_text_asset", "text": text},
    )


def list_assets(
    customer_id: str,
    asset_type: str = "IMAGE",
    limit: int = 100,
) -> dict[str, Any]:
    """Lists existing assets in the account, so creative can be reused."""
    from .lookup import query

    gaql = f"""
        SELECT asset.id, asset.name, asset.type, asset.resource_name,
               asset.image_asset.full_size.width_pixels,
               asset.image_asset.full_size.height_pixels
        FROM asset
        WHERE asset.type = '{asset_type}'
        LIMIT {limit}
    """
    return query(customer_id, gaql, limit=limit)
