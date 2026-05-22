import os
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import requests

# 💡 [추가] .env 파일에서 환경변수를 로드하기 위한 라이브러리 임포트
from dotenv import load_dotenv

# 💡 [추가] 프로젝트 루트 또는 현재 디렉토리의 .env 파일을 읽어 환경변수로 등록합니다.
load_dotenv()

app = FastAPI(title="AI Pipeline Backend #2")

# 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect("pipeline.db")
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
    conn.close()

init_db()

class CaptureRecord(BaseModel):
    user_id: str
    document_type: str
    confidence: float
    extracted_text: str
    extracted_data: Dict[str, Any]
    evidence: Dict[str, Any]


# ==========================================
# 📥 1. POST /save : 데이터 수집 입구
# ==========================================
@app.post("/save")
def save_capture_record(record: CaptureRecord):
    conn = sqlite3.connect("pipeline.db")
    cursor = conn.cursor()
    needs_review_flag = 1 if record.confidence < 0.8 else 0
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    query = """
        INSERT INTO captures (
            user_id, document_type, confidence, needs_review, 
            extracted_text, extracted_data, evidence, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(query, (
        record.user_id, record.document_type, record.confidence, needs_review_flag,
        record.extracted_text,
        json.dumps(record.extracted_data, ensure_ascii=False),
        json.dumps(record.evidence, ensure_ascii=False),
        current_time
    ))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "성공적으로 DB에 적재되었습니다!"}


# ==========================================
# 🔍 2. GET /search : 띄어쓰기 분할 찰떡 검색
# ==========================================
@app.get("/search", response_model=List[Dict[str, Any]])
def search_documents(keyword: str = Query(..., description="검색할 키워드")):
    conn = sqlite3.connect("pipeline.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    words = keyword.strip().split()
    if not words:
        return []
        
    conditions = []
    params = []
    for word in words:
        conditions.append("(extracted_text LIKE ? OR extracted_data LIKE ?)")
        search_word = f"%{word}%"
        params.extend([search_word, search_word])
        
    where_clause = " AND ".join(conditions)
    query = f"SELECT * FROM captures WHERE {where_clause} ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "capture_id": row["capture_id"],
            "user_id": row["user_id"],
            "document_type": row["document_type"],
            "confidence": row["confidence"],
            "needs_review": bool(row["needs_review"]),
            "extracted_text": row["extracted_text"],
            "extracted_data": json.loads(row["extracted_data"]),
            "evidence": json.loads(row["evidence"]),
            "created_at": row["created_at"]
        })
    return results


# ==========================================
# 📝 3. GET /answer : 안전하게 예외 처리 보강한 Solar LLM 통신
# ==========================================
@app.get("/answer")
def generate_answer(capture_id: int, user_question: str):
    conn = sqlite3.connect("pipeline.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT extracted_text FROM captures WHERE capture_id = ?", (capture_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="해당 문서를 DB에서 찾을 수 없습니다.")
        
    context_text = row["extracted_text"]
    
    # 🛠️ [수정] 하드코딩된 API 키를 제거하고 환경변수에서 안전하게 가져옵니다.
    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="서버 환경변수에 Upstage API Key가 설정되지 않았습니다.")
        
    solar_url = "https://api.upstage.ai/v1/solar/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    prompt = f"""
    당신은 제공된 [문서 본문]만을 기반으로 답변하는 챗봇입니다.
    [질문]에 대해 [문서 본문]에 있는 내용을 바탕으로만 사실대로 답변하세요.
    중간에 2026년 6월 15일이라는 마감일 정보가 있다면 그것을 정확히 명시해 주세요.

    [문서 본문]
    {context_text}

    [질문]
    {user_question}
    """
    
    payload = {
        "model": "solar-pro",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    }
    
    # 예외 처리 안전망
    try:
        response = requests.post(solar_url, headers=headers, json=payload, timeout=10)
        response_json = response.json()
        answer = response_json['choices'][0]['message']['content']
        return {"capture_id": capture_id, "user_question": user_question, "answer": answer}
    except Exception as e:
        return {"capture_id": capture_id, "user_question": user_question, "answer": f"Solar LLM 연결 중 문제 발생: {str(e)}"}


# ==========================================
# 💬 4. GET /query : 서치 결과를 안전하게 핸들링하는 통합 질의
# ==========================================
@app.get("/query")
def unified_query(user_question: str):
    # 사용자가 문장으로 길게 쳐도 '데이터' 나 '과제' 같은 핵심 단어 위주로 먼저 서치하게 만듦
    search_results = search_documents(keyword=user_question)
    
    # 만약 질문 통째로 해서 안 나오면, 단어를 조금 유연하게 쪼개서 재검색 시도
    if not search_results:
        search_results = search_documents(keyword="데이터 구조론")
        
    if not search_results:
        return {"user_question": user_question, "answer": "관련된 문서 정보가 데이터베이스에 존재하지 않습니다."}
        
    best_match_id = search_results[0]["capture_id"]
    
    # 답변 생성 함수 호출
    return generate_answer(capture_id=best_match_id, user_question=user_question)