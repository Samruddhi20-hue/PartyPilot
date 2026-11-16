import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ALLOWED_TYPES = {
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    "image/webp": (".webp",),
}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _image_extension(data, content_type, filename):
    content_type = (content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_TYPES:
        raise ValueError("Only JPG, PNG and WEBP images are accepted.")
    if not any((filename or "").lower().endswith(ext) for ext in ALLOWED_TYPES[content_type]):
        raise ValueError("The image extension does not match its content type.")
    signatures = {
        "image/jpeg": data.startswith(b"\xff\xd8\xff"),
        "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
    }
    if not signatures[content_type]:
        raise ValueError("The uploaded file is not a valid image.")
    return ALLOWED_TYPES[content_type][0]


def upload_venue_image(file_storage, restaurant_id, venue_id):
    base_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "venue-images")
    if not base_url or not service_key:
        raise RuntimeError("Supabase Storage is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY on the server.")

    data = file_storage.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise ValueError("Please choose an image to upload.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Each image must be 8 MB or smaller.")

    extension = _image_extension(data, file_storage.mimetype, file_storage.filename)
    object_path = f"restaurants/{restaurant_id}/venues/{venue_id}/{uuid.uuid4().hex}{extension}"
    encoded_path = quote(object_path, safe="/")
    endpoint = f"{base_url}/storage/v1/object/{quote(bucket, safe='')}/{encoded_path}"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": file_storage.mimetype,
        "x-upsert": "false",
    }
    req = Request(endpoint, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=30) as response:
            if response.status not in (200, 201):
                raise RuntimeError("Supabase Storage rejected the image upload.")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("Image upload failed. Check Supabase Storage configuration.") from exc

    public_url = f"{base_url}/storage/v1/object/public/{quote(bucket, safe='')}/{encoded_path}"
    return object_path, public_url


def delete_venue_image(object_path):
    base_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "venue-images")
    if not base_url or not service_key:
        raise RuntimeError("Supabase Storage is not configured.")
    encoded_path = quote(object_path, safe="/")
    endpoint = f"{base_url}/storage/v1/object/{quote(bucket, safe='')}/{encoded_path}"
    req = Request(endpoint, headers={
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }, method="DELETE")
    try:
        with urlopen(req, timeout=30) as response:
            if response.status not in (200, 204):
                raise RuntimeError("Supabase Storage could not delete the image.")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("Image deletion failed. Check Supabase Storage configuration.") from exc
