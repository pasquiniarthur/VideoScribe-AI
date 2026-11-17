import sqlite3
import json
import os
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "app.db")

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    
    # Transcripts & Highlights history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id TEXT PRIMARY KEY,
        video_id TEXT,
        title TEXT,
        author TEXT,
        duration INTEGER,
        thumbnail TEXT,
        url TEXT,
        source_type TEXT,
        transcript_json TEXT,
        summary_markdown TEXT,
        takeaways_json TEXT,
        chapters_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Chat messages history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        history_id TEXT,
        role TEXT,
        content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (history_id) REFERENCES history(id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["value"]
    # Check env var fallback
    return os.environ.get(key, default)

def set_setting(key: str, value: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO settings (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()

def save_history_item(item: Dict[str, Any]) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO history (
        id, video_id, title, author, duration, thumbnail, url, source_type,
        transcript_json, summary_markdown, takeaways_json, chapters_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        title = excluded.title,
        author = excluded.author,
        duration = excluded.duration,
        thumbnail = excluded.thumbnail,
        transcript_json = excluded.transcript_json,
        summary_markdown = excluded.summary_markdown,
        takeaways_json = excluded.takeaways_json,
        chapters_json = excluded.chapters_json
    """, (
        item["id"],
        item.get("video_id"),
        item.get("title", "Sem título"),
        item.get("author", "Desconhecido"),
        item.get("duration", 0),
        item.get("thumbnail", ""),
        item.get("url", ""),
        item.get("source_type", "youtube"),
        json.dumps(item.get("transcript", []), ensure_ascii=False),
        item.get("summary_markdown", ""),
        json.dumps(item.get("takeaways", []), ensure_ascii=False),
        json.dumps(item.get("chapters", []), ensure_ascii=False),
    ))
    conn.commit()
    conn.close()
    return item["id"]

def get_history_items(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, video_id, title, author, duration, thumbnail, url, source_type, created_at
    FROM history
    ORDER BY created_at DESC
    LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_history_item(item_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM history WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["transcript"] = json.loads(data["transcript_json"]) if data.get("transcript_json") else []
    data["takeaways"] = json.loads(data["takeaways_json"]) if data.get("takeaways_json") else []
    data["chapters"] = json.loads(data["chapters_json"]) if data.get("chapters_json") else []
    return data

def delete_history_item(item_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
    cursor.execute("DELETE FROM chat_history WHERE history_id = ?", (item_id,))
    conn.commit()
    conn.close()
    return True

def save_chat_message(history_id: str, role: str, content: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (history_id, role, content) VALUES (?, ?, ?)", (history_id, role, content))
    conn.commit()
    conn.close()

def get_chat_history(history_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role, content, created_at FROM chat_history WHERE history_id = ? ORDER BY id ASC", (history_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
