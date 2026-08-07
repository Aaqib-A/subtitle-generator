
from moviepy import VideoFileClip
import whisper
import srt
from deep_translator import GoogleTranslator
from datetime import timedelta

# Step 1: Extract audio from video
def extract_audio(video_path, audio_path="audio.wav"):
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(audio_path)
    return audio_path

# Step 2: Transcribe using Whisper
def transcribe(audio_path):
    model = whisper.load_model("small")
    result = model.transcribe(audio_path)
    return result['segments']

# Step 3: Translate text to English
def translate_text(text):
    return GoogleTranslator(source='auto', target='en').translate(text)

# Step 4: Convert to .srt format
def generate_srt(segments, output_srt_path="subtitles.srt"):
    subtitles = []
    for i, seg in enumerate(segments):
        translated_text = translate_text(seg['text'])
        start = timedelta(seconds=int(seg['start']))
        end = timedelta(seconds=int(seg['end']))
        subtitles.append(srt.Subtitle(index=i+1, start=start, end=end, content=translated_text))
    
    with open(output_srt_path, "w", encoding="utf-8") as f:
        f.write(srt.compose(subtitles))

# Main workflow
def process_video(video_path):
    audio_path = extract_audio(video_path)
    segments = transcribe(audio_path)
    generate_srt(segments)


# Run
process_video("o.mp4")
