"""
Thin HTTP client for the subtitle-generation backend.

The frontend does NOT run Whisper/moviepy/translation itself — it streams
the raw video to a backend service over HTTP and polls for the result.

Everything below the "API CONTRACT" line is a placeholder guess at a
reasonable REST design. It is isolated here on purpose: once you share your
actual backend's routes/payloads, only this file needs to change — app.py
just calls these four functions and doesn't care how they're implemented.
See BACKEND_API_CONTRACT.md for the full expected request/response shapes.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor


class BackendError(Exception):
    pass


# ---------------------------------------------------------------------------
# API CONTRACT (placeholder — align with your real backend)
# ---------------------------------------------------------------------------

def check_health(base_url: str, timeout: float = 5.0) -> bool:
    """GET /health -> 200 OK means the backend is reachable."""
    try:
        r = requests.get(f"{base_url.rstrip('/')}/health", timeout=timeout)
        return r.ok
    except requests.RequestException:
        return False


def submit_job(
    base_url: str,
    file_path: str,
    filename: str,
    settings: dict,
    on_upload_progress: Optional[Callable[[float], None]] = None,
) -> str:
    """
    POST /jobs  (multipart/form-data: file + settings fields)
    -> {"job_id": "..."}

    Streams the file from disk instead of loading it into memory, so upload
    size is bounded by disk, not RAM, on the frontend side.
    """
    file_handle = open(file_path, "rb")
    fields = {
        "file": (filename, file_handle, "application/octet-stream"),
        **{k: str(v) for k, v in settings.items()},
    }
    encoder = MultipartEncoder(fields=fields)

    def _cb(monitor):
        if on_upload_progress and encoder.len:
            on_upload_progress(min(monitor.bytes_read / encoder.len, 1.0))

    body = MultipartEncoderMonitor(encoder, _cb) if on_upload_progress else encoder

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/jobs",
            data=body,
            headers={"Content-Type": encoder.content_type},
            timeout=(10, None),  # 10s to connect, no cap on upload duration
        )
    except requests.RequestException as e:
        raise BackendError(f"Could not reach backend at {base_url}: {e}")
    finally:
        file_handle.close()

    if not resp.ok:
        raise BackendError(f"Backend rejected the job ({resp.status_code}): {resp.text}")
    job_id = resp.json().get("job_id")
    if not job_id:
        raise BackendError(f"Backend response missing 'job_id': {resp.text}")
    return job_id


def get_job_status(base_url: str, job_id: str, timeout: float = 10.0) -> dict:
    """GET /jobs/{job_id} -> {"status": "queued|processing|done|error", ...}"""
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/jobs/{job_id}", timeout=timeout)
    except requests.RequestException as e:
        raise BackendError(f"Could not reach backend at {base_url}: {e}")
    if not resp.ok:
        raise BackendError(f"Could not fetch job status ({resp.status_code}): {resp.text}")
    return resp.json()


def wait_for_result(
    base_url: str,
    job_id: str,
    on_status: Optional[Callable[[dict], None]] = None,
    poll_interval: float = 2.0,
    max_consecutive_errors: int = 5,
) -> dict:
    """Blocks, polling until the job reaches status 'done' or 'error'."""
    consecutive_errors = 0
    while True:
        try:
            status = get_job_status(base_url, job_id)
            consecutive_errors = 0
        except BackendError:
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                raise
            time.sleep(poll_interval)
            continue

        if on_status:
            on_status(status)
        if status.get("status") in ("done", "error"):
            return status
        time.sleep(poll_interval)
