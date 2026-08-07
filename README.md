# AI Subtitle Generator (local UI)

A Streamlit UI around a Whisper (transcription) → Google Translate (translation) → `.srt`
pipeline. Everything runs on your machine except the translation step, which calls Google
Translate and needs an internet connection (turn it off in the sidebar to stay fully offline).

## 1. Prerequisites

- Python 3.9–3.12
- **ffmpeg** installed and on your PATH (used by both `moviepy` and Whisper)
  - macOS: `brew install ffmpeg`
  - Windows: `winget install ffmpeg` (or download from ffmpeg.org and add to PATH)
  - Linux: `sudo apt install ffmpeg`

## 2. Install

```bash
python3 -m venv srt-venv
source srt-venv/bin/activate        # Windows: srt-venv\Scripts\activate
pip install -r requirements.txt
```


> If you have an NVIDIA GPU and want faster transcription, install the CUDA build of
> `torch` first (see https://pytorch.org/get-started/locally/) before installing the
> rest of the requirements — otherwise the CPU build is used automatically.

## 3. Run

```bash
streamlit run ui_app.py
```

This opens the app in your browser at `http://localhost:8501`. Nothing is uploaded
anywhere except the translation API calls described above.

## What you can configure in the UI

- **Video file** — mp4, mov, mkv, avi, webm, m4v
- **Whisper model size** — tiny/base/small/medium/large (bigger = more accurate, slower)
- **Source language** — auto-detect, or force a specific language if Whisper guesses wrong
- **Translate subtitles** — on/off, plus a target language
- **Output filename**, and an optional `.vtt` export alongside the `.srt`

The first run for a given model size will download that Whisper model (a few hundred MB
to ~3 GB depending on size); it's cached by Whisper afterwards.
