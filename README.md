# VideoScribe AI 🎥✨

Um aplicativo moderno e completo para **transcrever, resumir, extrair tópicos com timestamps interativos e conversar com vídeos e áudios do YouTube por link**.

---

## ✨ Principais Funcionalidades

1. **Transcrição Instantânea com Timestamps**:
   - Cole qualquer link do YouTube (`watch?v=...`, `youtu.be/...`, ou `shorts/...`).
   - Obtém a transcrição oficial em português, inglês, espanhol, etc. em poucos segundos.
   - Timestamps clicáveis sincronizados: clique em qualquer trecho `[02:15]` e o player do vídeo pula exatamente para aquele segundo.

2. **Destaques e Resumo Inteligente (AI Highlights)**:
   - **Key Takeaways**: Principais aprendizados e conclusões resumidos em tópicos.
   - **Capítulos & Linha do Tempo**: Tópicos com minutagem e resumo de cada bloco do vídeo.
   - **Resumo Executivo Detalhado**: Formatação rica em Markdown com links e minutagens.

3. **Player Sincronizado do YouTube**:
   - Player embutido nativo do YouTube IFrame.
   - Acompanhamento em tempo real: o texto da transcrição é destacado conforme o vídeo é reproduzido.

4. **Busca e Filtro em Tempo Real**:
   - Barra de pesquisa integrada na transcrição com destaque visual dos termos encontrados.
   - Estatísticas completas: contagem de palavras, estimativa de tempo de leitura e quantidade de falas.

5. **Chat com o Vídeo (Pergunte à IA)**:
   - Tire dúvidas sobre qualquer tema discutido no vídeo.
   - A IA responde citando os minutos e segundos onde a informação foi dita.

6. **Exportação Versátil**:
   - **Copiar Markdown**: Perfeito para Notion, Obsidian e anotações.
   - **Baixar .SRT**: Formato de legendas profissionais (compatível com Premiere, DaVinci Resolve, CapCut, VLC).
   - **Baixar .TXT**: Transcrição limpa com ou sem timestamps.
   - **Baixar .MD**: Arquivo Markdown completo.

7. **Histórico Local Persistente**:
   - Banco de dados SQLite local (`data/app.db`) que salva todos os vídeos transcritos.
   - Reabra qualquer vídeo do passado instantaneamente sem precisar reprocessar.

8. **Upload de Áudio / Vídeo do Computador**:
   - Além do YouTube, suporte para enviar arquivos `.mp3`, `.wav`, `.m4a`, `.mp4`, etc.

---

## 🚀 Como Executar

### Opção 1: Pelo executável rápido (Windows)
Basta dar dois cliques no arquivo:
```
iniciar.bat
```

### Opção 2: Pelo terminal
```powershell
# Ativar o ambiente virtual
.\.venv\Scripts\Activate.ps1

# Iniciar o aplicativo
python run.py
```
O navegador abrirá automaticamente em `http://localhost:8000`.

---

## 🔑 Ativando a Inteligência Artificial (Google Gemini)

O aplicativo funciona para transcrição **mesmo sem chave de API**. Porém, para ativar os **resumos inteligentes com IA, tópicos automáticos e o Chat com o Vídeo**, recomendamos configurar uma chave gratuita do Google Gemini:

1. Acesse [Google AI Studio](https://aistudio.google.com/apikey).
2. Clique em **Create API Key** (gratuito).
3. No aplicativo, clique no botão **API Key** no canto superior direito e cole a chave.
4. Pronto! Todos os resumos e o chat funcionarão com a IA de ponta do Gemini.
