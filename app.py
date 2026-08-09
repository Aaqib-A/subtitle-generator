"""
AI Subtitle Generator — frontend only.

All transcription/translation happens on a separate backend service (see
BACKEND_API_CONTRACT.md). This app just collects settings, streams the video
to the backend, polls for the result, and lets you preview/download it.

Run locally with:
    streamlit run app.py
"""

import os
import tempfile
import shutil

import streamlit as st

import api_client


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
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]
DEFAULT_BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


def srt_to_vtt(srt_content: str) -> str:
    return "WEBVTT\n\n" + srt_content.replace(",", ".")


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
st.caption("Transcribe and translate any video into subtitles — processed on your backend service.")

for key, default in {
    "result_srt": None, "result_name": None, "detected_lang": None,
}.items():
    st.session_state.setdefault(key, default)

with st.sidebar:
    st.header("🔌 Backend")
    backend_url = st.text_input(
        "Backend URL", value=DEFAULT_BACKEND_URL,
        help="e.g. http://localhost:8000 for local testing, or your server's address in production.",
    )
    if st.button("Test connection"):
        if api_client.check_health(backend_url):
            st.success("Backend is reachable.")
        else:
            st.error("Could not reach the backend at that URL.")

    st.divider()
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
        help="Leave on Auto-detect unless the transcriber guesses wrong.",
    )

    st.subheader("Translation")
    do_translate = st.checkbox("Translate subtitles", value=True)
    target_lang_name = st.selectbox(
        "Translate to", list(LANGUAGES.keys()),
        index=list(LANGUAGES.keys()).index("English"),
        disabled=not do_translate,
    )

    st.subheader("Output")
    default_output_name = (
        os.path.splitext(uploaded_file.name)[0] if uploaded_file is not None else "subtitles"
    )
    output_base = st.text_input(
        "Output filename (no extension)",
        value=default_output_name,
        key=f"output_base_{uploaded_file.name if uploaded_file is not None else 'none'}",
    )
    also_vtt = st.checkbox("Also export .vtt", value=False)

    run = st.button(
        "🚀 Generate subtitles", type="primary", use_container_width=True,
        disabled=uploaded_file is None or not backend_url,
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
            # Write once to disk so we can stream it to the backend without
            # holding the whole file in memory a second time.
            video_path = os.path.join(work_dir, uploaded_file.name)
            with open(video_path, "wb") as f:
                shutil.copyfileobj(uploaded_file, f)

            settings = {
                "model_size": model_size,
                "source_language": "auto" if source_lang_name == "Auto-detect" else LANGUAGES[source_lang_name],
                "translate": do_translate,
                "target_language": LANGUAGES[target_lang_name],
            }

            with status_box:
                upload_label = st.empty()
                upload_bar = st.progress(0.0)
                status_label = st.empty()

                upload_label.write("Uploading video to backend...")
                job_id = api_client.submit_job(
                    backend_url, video_path, uploaded_file.name, settings,
                    on_upload_progress=lambda frac: upload_bar.progress(frac),
                )
                upload_label.write("Upload complete. Waiting on backend...")

                def _on_status(status):
                    state = status.get("status", "processing")
                    progress = status.get("progress")
                    if progress is not None:
                        status_label.write(f"Backend status: **{state}** ({progress * 100:.0f}%)")
                    else:
                        status_label.write(f"Backend status: **{state}**")

                final = api_client.wait_for_result(backend_url, job_id, on_status=_on_status)

            if final.get("status") == "error":
                with status_box:
                    st.error(f"Backend reported an error: {final.get('error', 'unknown error')}")
            else:
                st.session_state.result_srt = final.get("srt", "")
                st.session_state.result_name = output_base.strip() or "subtitles"
                st.session_state.detected_lang = final.get("detected_language")

        except api_client.BackendError as e:
            with status_box:
                st.error(str(e))
        except Exception as e:
            with status_box:
                st.error(f"Something went wrong: {e}")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    if st.session_state.result_srt:
        with result_box:
            if st.session_state.detected_lang:
                st.caption(f"Detected source language: **{st.session_state.detected_lang}**")

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
