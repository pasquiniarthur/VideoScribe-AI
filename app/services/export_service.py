from typing import List, Dict, Any

def format_srt_time(seconds: float) -> str:
    """Format seconds into 00:00:00,000 for SRT."""
    millis = int((seconds - int(seconds)) * 1000)
    secs = int(seconds) % 60
    mins = (int(seconds) // 60) % 60
    hours = int(seconds) // 3600
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def format_vtt_time(seconds: float) -> str:
    """Format seconds into 00:00:00.000 for VTT."""
    millis = int((seconds - int(seconds)) * 1000)
    secs = int(seconds) % 60
    mins = (int(seconds) // 60) % 60
    hours = int(seconds) // 3600
    return f"{hours:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

def export_to_srt(segments: List[Dict[str, Any]]) -> str:
    """Generate valid SRT file content."""
    lines = []
    for i, seg in enumerate(segments, start=1):
        start = seg.get("start", 0.0)
        duration = seg.get("duration", 2.0)
        end = start + duration
        
        lines.append(str(i))
        lines.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
        lines.append(seg.get("text", "").strip())
        lines.append("")
    return "\n".join(lines)

def export_to_vtt(segments: List[Dict[str, Any]]) -> str:
    """Generate valid WebVTT file content."""
    lines = ["WEBVTT", ""]
    for i, seg in enumerate(segments, start=1):
        start = seg.get("start", 0.0)
        duration = seg.get("duration", 2.0)
        end = start + duration
        
        lines.append(str(i))
        lines.append(f"{format_vtt_time(start)} --> {format_vtt_time(end)}")
        lines.append(seg.get("text", "").strip())
        lines.append("")
    return "\n".join(lines)

def export_to_txt(segments: List[Dict[str, Any]], with_timestamps: bool = True) -> str:
    """Generate plain text export."""
    lines = []
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        if with_timestamps:
            lines.append(f"[{seg.get('timestamp', '00:00')}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines)

def export_to_markdown(item: Dict[str, Any]) -> str:
    """Generate rich Markdown document (Notion/Obsidian ready)."""
    title = item.get("title", "Transcrição de Vídeo")
    author = item.get("author", "")
    url = item.get("url", "")
    duration = item.get("duration_str", "")
    
    md = [f"# {title}", ""]
    meta = []
    if author:
        meta.append(f"**Autor:** {author}")
    if duration:
        meta.append(f"**Duração:** {duration}")
    if url:
        meta.append(f"**Link:** [{url}]({url})")
    if meta:
        md.append(" | ".join(meta))
        md.append("")
        
    takeaways = item.get("takeaways", [])
    if takeaways:
        md.append("## 💡 Principais Aprendizados (Key Takeaways)")
        for t in takeaways:
            md.append(f"- {t}")
        md.append("")
        
    summary = item.get("summary_markdown", "")
    if summary:
        md.append("## 📝 Resumo & Destaques")
        md.append(summary)
        md.append("")
        
    chapters = item.get("chapters", [])
    if chapters:
        md.append("## ⏱️ Capítulos & Linha do Tempo")
        for ch in chapters:
            ts = ch.get("timestamp", "00:00")
            ch_title = ch.get("title", "Capítulo")
            desc = ch.get("summary", "")
            md.append(f"- **[{ts}] {ch_title}**: {desc}")
        md.append("")
        
    transcript = item.get("transcript", [])
    if transcript:
        md.append("## 📜 Transcrição Completa")
        for seg in transcript:
            ts = seg.get("timestamp", "00:00")
            txt = seg.get("text", "")
            md.append(f"**[{ts}]** {txt}\n")
            
    return "\n".join(md)
