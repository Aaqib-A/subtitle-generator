# Backend API contract (placeholder — confirm against your actual backend)

The frontend only knows about 4 calls, all in `api_client.py`. If your backend's
routes or payload shapes differ, this is the only file you need to edit — nothing
in `app.py` depends on these details directly.

## 1. Health check
```
GET /health
```
Any 2xx response is treated as "reachable". Used by the sidebar's "Test connection" button.

## 2. Submit a job
```
POST /jobs
Content-Type: multipart/form-data
```
Fields:
| field | type | notes |
|---|---|---|
| `file` | file | the raw video, unmodified |
| `model_size` | string | one of `tiny`, `base`, `small`, `medium`, `large` |
| `source_language` | string | an ISO 639-1 code (`en`, `es`, ...) or the literal string `auto` |
| `translate` | string | `"True"` / `"False"` |
| `target_language` | string | an ISO 639-1 code |

Response `200`:
```json
{ "job_id": "abc123" }
```

## 3. Poll job status
```
GET /jobs/{job_id}
```
Response `200`, one of:
```json
{ "status": "queued" }
{ "status": "processing", "progress": 0.42 }
{ "status": "done", "srt": "1\n00:00:00,000 --> ...", "detected_language": "en" }
{ "status": "error", "error": "human-readable message" }
```
- `progress` is optional; when present the UI shows a percentage.
- `detected_language` is optional; shown as a caption if present.

## What to tell me to reconcile this

- Actual route paths and HTTP methods
- Actual field/param names for the upload
- Whether results come back synchronously (single call, no polling) or via
  job id + polling like above (recommended for large files, since transcription
  of a long video can take minutes and a single HTTP request is likely to time out)
- Any auth (API key header, bearer token, etc.)

## Known limitation: Streamlit's own upload ceiling

`requests-toolbelt` gives us true streaming from disk to your backend, so the
*frontend's* memory use doesn't scale with file size. But the browser → Streamlit
server leg still goes through Streamlit's built-in uploader, which is capped by
`server.maxUploadSize` in `.streamlit/config.toml` (currently set to 20000 MB / ~20GB)
and is buffered by Streamlit itself, not truly streamed. For most video files this
is plenty; if you need to comfortably support files far beyond that, the fix is a
custom upload component that sends the browser's file straight to the backend
(e.g. via a presigned URL), bypassing the Streamlit server entirely — a bigger
change, worth doing only if you hit this ceiling in practice.
