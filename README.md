# AI Subtitle Generator — frontend

A Streamlit UI that streams a video to a separate backend service for
transcription/translation, then polls for and displays the result. See
`BACKEND_API_CONTRACT.md` for exactly what this frontend expects your backend
to expose — that file is a placeholder pending your real backend's routes.

## Install

```bash
cd frontend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configure the backend URL

The sidebar has a **Backend URL** field. It defaults to the `BACKEND_URL`
environment variable, or `http://localhost:8000` if that's not set.

- **Local testing** (both on one machine): leave it as `http://localhost:8000`
  (or wherever your backend listens) and just run it.
- **Production** (separate machines): either export `BACKEND_URL` before
  launching, or type the backend's address straight into the sidebar field —
  no code change needed either way.

```bash
# local testing
streamlit run app.py

# pointing at a remote backend
BACKEND_URL=https://your-backend.example.com streamlit run app.py
```

Use the **Test connection** button in the sidebar to confirm the backend is
reachable before uploading a large file.

## Upload size

`.streamlit/config.toml` sets `server.maxUploadSize = 20000` (20GB), up from
Streamlit's 200MB default. The upload to your backend is streamed from disk
(via `requests-toolbelt`), so the frontend's memory use doesn't grow with file
size. See the "Known limitation" note at the bottom of `BACKEND_API_CONTRACT.md`
for the one remaining ceiling and how to remove it if you ever need to.

## What you can configure in the UI

- **Video file** — mp4, mov, mkv, avi, webm, m4v
- **Backend URL**
- **Whisper model size** — tiny/base/small/medium/large (sent to the backend)
- **Source language** — auto-detect, or force a specific language
- **Translate subtitles** — on/off, plus a target language
- **Output filename** (defaults to the video's own name), optional `.vtt` export
