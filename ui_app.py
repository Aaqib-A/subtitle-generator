"""
AI Subtitle Generator — local Streamlit UI
Wraps a Whisper (transcription) + Google Translate (translation) + srt (export)
pipeline with a settings panel, progress feedback, preview, and downloads.

Run locally with:
    streamlit run app.py
"""

import os
import tempfile
import shutil
from datetime import timedelta

import streamlit as st
import srt
from moviepy import VideoFileClip
import whisper
from deep_translator import GoogleTranslator

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# ----------------------------------------------------------------------------
# Language options
# Whisper and Google Translate mostly share 2-letter codes; a few differ
# (e.g. Chinese), so we keep one display list and a small override map.
# ----------------------------------------------------------------------------
LANGUAGES = {
    "English": "en", "Spanish": "es", "French": "fr", "German": "de",
    "Italian": "it", "Portuguese": "pt", "Russian": "ru", "Chinese": "zh",
    "Japanese": "ja", "Korean": "ko", "Arabic": "ar", "Hindi": "hi",
    "Dutch": "nl", "Turkish": "tr", "Polish": "pl", "Swedish": "sv",
    "Finnish": "fi", "Danish": "da", "Norwegian": "no", "Czech": "cs",
    "Greek": "el", "Hebrew": "he", "Hungarian": "hu", "Indonesian": "id",
    "Malay": "ms", "Romanian": "ro", "Ukrainian": "uk", "Vietnamese": "vi",
    "Thai": "th",
}

# Codes deep-translator (Google Translate) expects, where they differ from
# the Whisper code above.
TRANSLATE_CODE_OVERRIDES = {
    "zh": "zh-CN",
    "he": "iw",
}

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]


def to_translate_code(whisper_code: str) -> str:
    return TRANSLATE_CODE_OVERRIDES.get(whisper_code, whisper_code)


def get_device() -> str:
    if HAS_TORCH and torch.cuda.is_available():
        return "cuda"
    return "cpu"


# ----------------------------------------------------------------------------
# Pipeline steps (cached / reused across reruns where possible)
# ----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def load_whisper_model(model_size: str):
    return whisper.load_model(model_size)


def extract_audio(video_path: str, audio_path: str) -> None:
    clip = VideoFileClip(video_path)
    try:
        clip.audio.write_audiofile(audio_path, logger=None)
    finally:
        clip.close()


def transcribe(model, audio_path: str, language_code: str | None):
    fp16 = get_device() == "cuda"
    result = model.transcribe(audio_path, language=language_code, fp16=fp16)
    return result["segments"], result.get("language")


def translate_segments(segments, target_code: str, progress_cb=None):
    translator = GoogleTranslator(source="auto", target=to_translate_code(target_code))
    texts = []
    total = len(segments)
    for i, seg in enumerate(segments):
        try:
            texts.append(translator.translate(seg["text"].strip()))
        except Exception:
            # Fall back to the original text if the translation call fails
            # (most commonly because there's no internet connection).
            texts.append(seg["text"].strip())
        if progress_cb:
            progress_cb((i + 1) / total)
    return texts


def build_srt(segments, texts) -> str:
    subs = []
    for i, (seg, text) in enumerate(zip(segments, texts)):
        subs.append(
            srt.Subtitle(
                index=i + 1,
                start=timedelta(seconds=seg["start"]),
                end=timedelta(seconds=seg["end"]),
                content=text.strip(),
            )
        )
    return srt.compose(subs)


def srt_to_vtt(srt_content: str) -> str:
    body = srt_content.replace(",", ".")
    return "WEBVTT\n\n" + body


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
st.set_page_config(page_title="AI Subtitle Generator", page_icon="🎬", layout="wide")

st.markdown(
    """
    <style>
    .stButton>button[kind="primary"] { background-color: #2E5EAA; border-color: #2E5EAA; }
    .stButton>button[kind="primary"]:hover { background-color: #244a87; border-color: #244a87; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎬 AI Subtitle Generator")
st.caption("Transcribe and translate any video into subtitles, entirely on your machine.")

if "result_srt" not in st.session_state:
    st.session_state.result_srt = None
    st.session_state.result_name = None
    st.session_state.detected_lang = None

with st.sidebar:
    st.header("⚙️ Settings")

    uploaded_file = st.file_uploader(
        "Video file", type=["mp4", "mov", "mkv", "avi", "webm", "m4v"]
    )

    st.subheader("Transcription")
    model_size = st.selectbox(
        "Whisper model size", WHISPER_MODELS, index=2,
        help="Bigger models are more accurate but slower. 'small' is a good default.",
    )
    source_lang_name = st.selectbox(
        "Source language", ["Auto-detect"] + list(LANGUAGES.keys()),
        help="Leave on Auto-detect unless Whisper is guessing wrong.",
    )

    st.subheader("Translation")
    do_translate = st.checkbox("Translate subtitles", value=True)
    target_lang_name = st.selectbox(
        "Translate to", list(LANGUAGES.keys()),
        index=list(LANGUAGES.keys()).index("English"),
        disabled=not do_translate,
    )
    if do_translate:
        st.caption("Translation calls Google Translate and needs an internet connection.")

    st.subheader("Output")
    default_output_name = (
        os.path.splitext(uploaded_file.name)[0] if uploaded_file is not None else "subtitles"
    )
    output_base = st.text_input(
        "Output filename (no extension)",
        value=default_output_name,
        # Keying on the file name gives each newly-uploaded video its own
        # default (the video's name) while still letting you edit it freely.
        key=f"output_base_{uploaded_file.name if uploaded_file is not None else 'none'}",
    )
    also_vtt = st.checkbox("Also export .vtt", value=False)

    st.divider()
    st.caption(f"Compute device: **{get_device()}**")

    run = st.button(
        "🚀 Generate subtitles", type="primary", use_container_width=True,
        disabled=uploaded_file is None,
    )

col_preview, col_run = st.columns([1, 1], gap="large")

with col_preview:
    st.subheader("Preview")
    if uploaded_file is not None:
        st.video(uploaded_file)
    else:
        st.info("Upload a video from the sidebar to get started.")

with col_run:
    st.subheader("Progress")
    status_box = st.container()
    result_box = st.container()

    if run and uploaded_file is not None:
        st.session_state.result_srt = None
        work_dir = tempfile.mkdtemp(prefix="subtitle_app_")
        try:
            video_path = os.path.join(work_dir, uploaded_file.name)
            with open(video_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            audio_path = os.path.join(work_dir, "audio.wav")

            with status_box:
                with st.status("Running pipeline...", expanded=True) as status:
                    st.write("Extracting audio from video...")
                    extract_audio(video_path, audio_path)

                    st.write(f"Loading Whisper model ({model_size})...")
                    model = load_whisper_model(model_size)

                    st.write("Transcribing audio...")
                    lang_code = None if source_lang_name == "Auto-detect" else LANGUAGES[source_lang_name]
                    segments, detected_lang = transcribe(model, audio_path, lang_code)
                    st.session_state.detected_lang = detected_lang

                    if do_translate:
                        st.write(f"Translating {len(segments)} segments to {target_lang_name}...")
                        progress = st.progress(0.0)
                        texts = translate_segments(
                            segments, LANGUAGES[target_lang_name],
                            progress_cb=lambda frac: progress.progress(frac),
                        )
                    else:
                        st.write("Skipping translation — keeping transcribed text as-is.")
                        texts = [seg["text"].strip() for seg in segments]

                    st.write("Building .srt file...")
                    srt_content = build_srt(segments, texts)

                    status.update(label="Done!", state="complete", expanded=False)

            st.session_state.result_srt = srt_content
            st.session_state.result_name = output_base.strip() or "subtitles"

        except Exception as e:
            with status_box:
                st.error(f"Something went wrong: {e}")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    if st.session_state.result_srt:
        with result_box:
            if st.session_state.detected_lang:
                st.caption(f"Whisper detected source language: **{st.session_state.detected_lang}**")

            st.text_area("Subtitle preview", st.session_state.result_srt, height=250)

            dl1, dl2 = st.columns(2)
            with dl1:
                st.download_button(
                    "⬇️ Download .srt",
                    data=st.session_state.result_srt,
                    file_name=f"{st.session_state.result_name}.srt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with dl2:
                if also_vtt:
                    st.download_button(
                        "⬇️ Download .vtt",
                        data=srt_to_vtt(st.session_state.result_srt),
                        file_name=f"{st.session_state.result_name}.vtt",
                        mime="text/vtt",
                        use_container_width=True,
                    )