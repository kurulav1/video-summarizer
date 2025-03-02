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

# ✅ Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WKHTMLTOPDF_PATH = r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"

if not OPENAI_API_KEY:
    raise ValueError("❌ ERROR: OpenAI API key is missing! Please add it to the .env file.")

# ✅ Initialize FastAPI
app = FastAPI()

# ✅ Enable CORS (including WebSockets!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Change this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai.api_key = OPENAI_API_KEY

# ✅ Storage directories
UPLOAD_DIR = "downloads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ✅ Track active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

def sanitize_filename(filename):
    """Removes invalid characters from filenames."""
    return re.sub(r'[<>:"/\\|?*]', '', filename)[:50]  # Limit length for safety

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
        """ Uses Whisper to transcribe audio with real-time progress updates. """
        await self.send_status("🔄 Transcribing audio with Whisper...", progress=55)
        
        print(f"🟡 DEBUG: Starting transcription for {self.audio_path}")

        try:
            model = whisper.load_model("base")

            print("🟢 DEBUG: Whisper model loaded successfully.")

            result = model.transcribe(self.audio_path, word_timestamps=True)

            print("🟢 DEBUG: Transcription completed.")

            total_segments = len(result["segments"])
            for i, segment in enumerate(result["segments"]):
                progress = 55 + int((i / total_segments) * 15)
                await self.send_status(f"📝 Transcribing: {segment['text'][:50]}...", progress=progress)

            await self.send_status("✅ Audio transcription complete.", progress=70)

            print(f"🟢 DEBUG: Transcription Result: {result['text'][:100]}...")

            return result["text"]
        
        except Exception as e:
            print(f"❌ DEBUG: Transcription failed with error: {str(e)}")
            await self.send_status(f"❌ Transcription failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    async def summarize_text(self, text: str) -> str:
        """ Uses GPT-4o to summarize the transcribed text. """
        await self.send_status("📄 Generating summary...", progress=80)
        try:
            client = openai.OpenAI()
            prompt = (
                "You are a professional summarizer. Provide a structured, concise summary using Markdown "
                "with headings (##), bullet points (-), and bold key terms (**important**). "
                f"Here is the transcript:\n\n{text}\n\nGenerate a Markdown summary."
            )

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "You are an AI assistant that specializes in summarization."},
                          {"role": "user", "content": prompt}],
                max_tokens=2000
            )

            summary = response.choices[0].message.content
            await self.send_status("✅ Summary generated.", progress=90)
            return summary
        except Exception as e:
            await self.send_status(f"❌ Summarization failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

    async def save_summary_as_pdf(self, summary_md: str):
        """ Converts the summary to a PDF. """
        await self.send_status("📄 Generating PDF...", progress=95)
        try:
            html_content = markdown.markdown(summary_md)
            styled_html = f"""
            <html><head><meta charset='UTF-8'></head>
            <body style="font-family:Arial; padding:20px; max-width:800px;">
            <h1 style="color:#0078D7;">Summary Report</h1>
            {html_content}
            </body></html>
            """
            config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
            pdfkit.from_string(styled_html, self.pdf_path, configuration=config)
            await self.send_status("✅ PDF generation complete.", progress=100)
        except Exception as e:
            await self.send_status(f"❌ PDF generation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

@app.post("/process_video/")
async def process_video(background_tasks: BackgroundTasks, file: UploadFile = File(...), task_id: str = Form(...)):
    """ API Endpoint to process video files """
    
    for _ in range(6):  
        if task_id in active_connections:
            break
        await asyncio.sleep(0.5)

    if task_id not in active_connections:
        raise HTTPException(status_code=400, detail="No active WebSocket connection for this task.")

    processor = VideoProcessor(file, active_connections[task_id], task_id)

    try:
        await processor.save_uploaded_video()
        await processor.extract_audio()
        transcript = await processor.transcribe_audio()
        summary_md = await processor.summarize_text(transcript)
        background_tasks.add_task(processor.save_summary_as_pdf, summary_md)

        return {"summary": summary_md, "pdf": f"/download/{task_id}"}
    
    except HTTPException as e:
        return {"error": e.detail}

@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """ WebSocket connection for real-time status updates. """
    await websocket.accept()
    active_connections[task_id] = websocket

    try:
        while True:
            await asyncio.sleep(2)
            await websocket.send_json({"status": "WebSocket Connection Active"})
    except WebSocketDisconnect:
        print(f"❌ WebSocket disconnected for Task ID: {task_id}")
        active_connections.pop(task_id, None)

@app.get("/download/{task_id}")
async def download_pdf(task_id: str):
    """ Serves the generated PDF file """
    pdf_path = os.path.join(UPLOAD_DIR, f"{task_id}.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found.")
    return FileResponse(pdf_path, filename=f"summary_{task_id}.pdf", media_type="application/pdf")
