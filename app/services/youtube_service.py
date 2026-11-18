import re
import urllib.parse
from typing import Optional, Dict, Any, List
import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def extract_video_id(url_or_id: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    text = url_or_id.strip()
    if len(text) == 11 and re.match(r"^[a-zA-Z0-9_-]{11}$", text):
        return text
    
    # Common regex patterns
    patterns = [
        r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
            
    parsed = urllib.parse.urlparse(text)
    if "youtube.com" in parsed.netloc:
        query = urllib.parse.parse_qs(parsed.query)
        if "v" in query and query["v"]:
            return query["v"][0]
    elif "youtu.be" in parsed.netloc:
        path = parsed.path.strip("/")
        if len(path) == 11:
            return path
            
    return None

def get_video_metadata(video_id: str) -> Dict[str, Any]:
    """Retrieve video title, channel, duration, and thumbnail."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    meta = {
        "video_id": video_id,
        "url": url,
        "title": f"YouTube Video ({video_id})",
        "author": "YouTube Creator",
        "duration": 0,
        "duration_str": "00:00",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    }
    
    is_oembed_404 = False
    # Fast oEmbed check
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        res = requests.get(oembed_url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            meta["title"] = data.get("title", meta["title"])
            meta["author"] = data.get("author_name", meta["author"])
            if data.get("thumbnail_url"):
                meta["thumbnail"] = data.get("thumbnail_url")
        elif res.status_code in (404, 401, 403):
            is_oembed_404 = True
    except Exception:
        pass

    # Detailed extraction via yt-dlp (flat)
    ytdl_unavailable = False
    try:
        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                meta["title"] = info.get("title") or meta["title"]
                meta["author"] = info.get("uploader") or info.get("channel") or meta["author"]
                meta["duration"] = int(info.get("duration") or 0)
                meta["duration_str"] = format_timestamp(meta["duration"])
                if info.get("thumbnail"):
                    meta["thumbnail"] = info.get("thumbnail")
    except Exception as e:
        err_msg = str(e).lower()
        if "unavailable" in err_msg or "not found" in err_msg or "private" in err_msg:
            ytdl_unavailable = True
        print(f"Warning: yt-dlp metadata failed: {e}")

    if is_oembed_404 and ytdl_unavailable:
        meta["is_unavailable"] = True
        
    return meta

def group_transcript_into_paragraphs(snippets: List[Dict[str, Any]], interval_sec: float = 35.0) -> List[Dict[str, Any]]:
    """Group short snippets into readable paragraphs with timestamp anchors."""
    if not snippets:
        return []
        
    paragraphs = []
    current_block = []
    block_start = snippets[0]["start"]
    
    for snip in snippets:
        current_block.append(snip["text"])
        # If segment reached interval or strong sentence terminator at end of block
        current_text = " ".join(current_block)
        time_elapsed = (snip["start"] + snip.get("duration", 0)) - block_start
        
        ends_with_period = snip["text"].strip().endswith((".", "!", "?"))
        if (time_elapsed >= interval_sec and ends_with_period) or time_elapsed >= (interval_sec * 1.5):
            paragraphs.append({
                "start": block_start,
                "timestamp": format_timestamp(block_start),
                "text": current_text.replace("\n", " ").strip()
            })
            current_block = []
            block_start = snip["start"] + snip.get("duration", 0)
            
    if current_block:
        paragraphs.append({
            "start": block_start,
            "timestamp": format_timestamp(block_start),
            "text": " ".join(current_block).replace("\n", " ").strip()
        })
        
    return paragraphs

def get_transcript(video_id: str, preferred_lang: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch YouTube transcript with timestamps.
    Returns:
    {
        "language": "pt",
        "is_generated": False,
        "segments": [{"start": 1.2, "duration": 2.1, "timestamp": "00:01", "text": "..."}],
        "paragraphs": [{"start": 1.2, "timestamp": "00:01", "text": "..."}],
        "full_text": "...",
        "available_languages": [{"code": "pt", "name": "Portuguese"}]
    }
    """
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)
    
    available_langs = []
    for t in transcript_list:
        available_langs.append({
            "code": t.language_code,
            "language": getattr(t, "language", t.language_code),
            "is_generated": t.is_generated
        })
        
    # Search order
    preferred = [preferred_lang] if preferred_lang else []
    preferred.extend(["pt", "pt-BR", "en", "es"])
    
    # Filter out empty/None
    preferred = [p for p in preferred if p]
    
    transcript = None
    selected_lang = None
    is_gen = False
    
    # 1. Try manual transcripts matching preferred
    for p in preferred:
        try:
            transcript = transcript_list.find_manually_created_transcript([p])
            selected_lang = p
            is_gen = False
            break
        except Exception:
            continue
            
    # 2. Try generated transcripts matching preferred
    if not transcript:
        for p in preferred:
            try:
                transcript = transcript_list.find_generated_transcript([p])
                selected_lang = p
                is_gen = True
                break
            except Exception:
                continue

    # 3. Fallback to any transcript available
    if not transcript:
        try:
            transcript = transcript_list.find_transcript(preferred)
        except Exception:
            # Take the very first available
            for t in transcript_list:
                transcript = t
                selected_lang = t.language_code
                is_gen = t.is_generated
                break
                
    if not transcript:
        raise ValueError(f"Nenhuma legenda ou transcrição foi encontrada para este vídeo (ID: {video_id}).")
        
    fetched_data = transcript.fetch()
    
    segments = []
    full_text_parts = []
    
    for item in fetched_data:
        # Fetch item can be dict or FetchedTranscriptSnippet object
        if hasattr(item, "text"):
            text = item.text
            start = float(item.start)
            duration = float(getattr(item, "duration", 0.0))
        elif isinstance(item, dict):
            text = item.get("text", "")
            start = float(item.get("start", 0.0))
            duration = float(item.get("duration", 0.0))
        else:
            continue
            
        clean_text = text.replace("\n", " ").strip()
        if not clean_text:
            continue
            
        segments.append({
            "start": round(start, 2),
            "duration": round(duration, 2),
            "timestamp": format_timestamp(start),
            "text": clean_text
        })
        full_text_parts.append(clean_text)
        
    full_text = " ".join(full_text_parts)
    paragraphs = group_transcript_into_paragraphs(segments)
    
    return {
        "language": selected_lang or getattr(transcript, "language_code", "desconhecido"),
        "is_generated": is_gen,
        "segments": segments,
        "paragraphs": paragraphs,
        "full_text": full_text,
        "available_languages": available_langs
    }
