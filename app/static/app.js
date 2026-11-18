// VideoScribe AI Client Application
let currentItem = null;
let ytPlayer = null;
let ytPlayerReady = false;
let playbackTrackerInterval = null;
let activeTab = 'highlights';

// Helper to convert MM:SS or HH:MM:SS string to seconds
function parseTimestampToSeconds(ts) {
  if (!ts) return 0;
  const parts = ts.trim().replace(/[\[\]]/g, '').split(':').map(Number);
  if (parts.length === 3) {
    return (parts[0] * 3600) + (parts[1] * 60) + parts[2];
  } else if (parts.length === 2) {
    return (parts[0] * 60) + parts[1];
  }
  return 0;
}

// Convert seconds to MM:SS or HH:MM:SS
function formatSeconds(secs) {
  secs = Math.floor(secs);
  const hours = Math.floor(secs / 3600);
  const minutes = Math.floor((secs % 3600) / 60);
  const seconds = secs % 60;
  if (hours > 0) {
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

// YouTube IFrame API Callback
function onYouTubeIframeAPIReady() {
  console.log("YouTube IFrame API Ready");
}

function initYouTubePlayer(videoId) {
  const container = document.getElementById("youtube-player-container");
  container.innerHTML = '<div id="yt-player"></div>';
  container.classList.remove("hidden");
  document.getElementById("local-player-container").classList.add("hidden");

  ytPlayerReady = false;
  try {
    ytPlayer = new YT.Player('yt-player', {
      height: '100%',
      width: '100%',
      videoId: videoId,
      playerVars: {
        'playsinline': 1,
        'rel': 0,
        'modestbranding': 1
      },
      events: {
        'onReady': () => {
          ytPlayerReady = true;
          startPlaybackTracker();
        }
      }
    });
  } catch (err) {
    console.error("Error creating YT Player:", err);
  }
}

// Seek video player to specific second
function seekToSeconds(seconds) {
  if (currentItem && currentItem.source_type === 'youtube' && ytPlayer && ytPlayerReady) {
    ytPlayer.seekTo(seconds, true);
    ytPlayer.playVideo();
  } else {
    const audio = document.getElementById("local-audio-player");
    if (audio) {
      audio.currentTime = seconds;
      audio.play();
    }
  }
}

// Monitor playback time to highlight transcript in real-time
function startPlaybackTracker() {
  if (playbackTrackerInterval) clearInterval(playbackTrackerInterval);
  playbackTrackerInterval = setInterval(() => {
    let currentTime = 0;
    if (currentItem && currentItem.source_type === 'youtube' && ytPlayer && ytPlayerReady && typeof ytPlayer.getCurrentTime === 'function') {
      try {
        currentTime = ytPlayer.getCurrentTime();
      } catch (e) {}
    } else {
      const audio = document.getElementById("local-audio-player");
      if (audio && !audio.paused) {
        currentTime = audio.currentTime;
      }
    }

    if (currentTime > 0) {
      highlightActiveSegment(currentTime);
    }
  }, 800);
}

function highlightActiveSegment(currentTime) {
  const segments = document.querySelectorAll(".transcript-segment");
  let activeElement = null;

  segments.forEach(el => {
    const start = parseFloat(el.getAttribute("data-start") || 0);
    const duration = parseFloat(el.getAttribute("data-duration") || 5);
    if (currentTime >= start && currentTime <= (start + duration + 1.5)) {
      el.classList.add("active-segment");
      activeElement = el;
    } else {
      el.classList.remove("active-segment");
    }
  });
}

// Replace [MM:SS] in text with interactive timestamp buttons
function renderInteractiveTimestamps(text) {
  if (!text) return "";
  return text.replace(/\[(\d{1,2}:\d{2}(?::\d{2})?)\]/g, (match, ts) => {
    const secs = parseTimestampToSeconds(ts);
    return `<button class="timestamp-tag" onclick="seekToSeconds(${secs})" title="Pular para ${ts}">⏱️ ${ts}</button>`;
  });
}

// Toast notification helper
function showToast(msg) {
  const toast = document.getElementById("toast");
  const msgEl = document.getElementById("toast-message");
  msgEl.textContent = msg;
  toast.classList.remove("hidden");
  setTimeout(() => {
    toast.classList.add("hidden");
  }, 2800);
}

// Paste clipboard into URL input
async function pasteClipboard() {
  try {
    const text = await navigator.clipboard.readText();
    if (text) {
      document.getElementById("youtube-url-input").value = text;
      showToast("Link colado!");
    }
  } catch (err) {
    showToast("Permissão de leitura negada pelo navegador");
  }
}

// Tab Switching
function switchTab(tab) {
  activeTab = tab;
  ['highlights', 'transcript', 'chat'].forEach(t => {
    const btn = document.getElementById(`tab-btn-${t}`);
    const content = document.getElementById(`tab-content-${t}`);
    if (t === tab) {
      btn.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition bg-brand-600 text-white shadow-sm";
      content.classList.remove("hidden");
      if (t === 'transcript' || t === 'chat') {
        content.classList.add("flex");
      }
    } else {
      btn.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition text-zinc-400 hover:text-white hover:bg-zinc-800/60";
      content.classList.add("hidden");
      content.classList.remove("flex");
    }
  });
  lucide.createIcons();
}

// Process YouTube Form Submit
async function handleFormSubmit(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("youtube-url-input");
  const url = input.value.trim();
  const lang = document.getElementById("lang-select").value;
  if (!url) return;

  hideError();
  showLoading("Processando vídeo do YouTube...", "Obtendo metadados e transcrição oficial...");

  try {
    const res = await fetch("/api/process-youtube", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url, language: lang })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Falha ao processar o vídeo.");
    }

    displayLoadedVideo(data.item);
    loadHistoryList();
  } catch (err) {
    showError(err.message);
  } finally {
    hideLoading();
  }
}

// Handle Local File Upload
async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  hideError();
  showLoading("Processando arquivo...", "Convertendo áudio e transcrevendo via IA...");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/upload-file", {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Falha no envio do arquivo.");
    }

    displayLoadedVideo(data.item);
    loadHistoryList();
  } catch (err) {
    showError(err.message);
  } finally {
    hideLoading();
    event.target.value = "";
  }
}

// Display Loaded Video in Workspace
function displayLoadedVideo(item) {
  currentItem = item;

  // Metadata
  document.getElementById("video-title").textContent = item.title || "Sem título";
  document.getElementById("video-author").textContent = item.author || "Criador";
  document.getElementById("video-duration").textContent = item.duration_str || "00:00";

  const extLink = document.getElementById("video-external-link");
  if (item.url) {
    extLink.href = item.url;
    extLink.classList.remove("hidden");
  } else {
    extLink.classList.add("hidden");
  }

  // Setup player
  if (item.source_type === 'youtube' && item.video_id) {
    initYouTubePlayer(item.video_id);
  } else {
    // Local player setup
    document.getElementById("youtube-player-container").classList.add("hidden");
    document.getElementById("local-player-container").classList.remove("hidden");
  }

  // Render Stats
  const fullText = (item.transcript || []).map(s => s.text).join(" ");
  const wordCount = fullText.split(/\s+/).filter(Boolean).length;
  const readTime = Math.max(1, Math.ceil(wordCount / 180));
  document.getElementById("stat-word-count").textContent = wordCount.toLocaleString('pt-BR');
  document.getElementById("stat-read-time").textContent = `${readTime} min`;
  document.getElementById("stat-segment-count").textContent = (item.transcript || []).length;

  // Render Takeaways
  const takeawaysList = document.getElementById("takeaways-list");
  takeawaysList.innerHTML = "";
  const takeaways = item.takeaways || [];
  if (takeaways.length > 0) {
    document.getElementById("takeaways-box").classList.remove("hidden");
    takeaways.forEach(t => {
      const li = document.createElement("li");
      li.className = "flex items-start gap-2 leading-relaxed";
      li.innerHTML = `<span class="text-brand-400 mt-1 font-bold">•</span> <span>${renderInteractiveTimestamps(t)}</span>`;
      takeawaysList.appendChild(li);
    });
  } else {
    document.getElementById("takeaways-box").classList.add("hidden");
  }

  // Render Chapters
  const chaptersList = document.getElementById("chapters-list");
  chaptersList.innerHTML = "";
  const chapters = item.chapters || [];
  if (chapters.length > 0) {
    document.getElementById("chapters-box").classList.remove("hidden");
    chapters.forEach(ch => {
      const secs = ch.seconds !== undefined ? ch.seconds : parseTimestampToSeconds(ch.timestamp);
      const card = document.createElement("div");
      card.className = "flex items-start gap-3 p-2.5 rounded-xl bg-zinc-950/60 border border-zinc-800/80 hover:border-brand-500/50 hover:bg-zinc-800/30 transition cursor-pointer group";
      card.onclick = () => seekToSeconds(secs);
      card.innerHTML = `
        <button class="timestamp-tag shrink-0 mt-0.5 group-hover:bg-brand-500 group-hover:text-white transition">
          ⏱️ ${ch.timestamp || formatSeconds(secs)}
        </button>
        <div class="flex-1 min-w-0">
          <div class="text-xs font-bold text-zinc-200 group-hover:text-brand-300 transition truncate">${ch.title}</div>
          <div class="text-[11px] text-zinc-400 line-clamp-2 mt-0.5">${ch.summary || ""}</div>
        </div>
      `;
      chaptersList.appendChild(card);
    });
  } else {
    document.getElementById("chapters-box").classList.add("hidden");
  }

  // Render Markdown Summary
  const summaryBox = document.getElementById("summary-content");
  let rawMd = item.summary_markdown || "Nenhum resumo gerado.";
  // Convert markdown to HTML via Marked
  let parsedHtml = marked.parse(rawMd);
  // Inject interactive buttons
  summaryBox.innerHTML = renderInteractiveTimestamps(parsedHtml);

  // Render Transcript
  renderTranscript(item.paragraphs || item.transcript || []);

  // Update Export links
  document.getElementById("btn-export-md").href = `/api/export/${item.id}?format=md`;
  document.getElementById("btn-export-srt").href = `/api/export/${item.id}?format=srt`;
  document.getElementById("btn-export-txt").href = `/api/export/${item.id}?format=txt`;

  // Load chat messages
  loadChatMessages(item.id);

  // Show Workspace
  document.getElementById("workspace-section").classList.remove("hidden");
  switchTab("highlights");
  lucide.createIcons();

  // Scroll to workspace smoothly
  document.getElementById("workspace-section").scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Render Transcript Segments List
function renderTranscript(segments, filterText = "") {
  const container = document.getElementById("transcript-container");
  container.innerHTML = "";

  const query = filterText.toLowerCase().trim();
  let matchesCount = 0;

  segments.forEach(seg => {
    const text = seg.text || "";
    const isMatch = !query || text.toLowerCase().includes(query);

    if (query && isMatch) {
      matchesCount++;
    }

    if (!isMatch) return;

    let displayText = text;
    if (query) {
      const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, "gi");
      displayText = displayText.replace(regex, '<mark class="search-highlight">$1</mark>');
    }

    const secs = seg.start !== undefined ? seg.start : parseTimestampToSeconds(seg.timestamp);
    const div = document.createElement("div");
    div.className = "transcript-segment p-2.5 rounded-xl hover:bg-zinc-800/40 border border-transparent hover:border-zinc-800 transition flex items-start gap-3 cursor-pointer";
    div.setAttribute("data-start", secs);
    div.setAttribute("data-duration", seg.duration || 5);
    div.onclick = () => seekToSeconds(secs);

    div.innerHTML = `
      <button class="timestamp-tag shrink-0 mt-0.5" title="Ouvir a partir de ${seg.timestamp}">
        ${seg.timestamp || formatSeconds(secs)}
      </button>
      <div class="text-xs md:text-sm text-zinc-300 leading-relaxed flex-1 select-text">
        ${displayText}
      </div>
    `;
    container.appendChild(div);
  });

  const countBadge = document.getElementById("search-matches-count");
  if (query) {
    countBadge.textContent = `${matchesCount} ocorrência(s)`;
  } else {
    countBadge.textContent = "";
  }
}

// Transcript Live Search Handler
function handleTranscriptSearch(e) {
  const val = e.target.value;
  const clearBtn = document.getElementById("btn-clear-search");
  if (val) {
    clearBtn.classList.remove("hidden");
  } else {
    clearBtn.classList.add("hidden");
  }
  if (currentItem) {
    renderTranscript(currentItem.paragraphs || currentItem.transcript || [], val);
  }
}

function clearTranscriptSearch() {
  const input = document.getElementById("transcript-search-input");
  input.value = "";
  document.getElementById("btn-clear-search").classList.add("hidden");
  if (currentItem) {
    renderTranscript(currentItem.paragraphs || currentItem.transcript || [], "");
  }
}

// Copy Full Raw Transcript
function copyRawTranscript() {
  if (!currentItem) return;
  const segments = currentItem.paragraphs || currentItem.transcript || [];
  const text = segments.map(s => `[${s.timestamp}] ${s.text}`).join("\n\n");
  navigator.clipboard.writeText(text);
  showToast("Transcrição completa copiada!");
}

// Copy Markdown
async function copyMarkdownToClipboard() {
  if (!currentItem) return;
  try {
    const res = await fetch(`/api/export/${currentItem.id}?format=md`);
    const md = await res.text();
    await navigator.clipboard.writeText(md);
    showToast("Resumo em Markdown copiado!");
    closeExportMenu();
  } catch (err) {
    showToast("Erro ao copiar markdown.");
  }
}

// Export Dropdown menu toggle
function toggleExportMenu() {
  const menu = document.getElementById("export-menu");
  menu.classList.toggle("hidden");
}
function closeExportMenu() {
  document.getElementById("export-menu").classList.add("hidden");
}
document.addEventListener("click", (e) => {
  const wrapper = document.getElementById("export-dropdown-wrapper");
  if (wrapper && !wrapper.contains(e.target)) {
    closeExportMenu();
  }
});

// Chat handlers
async function handleChatSubmit(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg || !currentItem) return;

  input.value = "";
  appendChatMessage("user", msg);

  const sendBtn = document.getElementById("btn-chat-send");
  sendBtn.disabled = true;

  // Typing indicator
  const typingId = appendTypingIndicator();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        history_id: currentItem.id,
        message: msg
      })
    });

    const data = await res.json();
    removeTypingIndicator(typingId);

    if (data.reply) {
      appendChatMessage("assistant", data.reply);
    }
  } catch (err) {
    removeTypingIndicator(typingId);
    appendChatMessage("assistant", `Desculpe, ocorreu um erro ao consultar a IA: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
  }
}

function useQuickQuestion(q) {
  document.getElementById("chat-input").value = q;
  handleChatSubmit();
}

function appendChatMessage(role, content) {
  const chatMessages = document.getElementById("chat-messages");
  const isUser = role === "user";

  const msgDiv = document.createElement("div");
  msgDiv.className = `flex flex-col ${isUser ? 'items-end' : 'items-start'} gap-1`;

  const bubble = document.createElement("div");
  bubble.className = isUser 
    ? "bg-brand-600 text-white rounded-2xl rounded-tr-none px-4 py-2.5 text-xs md:text-sm max-w-[85%] shadow-md leading-relaxed" 
    : "bg-zinc-950 border border-zinc-800 text-zinc-200 rounded-2xl rounded-tl-none px-4 py-2.5 text-xs md:text-sm max-w-[85%] shadow-md leading-relaxed";

  if (isUser) {
    bubble.textContent = content;
  } else {
    // Parse markdown and timestamps in assistant answer
    bubble.innerHTML = renderInteractiveTimestamps(marked.parse(content));
  }

  msgDiv.appendChild(bubble);
  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendTypingIndicator() {
  const id = `typing-${Date.now()}`;
  const chatMessages = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.id = id;
  div.className = "flex items-center gap-1.5 p-3 rounded-2xl bg-zinc-950 border border-zinc-800 max-w-[120px]";
  div.innerHTML = `
    <span class="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce"></span>
    <span class="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce" style="animation-delay: 0.2s"></span>
    <span class="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce" style="animation-delay: 0.4s"></span>
  `;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

async function loadChatMessages(historyId) {
  const chatMessages = document.getElementById("chat-messages");
  // Keep the welcome box, clear old messages
  chatMessages.querySelectorAll(".flex.flex-col").forEach(e => e.remove());

  try {
    const res = await fetch(`/api/chat/${historyId}`);
    const data = await res.json();
    if (data.messages && data.messages.length > 0) {
      data.messages.forEach(m => {
        appendChatMessage(m.role, m.content);
      });
    }
  } catch (err) {
    console.error("Error loading chat history:", err);
  }
}

// History Drawer & List Management
function toggleHistoryDrawer() {
  const drawer = document.getElementById("history-drawer");
  drawer.classList.toggle("hidden");
  if (!drawer.classList.contains("hidden")) {
    loadHistoryList();
  }
}

async function loadHistoryList() {
  try {
    const res = await fetch("/api/history");
    const data = await res.json();
    const list = document.getElementById("history-items-list");
    list.innerHTML = "";

    if (!data.items || data.items.length === 0) {
      list.innerHTML = '<div class="text-xs text-zinc-500 text-center py-8">Nenhum vídeo no histórico ainda.</div>';
      return;
    }

    data.items.forEach(item => {
      const card = document.createElement("div");
      card.className = "p-2.5 rounded-xl bg-zinc-950/80 border border-zinc-800 hover:border-brand-500/50 transition cursor-pointer flex items-center justify-between gap-3 group";
      card.onclick = () => loadHistoryItemById(item.id);

      card.innerHTML = `
        <div class="flex items-center gap-2.5 min-w-0">
          <div class="w-12 h-8 rounded bg-zinc-800 overflow-hidden shrink-0 flex items-center justify-center">
            ${item.thumbnail ? `<img src="${item.thumbnail}" class="w-full h-full object-cover">` : '<i data-lucide="video" class="w-4 h-4 text-zinc-500"></i>'}
          </div>
          <div class="min-w-0">
            <div class="text-xs font-semibold text-zinc-200 group-hover:text-brand-300 transition truncate">${item.title}</div>
            <div class="text-[10px] text-zinc-500 truncate">${item.author || "Criador"}</div>
          </div>
        </div>
        <button onclick="event.stopPropagation(); deleteItemById('${item.id}')" class="p-1 rounded text-zinc-500 hover:text-red-400 hover:bg-zinc-800 transition" title="Excluir">
          <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
        </button>
      `;
      list.appendChild(card);
    });
    lucide.createIcons();
  } catch (err) {
    console.error("Error loading history:", err);
  }
}

async function loadHistoryItemById(id) {
  showLoading("Carregando vídeo...", "Recuperando dados do histórico local...");
  try {
    const res = await fetch(`/api/history/${id}`);
    const item = await res.json();
    if (res.ok) {
      displayLoadedVideo(item);
      toggleHistoryDrawer();
    }
  } catch (err) {
    showError("Erro ao carregar item do histórico");
  } finally {
    hideLoading();
  }
}

async function deleteItemById(id) {
  if (!confirm("Deseja realmente remover este item do histórico?")) return;
  try {
    await fetch(`/api/history/${id}`, { method: "DELETE" });
    loadHistoryList();
    if (currentItem && currentItem.id === id) {
      resetToHome();
    }
  } catch (err) {
    console.error("Error deleting item:", err);
  }
}

function resetToHome() {
  document.getElementById("workspace-section").classList.add("hidden");
  document.getElementById("youtube-url-input").value = "";
  if (ytPlayer && typeof ytPlayer.stopVideo === 'function') {
    try { ytPlayer.stopVideo(); } catch (e) {}
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// UI State helpers
let loadingInterval = null;

function showLoading(title, subtitle) {
  document.getElementById("loading-title").textContent = title;
  document.getElementById("loading-subtitle").textContent = subtitle;
  document.getElementById("loading-card").classList.remove("hidden");
  document.getElementById("loading-card").classList.add("flex");
  document.getElementById("loading-card").scrollIntoView({ behavior: 'smooth', block: 'center' });

  const messages = [
    { title: "Processando vídeo com a IA...", sub: "Analisando o áudio e a estrutura do conteúdo..." },
    { title: "Identificando tópicos e timestamps...", sub: "Mapeando os momentos mais importantes da fala..." },
    { title: "Criando resumo executivo...", sub: "Quase pronto! Organizando as anotações e aprendizados chave..." }
  ];

  let step = 0;
  if (loadingInterval) clearInterval(loadingInterval);
  loadingInterval = setInterval(() => {
    if (step < messages.length) {
      document.getElementById("loading-title").textContent = messages[step].title;
      document.getElementById("loading-subtitle").textContent = messages[step].sub;
      step++;
    }
  }, 6000);
}

function hideLoading() {
  if (loadingInterval) clearInterval(loadingInterval);
  document.getElementById("loading-card").classList.add("hidden");
  document.getElementById("loading-card").classList.remove("flex");
}

function showError(msg) {
  document.getElementById("error-message").textContent = msg;
  document.getElementById("error-card").classList.remove("hidden");
  document.getElementById("error-card").scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function hideError() {
  document.getElementById("error-card").classList.add("hidden");
}

// Init on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();
});
