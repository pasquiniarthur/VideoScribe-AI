import json
import re
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
from app.database import get_setting

def get_gemini_client(api_key: Optional[str] = None) -> Optional[genai.Client]:
    """Get initialized Gemini client if API key is configured."""
    key = api_key or get_setting("GEMINI_API_KEY")
    if not key:
        return None
    try:
        return genai.Client(api_key=key.strip())
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        return None

def heuristic_summary(transcript_data: Dict[str, Any], title: str) -> Dict[str, Any]:
    """Fallback smart summary when no API key is provided."""
    paragraphs = transcript_data.get("paragraphs", [])
    segments = transcript_data.get("segments", [])
    
    takeaways = []
    chapters = []
    
    if paragraphs:
        # First paragraph as intro takeaway
        takeaways.append(f"Abertura: {paragraphs[0]['text'][:160]}...")
        if len(paragraphs) > 2:
            mid_idx = len(paragraphs) // 2
            takeaways.append(f"Ponto central: {paragraphs[mid_idx]['text'][:160]}...")
        if len(paragraphs) > 1:
            takeaways.append(f"Conclusão: {paragraphs[-1]['text'][:160]}...")
            
    # Group every ~2-3 minutes as chapters
    last_ch_time = -1000
    for seg in segments:
        start = seg.get("start", 0)
        if start - last_ch_time >= 150: # every 2.5 minutes
            chapters.append({
                "timestamp": seg.get("timestamp", "00:00"),
                "seconds": start,
                "title": f"Tópico em {seg.get('timestamp')}",
                "summary": seg.get("text", "")[:120] + "..."
            })
            last_ch_time = start

    summary_md = f"""### Visão Geral
Este vídeo possui {len(segments)} trechos de fala e duração total transcrita.

*(Dica: Para resumos inteligentes de alto nível com IA, análises aprofundadas e chat interativo, configure sua chave gratuita do Google Gemini nas Configurações no topo da página).*
"""

    return {
        "summary_markdown": summary_md,
        "takeaways": takeaways,
        "chapters": chapters,
        "is_ai_generated": False
    }

def generate_video_highlights(transcript_data: Dict[str, Any], title: str, author: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate rich VideoScribe-style summary using Gemini API.
    Returns:
    {
        "summary_markdown": "...",
        "takeaways": ["point 1", "point 2"],
        "chapters": [{"timestamp": "01:23", "seconds": 83, "title": "...", "summary": "..."}],
        "is_ai_generated": True
    }
    """
    client = get_gemini_client(api_key)
    if not client:
        return heuristic_summary(transcript_data, title)
        
    paragraphs = transcript_data.get("paragraphs", [])
    transcript_with_timestamps = []
    for p in paragraphs[:150]: # ensure manageable context
        transcript_with_timestamps.append(f"[{p.get('timestamp', '00:00')}] {p.get('text', '')}")
    transcript_context = "\n".join(transcript_with_timestamps)
    
    prompt = f"""Você é o VideoScribe AI, um assistente especialista em análise e síntese de vídeos e áudios.
Analise a transcrição abaixo com timestamps e gere uma síntese estruturada e rica em português (ou no idioma original do vídeo).

Título do Vídeo: {title}
Canal/Autor: {author}

Transcrição com timestamps:
{transcript_context}

INSTRUÇÕES DE FORMATO DE RESPOSTA:
Responda EXCLUSIVAMENTE em formato JSON com as seguintes chaves:
{{
  "takeaways": [
    "Insight ou aprendizado chave 1 (curto, direto e impactante)",
    "Insight ou aprendizado chave 2",
    "Insight ou aprendizado chave 3",
    "Insight ou aprendizado chave 4"
  ],
  "chapters": [
    {{
      "timestamp": "00:00",
      "seconds": 0,
      "title": "Título conciso do capítulo/seção",
      "summary": "Breve explicação do que é abordado neste trecho"
    }}
  ],
  "summary_markdown": "Texto em Markdown contendo uma visão geral detalhada do vídeo, tópicos abordados, citações notáveis e conclusões. IMPORTANTE: Sempre que mencionar momentos específicos, inclua o timestamp clicável no formato [MM:SS] ou [HH:MM:SS]."
}}
Retorne APENAS o JSON válido, sem cercas de código Markdown desnecessárias fora do JSON.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        
        raw_text = response.text.strip()
        # Clean potential markdown wrapping if present
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?", "", raw_text)
            raw_text = re.sub(r"```$", "", raw_text).strip()
            
        data = json.loads(raw_text)
        return {
            "summary_markdown": data.get("summary_markdown", ""),
            "takeaways": data.get("takeaways", []),
            "chapters": data.get("chapters", []),
            "is_ai_generated": True
        }
    except Exception as e:
        print(f"Error calling Gemini generate_video_highlights: {e}")
        fallback = heuristic_summary(transcript_data, title)
        fallback["error_message"] = f"Erro na IA: {str(e)}"
        return fallback

def answer_video_chat(question: str, history_item: Dict[str, Any], chat_history: List[Dict[str, Any]], api_key: Optional[str] = None) -> str:
    """Answer a user question based on the video's transcript."""
    client = get_gemini_client(api_key)
    if not client:
        return "⚠️ Chave de API do Gemini não configurada. Adicione sua chave gratuita nas Configurações (ícone de engrenagem no topo) para conversar com o vídeo."
        
    title = history_item.get("title", "")
    author = history_item.get("author", "")
    transcript_segments = history_item.get("transcript", [])
    
    # Format transcript with timestamps
    sample = []
    for s in transcript_segments[:250]:
        sample.append(f"[{s.get('timestamp', '00:00')}] {s.get('text', '')}")
    transcript_text = "\n".join(sample)
    
    conversation_context = []
    for msg in chat_history[-6:]:
        role_label = "Usuário" if msg.get("role") == "user" else "Assistente"
        conversation_context.append(f"{role_label}: {msg.get('content')}")
    history_str = "\n".join(conversation_context)
    
    prompt = f"""Você é o VideoScribe AI, um assistente que responde perguntas sobre o conteúdo de um vídeo/áudio específico.
Responda à pergunta do usuário com base EXCLUSIVAMENTE nas informações fornecidas na transcrição abaixo.

Vídeo: {title} por {author}

Transcrição com timestamps:
{transcript_text}

Histórico da conversa recente:
{history_str}

Pergunta atual do Usuário: {question}

Instruções:
1. Responda de forma clara, educada e direta em português.
2. SEMPRE cite o timestamp exato no formato `[MM:SS]` (ex: `[02:15]`) de onde a informação foi dita, para que o usuário possa clicar e ouvir.
3. Se a informação não foi mencionada no vídeo, diga gentilmente que o assunto não foi abordado no conteúdo transcrito.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4
            )
        )
        return response.text.strip()
    except Exception as e:
        return f"Erro ao consultar a IA: {str(e)}"
