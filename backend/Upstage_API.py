import os
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Pipeline Backend #2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터베이스 초기화
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pipeline.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS captures (
                capture_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                document_type TEXT,
                confidence REAL,
                needs_review INTEGER,
                extracted_text TEXT,
                extracted_data TEXT,
                evidence TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()

init_db()

# 데이터 모델
class CaptureRecord(BaseModel):
    user_id: str
    document_type: str
    confidence: float
    extracted_text: str
    extracted_data: Any 
    evidence: Optional[Any] = {} 

class AnswerRequest(BaseModel):
    capture_id: int
    user_question: str

def safe_json_load(data: Any) -> Dict[str, Any]:
    if isinstance(data, str):
        try: return json.loads(data)
        except: return {}
    return data if isinstance(data, dict) else {}

# ==========================================
# 📥 1. POST /save
# ==========================================
@app.post("/save")
def save_capture_record(record: CaptureRecord):
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        needs_review_flag = 1 if record.confidence < 0.8 else 0
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        ext_data = safe_json_load(record.extracted_data)
        evid = safe_json_load(record.evidence)
        
        cursor.execute("""
            INSERT INTO captures (user_id, document_type, confidence, needs_review, 
                                extracted_text, extracted_data, evidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (record.user_id, record.document_type, record.confidence, needs_review_flag,
              record.extracted_text, json.dumps(ext_data, ensure_ascii=False),
              json.dumps(evid, ensure_ascii=False), current_time))
        conn.commit()
    finally:
        conn.close()
    return {"status": "success", "message": "성공적으로 DB에 적재되었습니다!"}

# ==========================================
# 🔍 2. POST /search (수정됨)
# ==========================================
def escape_like_pattern(word: str) -> str:
    return word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

@app.post("/search", response_model=List[Dict[str, Any]])
def search_documents(payload: Dict[str, Any]):
    keyword = payload.get("keyword", "")
    words = keyword.strip().split()[:5]
    if not words: return []
        
    conditions, params = [], []
    for word in words:
        conditions.append("(extracted_text LIKE ? ESCAPE '\\' OR extracted_data LIKE ? ESCAPE '\\')")
        escaped_word = escape_like_pattern(word)
        search_word = f"%{escaped_word}%"
        params.extend([search_word, search_word])
        
    query = f"SELECT * FROM captures WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.cursor().execute(query, params).fetchall()
    finally:
        conn.close()
    
    return [{
        "capture_id": r["capture_id"], "user_id": r["user_id"],
        "document_type": r["document_type"], "confidence": r["confidence"],
        "needs_review": bool(r["needs_review"]), "extracted_text": r["extracted_text"],
        "extracted_data": json.loads(r["extracted_data"]),
        "evidence": json.loads(r["evidence"]), "created_at": r["created_at"]
    } for r in rows]

# ==========================================
# ⚙️ 3. LLM 및 통합 질의
# ==========================================
def _generate_answer_logic(capture_id: int, user_question: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.cursor().execute("SELECT extracted_text FROM captures WHERE capture_id = ?", (capture_id,)).fetchone()
    conn.close()
    
    if not row: raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        
    api_key = os.getenv("UPSTAGE_API_KEY")
    solar_url = os.getenv("SOLAR_API_URL", "https://api.upstage.ai/v1/chat/completions")
    
    prompt = f"당신은 대학 생활 비서입니다. [본문]을 바탕으로 질문에 답변하세요.\n\n[본문]\n{row['extracted_text']}\n\n[질문]\n{user_question}"
    
    response = requests.post(solar_url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                             json={"model": os.getenv("SOLAR_MODEL_NAME", "solar-pro"), "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}, timeout=10)
    
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']

@app.post("/answer")
def generate_answer_endpoint(req: AnswerRequest):
    return {"answer": _generate_answer_logic(req.capture_id, req.user_question)}

@app.get("/query")
def unified_query(user_question: str):
    # 이 부분은 웹에서 직접 호출할 때 사용 가능
    return {"answer": "직접 검색 로직을 구현하거나 POST /search를 사용하세요."}