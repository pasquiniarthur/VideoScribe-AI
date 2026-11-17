import os
import sys
import threading
import time
import webbrowser
import uvicorn

def open_browser(port):
    time.sleep(1.2)
    url = f"http://localhost:{port}"
    print(f"\n🚀 Abrindo aplicativo no navegador: {url}\n")
    webbrowser.open(url)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    is_cloud = bool(os.environ.get("RENDER") or os.environ.get("PORT") != "8000" if "PORT" in os.environ else False)
    
    print("=" * 60)
    print("🎥 VideoScribe AI")
    print("Transcrever e Resumir Áudios e Vídeos do YouTube")
    print("=" * 60)
    print(f"Iniciando servidor em http://0.0.0.0:{port} ...")
    
    # Launch browser only if running locally
    if not is_cloud:
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    
    # Start FastAPI server via uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
