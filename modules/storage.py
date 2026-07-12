"""
Supabase Storage helper for bank statement PDFs, receipt/invoice documents,
and generated voucher PDFs — replaces the local documents/ and vouchers/
folders from the original local-only prototype, since a cloud app server's
disk isn't persistent across restarts/redeploys.

All files live in one bucket (BUCKET), namespaced by kind/path, e.g.:
  statements/2026-01/statement.pdf
  documents/2026-01/txn42_receipt.jpg
  vouchers/2026/PV-2026-001.pdf
"""
from modules.config import get_secret

BUCKET = "lily-dahlia-files"

_client = None


def _get_client():
    global _client
    if _client is None:
        from supabase import create_client

        url = get_secret("SUPABASE_URL")
        key = get_secret("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SERVICE_KEY are not set. Add them to "
                ".streamlit/secrets.toml (local dev) or the app's Secrets settings "
                "(Streamlit Community Cloud) — see Getting_Started_Guide.md."
            )
        _client = create_client(url, key)
    return _client


def upload_bytes(path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Uploads (or overwrites) a file at `path` in the bucket. Returns the path."""
    client = _get_client()
    client.storage.from_(BUCKET).upload(
        path, data, {"content-type": content_type, "upsert": "true"}
    )
    return path


def download_bytes(path: str) -> bytes:
    client = _get_client()
    return client.storage.from_(BUCKET).download(path)
