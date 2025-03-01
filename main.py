import os
from pytube import YouTube
from moviepy.editor import VideoFileClip
import whisper
from transformers import pipeline, BartTokenizer

def download_video(url, output_path):
    yt = YouTube(url)
    stream = yt.streams.filter(only_video=False, file_extension="mp4").first()
    stream.download(output_path=output_path)
    return os.path.join(output_path, stream.default_filename)

def extract_audio(video_path, audio_path):
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(audio_path)
    clip.close()
    return audio_path

def transcribe_audio(audio_path):
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result["text"]

def split_text(text, tokenizer, max_tokens=1024):
    tokens = tokenizer.encode(text, truncation=False)
    
    # Ensure proper chunking
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk = tokens[i:i + max_tokens]
        chunks.append(tokenizer.decode(chunk, skip_special_tokens=True))
    
    return chunks

def summarize_text(text):
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    tokenizer = BartTokenizer.from_pretrained("facebook/bart-large-cnn")

    chunks = split_text(text, tokenizer, max_tokens=1024)
    summaries = []

    for chunk in chunks:
        try:
            summary = summarizer(chunk, max_length=300, min_length=50, do_sample=False)
            summaries.append(summary[0]["summary_text"])
        except Exception as e:
            print(f"Error summarizing chunk: {e}")
            summaries.append(chunk[:300])  # Fallback: Take first 300 characters
    
    final_summary = " ".join(summaries)
    return final_summary

def main():
    video_input = input("Enter video URL or local file path: ")
    output_path = "downloads"
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    if video_input.lower().startswith("http"):
        video_file = download_video(video_input, output_path)
    else:
        if not os.path.exists(video_input):
            print("Local file does not exist.")
            return
        video_file = video_input

    audio_file = os.path.join(output_path, "audio.mp3")
    extract_audio(video_file, audio_file)

    transcript = transcribe_audio(audio_file)
    with open(os.path.join(output_path, "transcript.txt"), "w") as f:
        f.write(transcript)

    summary = summarize_text(transcript)
    with open(os.path.join(output_path, "summary.txt"), "w") as f:
        f.write(summary)

    print("✅ Transcript and summary saved in", output_path)

if __name__ == "__main__":
    main()
