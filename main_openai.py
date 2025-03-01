import os
import re
import openai
import markdown
import pdfkit
import whisper
import asyncio
import shutil
import uuid
from dotenv import load_dotenv
from moviepy.editor import VideoFileClip
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Dict

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"

if not OPENAI_API_KEY:
    raise ValueError("❌ ERROR: OpenAI API key is missing! Please add it to the .env file.")

app = FastAPI()

# ✅ Fix CORS issue for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Allow frontend requests
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai.api_key = OPENAI_API_KEY

# Directories
UPLOAD_DIR = "downloads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Dictionary to track WebSocket connections
active_connections: Dict[str, WebSocket] = {}

def sanitize_filename(filename):
    """Removes or replaces problematic characters from filenames."""
    safe_filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    safe_filename = safe_filename.replace(' ', '_')
    return safe_filename[:50]  # Limit length to avoid path issues

class VideoProcessor:
    """Handles video processing tasks with real-time updates via WebSockets."""

    def __init__(self, video_file: UploadFile, websocket: WebSocket, task_id: str):
        self.video_file = video_file
        self.websocket = websocket
        self.task_id = task_id
        sanitized_filename = sanitize_filename(video_file.filename)
        self.video_path = os.path.join(UPLOAD_DIR, sanitized_filename)
        self.audio_path = self.video_path.replace(".mp4", ".mp3")
        self.pdf_path = os.path.join(UPLOAD_DIR, f"{task_id}.pdf")

    async def send_status(self, message: str, progress: int = None):
        """ Sends real-time status updates to the WebSocket client. """
        try:
            if self.task_id in active_connections:
                status_message = {"status": message}
                if progress is not None:
                    status_message["progress"] = progress
                await active_connections[self.task_id].send_json(status_message)
        except (WebSocketDisconnect, RuntimeError):
            print(f"❌ WebSocket disconnected for Task ID: {self.task_id}")
            active_connections.pop(self.task_id, None)

    async def save_uploaded_video(self):
        """ Saves the uploaded video file. """
        await self.send_status("Uploading video...", progress=10)
        try:
            with open(self.video_path, "wb") as buffer:
                buffer.write(await self.video_file.read())
            await self.send_status("✅ Video uploaded successfully.", progress=20)
        except Exception as e:
            await self.send_status(f"❌ Failed to save video: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save video: {str(e)}")

    async def extract_audio(self):
        """ Extracts audio from the uploaded video. """
        await self.send_status("Extracting audio from video...", progress=30)
        try:
            clip = VideoFileClip(self.video_path)
            clip.audio.write_audiofile(self.audio_path, codec="mp3")
            clip.close()
            await self.send_status("✅ Audio extraction complete.", progress=50)
        except Exception as e:
            await self.send_status(f"❌ Audio extraction failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Audio extraction failed: {str(e)}")

    async def transcribe_audio(self) -> str:
        """ Uses Whisper to transcribe audio. """
        await self.send_status("🔄 Transcribing audio with Whisper...", progress=55)
        try:
            model = whisper.load_model("base")
            result = model.transcribe(self.audio_path)
            await self.send_status("✅ Audio transcription complete.", progress=70)
            return result["text"]
        except Exception as e:
            await self.send_status(f"❌ Transcription failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    async def summarize_text(self, text: str) -> str:
        """ Uses GPT-4o to summarize the transcribed text into Markdown format. """
        await self.send_status("📄 Summarizing transcript using GPT-4o...", progress=80)
        try:
            client = openai.OpenAI()
            prompt = (
                "You are a professional summarizer. Your task is to summarize the following transcript "
                "from a talk, lecture, or presentation. Provide a structured, concise summary using Markdown "
                "formatting with headings (##), bullet points (-), and bold key terms (**important**). "
                "Avoid fluff and focus on the main ideas, arguments, and conclusions. Here is the transcript:\n\n"
                f"{text}\n\n"
                "Now, generate a high-quality Markdown-formatted summary."
            )

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "You are an AI assistant that specializes in summarization."},
                          {"role": "user", "content": prompt}],
                max_tokens=2000
            )

            await self.send_status("✅ Summary generated.", progress=90)
            return response.choices[0].message.content
        except Exception as e:
            await self.send_status(f"❌ Summarization failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

    async def save_summary_as_pdf(self, summary_md: str):
        """ Converts the Markdown summary into a styled PDF """
        await self.send_status("Generating PDF...", progress=95)
        try:
            html_content = markdown.markdown(summary_md)
            styled_html = f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; font-size: 12pt; color: #333; padding: 40px; }}
                    h1, h2, h3 {{ color: #0078D7; font-weight: bold; }}
                    ul {{ padding-left: 20px; }}
                    strong {{ color: #D9534F; font-weight: bold; }}
                    .container {{ background: white; padding: 25px; border-radius: 10px; }}
                    .title-bar {{ background: #0078D7; padding: 15px; text-align: center; color: white; font-size: 18pt; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="title-bar">📄 Summary Report</div>
                    {html_content}
                </div>
            </body>
            </html>
            """

            config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
            pdfkit.from_string(styled_html, self.pdf_path, configuration=config)
            await self.send_status("✅ PDF generation complete.", progress=100)
        except Exception as e:
            await self.send_status(f"❌ PDF generation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

@app.get("/download/{task_id}")
async def download_pdf(task_id: str):
    """ Serves the generated PDF file for the given task ID """
    pdf_path = os.path.join(UPLOAD_DIR, f"{task_id}.pdf")

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found.")

    return FileResponse(pdf_path, filename=f"summary_{task_id}.pdf", media_type="application/pdf")
