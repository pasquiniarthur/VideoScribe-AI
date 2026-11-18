import os
import subprocess
import json
import re
from typing import Dict, Any, List
from app.services.youtube_service import format_timestamp, group_transcript_into_paragraphs
from app.services.ai_service import get_gemini_client, generate_content_with_fallback

def convert_to_audio(input_path: str, output_path: str) -> bool:
    """Extract audio from video or convert audio to lightweight MP3 using ffmpeg."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vn", "-ar", "16000", "-ac", "1", "-b:a", "64k",
        output_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        return res.returncode == 0
    except Exception as e:
        print(f"ffmpeg conversion error: {e}")
        return False

def get_audio_duration(file_path: str) -> float:
    """Get duration of audio file in seconds."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        return float(res.stdout.strip())
    except Exception:
        return 0.0

def transcribe_audio_file(file_path: str, filename: str, api_key: str = None) -> Dict[str, Any]:
    """Transcribe local audio file using Gemini Multimodal Audio API."""
    client = get_gemini_client(api_key)
    if not client:
        raise ValueError("Para transcrever arquivos locais de áudio/vídeo, configure sua chave do Google Gemini nas Configurações.")
        
    duration = get_audio_duration(file_path)
    
    # Upload file via Gemini Files API
    uploaded_file = client.files.upload(file=file_path)
    
    prompt = """Você é um sistema profissional de transcrição de áudio e vídeo com timestamps.
Transcreva o áudio completo com alta fidelidade no idioma falado.
Divida a fala em segmentos naturais de 15 a 45 segundos com timestamps de início.

Responda EXCLUSIVAMENTE em formato JSON com a seguinte estrutura:
{
  "language": "pt",
  "segments": [
    {
      "start": 0.0,
      "timestamp": "00:00",
      "text": "Primeiro trecho falado..."
    },
    {
      "start": 25.5,
      "timestamp": "00:25",
      "text": "Segundo trecho falado..."
    }
  ]
}
Retorne APENAS o JSON válido.
"""

    try:
        response = generate_content_with_fallback(
            client=client,
            contents=[uploaded_file, prompt]
        )
        
        # Cleanup uploaded remote file
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass
            
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?", "", raw_text)
            raw_text = re.sub(r"```$", "", raw_text).strip()
            
        data = json.loads(raw_text)
        segments = data.get("segments", [])
        
        # Ensure duration fields
        for i, s in enumerate(segments):
            start = float(s.get("start", 0.0))
            s["timestamp"] = format_timestamp(start)
            next_start = float(segments[i+1].get("start", start + 5.0)) if i + 1 < len(segments) else start + 5.0
            s["duration"] = round(max(1.0, next_start - start), 2)
            
        paragraphs = group_transcript_into_paragraphs(segments)
        full_text = " ".join([s.get("text", "") for s in segments])
        
        return {
            "title": os.path.splitext(filename)[0],
            "author": "Arquivo Local",
            "duration": int(duration),
            "duration_str": format_timestamp(duration),
            "language": data.get("language", "pt"),
            "segments": segments,
            "paragraphs": paragraphs,
            "full_text": full_text
        }
    except Exception as e:
        raise RuntimeError(f"Erro na transcrição via Gemini: {str(e)}")
