import os
import uuid
import tempfile
import shutil
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.database import (
    init_db, get_setting, set_setting, save_history_item,
    get_history_items, get_history_item, delete_history_item,
    save_chat_message, get_chat_history
)
from app.services.youtube_service import extract_video_id, get_video_metadata, get_transcript
from app.services.ai_service import generate_video_highlights, answer_video_chat
from app.services.audio_service import convert_to_audio, transcribe_audio_file
from app.services.export_service import export_to_markdown, export_to_srt, export_to_vtt, export_to_txt

# Initialize database
init_db()

app = FastAPI(title="VideoScribe AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class YoutubeRequest(BaseModel):
    url: str
    language: Optional[str] = None
    force_reload: Optional[bool] = False

class SettingsRequest(BaseModel):
    gemini_api_key: str

class ChatRequest(BaseModel):
    history_id: str
    message: str

@app.get("/api/settings")
def get_settings():
    key = get_setting("GEMINI_API_KEY", "")
    has_key = bool(key and len(key.strip()) > 5)
    masked = f"{key[:4]}...{key[-4:]}" if has_key and len(key) > 8 else ""
    return {
        "has_gemini_key": has_key,
        "masked_key": masked
    }

@app.post("/api/settings")
def save_settings(req: SettingsRequest):
    set_setting("GEMINI_API_KEY", req.gemini_api_key.strip())
    return {"status": "success", "message": "Chave de API salva com sucesso!"}

@app.get("/api/history")
def list_history():
    return {"items": get_history_items()}

@app.get("/api/history/{item_id}")
def fetch_history_item(item_id: str):
    item = get_history_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado no histórico")
    return item

@app.delete("/api/history/{item_id}")
def remove_history_item(item_id: str):
    delete_history_item(item_id)
    return {"status": "success"}

@app.post("/api/process-youtube")
def process_youtube(req: YoutubeRequest):
    video_id = extract_video_id(req.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Link do YouTube inválido. Cole uma URL como https://www.youtube.com/watch?v=... ou https://youtu.be/...")
        
    # Check if video already exists in history (unless forced reload)
    history_id = f"yt_{video_id}"
    if not req.force_reload:
        existing = get_history_item(history_id)
        if existing and existing.get("transcript"):
            return {
                "status": "cached",
                "item": existing
            }
            
    # 1. Fetch metadata
    meta = get_video_metadata(video_id)
    
    # 2. Fetch transcript
    try:
        transcript_data = get_transcript(video_id, preferred_lang=req.language)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Não foi possível obter a transcrição do YouTube: {str(e)}. "
                   f"Dica: Vídeos precisam ter legendas (automáticas ou manuais) habilitadas."
        )
        
    # 3. Generate Highlights and Summary
    highlights = generate_video_highlights(
        transcript_data=transcript_data,
        title=meta["title"],
        author=meta["author"]
    )
    
    item = {
        "id": history_id,
        "video_id": video_id,
        "title": meta["title"],
        "author": meta["author"],
        "duration": meta["duration"],
        "duration_str": meta.get("duration_str", "00:00"),
        "thumbnail": meta["thumbnail"],
        "url": meta["url"],
        "source_type": "youtube",
        "transcript": transcript_data["segments"],
        "paragraphs": transcript_data["paragraphs"],
        "summary_markdown": highlights["summary_markdown"],
        "takeaways": highlights["takeaways"],
        "chapters": highlights["chapters"],
        "is_ai_generated": highlights.get("is_ai_generated", False)
    }
    
    save_history_item(item)
    return {
        "status": "success",
        "item": item
    }

@app.post("/api/upload-file")
async def upload_audio_video(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename)[1].lower()
    allowed_exts = [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp4", ".mov", ".mkv", ".webm"]
    if suffix not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Extensão não suportada ({suffix}). Suportados: {', '.join(allowed_exts)}")
        
    temp_dir = tempfile.mkdtemp()
    raw_path = os.path.join(temp_dir, f"input_{file.filename}")
    converted_path = os.path.join(temp_dir, "audio.mp3")
    
    try:
        with open(raw_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Convert to standard audio
        success = convert_to_audio(raw_path, converted_path)
        process_path = converted_path if success and os.path.exists(converted_path) else raw_path
        
        # Transcribe with Gemini
        transcription = transcribe_audio_file(process_path, filename=file.filename)
        
        # Generate highlights
        highlights = generate_video_highlights(
            transcript_data=transcription,
            title=transcription["title"],
            author=transcription["author"]
        )
        
        item_id = f"file_{uuid.uuid4().hex[:10]}"
        item = {
            "id": item_id,
            "video_id": None,
            "title": transcription["title"],
            "author": transcription["author"],
            "duration": transcription["duration"],
            "duration_str": transcription["duration_str"],
            "thumbnail": "",
            "url": "",
            "source_type": "file",
            "transcript": transcription["segments"],
            "paragraphs": transcription["paragraphs"],
            "summary_markdown": highlights["summary_markdown"],
            "takeaways": highlights["takeaways"],
            "chapters": highlights["chapters"],
            "is_ai_generated": highlights.get("is_ai_generated", False)
        }
        save_history_item(item)
        return {"status": "success", "item": item}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/api/chat")
def handle_chat(req: ChatRequest):
    item = get_history_item(req.history_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
        
    chat_history = get_chat_history(req.history_id)
    save_chat_message(req.history_id, "user", req.message)
    
    reply = answer_video_chat(
        question=req.message,
        history_item=item,
        chat_history=chat_history
    )
    
    save_chat_message(req.history_id, "assistant", reply)
    updated_history = get_chat_history(req.history_id)
    return {
        "reply": reply,
        "chat_history": updated_history
    }

@app.get("/api/chat/{history_id}")
def fetch_chat(history_id: str):
    return {"messages": get_chat_history(history_id)}

@app.get("/api/export/{item_id}")
def export_file(item_id: str, format: str = "md"):
    item = get_history_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
        
    safe_title = "".join([c if c.isalnum() or c in " -_" else "_" for c in item.get("title", "transcricao")])[:40]
    segments = item.get("transcript", [])
    
    if format == "srt":
        content = export_to_srt(segments)
        media_type = "application/x-subrip"
        filename = f"{safe_title}.srt"
    elif format == "vtt":
        content = export_to_vtt(segments)
        media_type = "text/vtt"
        filename = f"{safe_title}.vtt"
    elif format == "txt":
        content = export_to_txt(segments, with_timestamps=True)
        media_type = "text/plain; charset=utf-8"
        filename = f"{safe_title}.txt"
    else: # markdown default
        content = export_to_markdown(item)
        media_type = "text/markdown; charset=utf-8"
        filename = f"{safe_title}.md"
        
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

# Static files for the frontend
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
