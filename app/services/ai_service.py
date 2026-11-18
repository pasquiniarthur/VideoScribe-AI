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

FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-3.8-flash",
]

def generate_content_with_fallback(client, contents, config=None):
    """Try models sequentially to protect against temporary 503 high demand spikes."""
    last_err = None
    for model_name in FALLBACK_MODELS:
        try:
            return client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
        except Exception as e:
            err_str = str(e)
            print(f"Model {model_name} warning: {err_str}, trying fallback...")
            last_err = e
            if "503" in err_str or "404" in err_str or "high demand" in err_str.lower() or "UNAVAILABLE" in err_str:
                continue
            if "API_KEY_INVALID" in err_str or "403" in err_str:
                raise e
    raise last_err

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
        response = generate_content_with_fallback(
            client=client,
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
        response = generate_content_with_fallback(
            client=client,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4
            )
        )
        return response.text.strip()
    except Exception as e:
        return f"Erro ao consultar a IA: {str(e)}"

def transcribe_youtube_with_gemini(video_id: str, title: str, author: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Direct Gemini Multimodal Video processing for YouTube URLs.
    Bypasses YouTube cloud datacenter IP blocks completely by letting Google process the video directly!
    """
    from app.services.youtube_service import format_timestamp, group_transcript_into_paragraphs
    client = get_gemini_client(api_key)
    if not client:
        raise ValueError("Chave de API do Google Gemini não configurada.")
        
    yt_url = f"https://www.youtube.com/watch?v={video_id}"
    
    prompt = f"""Você é o VideoScribe AI. Analise este vídeo do YouTube ({title} por {author}) e gere a síntese estruturada e a transcrição dos momentos principais com timestamps precisos no formato [MM:SS] ou [HH:MM:SS].

Responda EXCLUSIVAMENTE em formato JSON com a seguinte estrutura:
{{
  "language": "pt",
  "takeaways": [
    "Insight ou aprendizado chave 1",
    "Insight ou aprendizado chave 2",
    "Insight ou aprendizado chave 3",
    "Insight ou aprendizado chave 4"
  ],
  "chapters": [
    {{
      "timestamp": "00:00",
      "seconds": 0,
      "title": "Título conciso da seção",
      "summary": "Resumo do que é abordado neste trecho"
    }}
  ],
  "summary_markdown": "Resumo analítico detalhado do vídeo em Markdown, citando momentos chave no formato [MM:SS].",
  "segments": [
    {{
      "start": 0.0,
      "timestamp": "00:00",
      "text": "Fala e conteúdo deste momento do vídeo..."
    }}
  ]
}}
Divida em 15 a 30 blocos cronológicos representativos cobrindo do início ao fim do vídeo.
Retorne APENAS o JSON válido.
"""

    try:
        response = generate_content_with_fallback(
            client=client,
            contents=[
                types.Part.from_uri(
                    file_uri=yt_url,
                    mime_type="video/*"
                ),
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?", "", raw_text)
            raw_text = re.sub(r"```$", "", raw_text).strip()
            
        data = json.loads(raw_text)
        segments = data.get("segments", [])
        
        for i, s in enumerate(segments):
            start = float(s.get("start", 0.0))
            s["start"] = start
            s["timestamp"] = s.get("timestamp") or format_timestamp(start)
            next_start = float(segments[i+1].get("start", start + 5.0)) if i + 1 < len(segments) else start + 5.0
            s["duration"] = round(max(1.0, next_start - start), 2)
            
        paragraphs = group_transcript_into_paragraphs(segments)
        
        return {
            "language": data.get("language", "pt"),
            "segments": segments,
            "paragraphs": paragraphs,
            "summary_markdown": data.get("summary_markdown", ""),
            "takeaways": data.get("takeaways", []),
            "chapters": data.get("chapters", []),
            "is_ai_generated": True
        }
    except Exception as e:
        raise RuntimeError(f"Falha ao processar vídeo via Gemini: {str(e)}")

