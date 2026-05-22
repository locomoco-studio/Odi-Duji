import os
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException, Query
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
def init_db():
    conn = sqlite3.connect("pipeline.db")
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
        # [Fix 2] 커넥션 안전 반납
        conn.close()

init_db()

# Pydantic 모델 정의
class CaptureRecord(BaseModel):
    user_id: str
    document_type: str
    confidence: float
    extracted_text: str
    extracted_data: Dict[str, Any]
    evidence: Dict[str, Any]

class AnswerRequest(BaseModel):
    # [Fix 3] POST 요청을 위한 바디 모델 추가
    capture_id: int
    user_question: str


# ==========================================
# 📥 1. POST /save : 데이터 수집 입구
# ==========================================
@app.post("/save")
def save_capture_record(record: CaptureRecord):
    conn = sqlite3.connect("pipeline.db")
    try:
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
    finally:
        conn.close()
        
    return {"status": "success", "message": "성공적으로 DB에 적재되었습니다!"}


# ==========================================
# 🔍 2. GET /search : 띄어쓰기 분할 찰떡 검색
# ==========================================
def escape_like_pattern(word: str) -> str:
    """[Fix 1] LIKE 검색 시 와일드카드로 인식되는 특수문자를 이스케이프 처리합니다."""
    return word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

@app.get("/search", response_model=List[Dict[str, Any]])
def search_documents(keyword: str = Query(..., description="검색할 키워드")):
    words = keyword.strip().split()
    if not words:
        return []
        
    words = words[:5] # [Fix 1] 조건 폭주 방지
        
    conditions = []
    params = []
    for word in words:
        conditions.append("(extracted_text LIKE ? ESCAPE '\\' OR extracted_data LIKE ? ESCAPE '\\')")
        escaped_word = escape_like_pattern(word)
        search_word = f"%{escaped_word}%"
        params.extend([search_word, search_word])
        
    where_clause = " AND ".join(conditions)
    query = f"SELECT * FROM captures WHERE {where_clause} ORDER BY created_at DESC"
    
    conn = sqlite3.connect("pipeline.db")
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
    finally:
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
# ⚙️ [Fix 5] 비즈니스 로직 분리: LLM 답변 생성 핵심 서비스 함수
# ==========================================
def _generate_answer_logic(capture_id: int, user_question: str) -> str:
    """엔드포인트 라우팅 우회 문제를 막기 위해 내부 로직을 분리한 서비스 함수입니다."""
    conn = sqlite3.connect("pipeline.db")
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT extracted_text FROM captures WHERE capture_id = ?", (capture_id,))
        row = cursor.fetchone()
    finally:
        conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="해당 문서를 DB에서 찾을 수 없습니다.")
        
    context_text = row["extracted_text"]
    
    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="서버 환경변수에 Upstage API Key가 설정되지 않았습니다.")
        
    solar_url = os.getenv("SOLAR_API_URL", "https://api.upstage.ai/v1/solar/chat/completions")
    solar_model = os.getenv("SOLAR_MODEL_NAME", "solar-pro")
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    prompt = f"""
    당신은 제공된 [문서 본문]의 내용만을 신뢰하여 질문에 답변하는 대학 생활 비서 에이전트입니다.
    
    [답변 규칙]
    1. 추측이나 외부 지식을 절대 배제하고, 오직 [문서 본문]에 명시된 사실만을 기반으로 답변하세요.
    2. 본문 중에 과제 마감일, 장학금 신청 기한, 행사 일시 등 '날짜 및 시간 정보'가 발견된다면 유저가 놓치지 않도록 정확하고 명확하게 강조하여 답변에 포함해 주세요.
    3. 만약 질문에 대한 답을 [문서 본문]에서 찾을 수 없다면, 억지로 답변을 꾸며내지 말고 "제공된 문서에서 관련 정보를 찾을 수 없습니다."라고 답변하세요.

    [문서 본문]
    {context_text}

    [질문]
    {user_question}
    """
    
    payload = {
        "model": solar_model,  
        "messages": [{"role": "user", "content": prompt.strip()}],
        "temperature": 0.1
    }
    
    try:
        response = requests.post(solar_url, headers=headers, json=payload, timeout=10)
        response.raise_for_status() # 200번대 응답이 아닐 경우 예외 발생
        response_json = response.json()
        return response_json['choices'][0]['message']['content']
    except Exception as e:
        # [Fix 4] 정상 200 OK 내부에 오류 문자열을 담지 않고, 명확한 500 에러를 던집니다.
        raise HTTPException(status_code=500, detail=f"Solar LLM 연결 중 문제 발생: {str(e)}")


# ==========================================
# 📝 3. POST /answer : 단일 질문 응답 엔드포인트
# ==========================================
@app.post("/answer") # [Fix 3] 정보 노출을 막기 위해 GET -> POST로 변경
def generate_answer_endpoint(req: AnswerRequest):
    answer = _generate_answer_logic(req.capture_id, req.user_question)
    return {"capture_id": req.capture_id, "user_question": req.user_question, "answer": answer}


# ==========================================
# 💬 4. GET /query : 통합 질의 핸들러
# ==========================================
@app.get("/query")
def unified_query(user_question: str):
    clean_question = user_question.strip()
    if not clean_question:
        return {
            "answer": "질문이 비어 있습니다. 궁금한 점을 입력해 주세요.",
            "results": []
        }

    search_results = search_documents(keyword=clean_question)
    
    if not search_results:
        words = [w for w in clean_question.split() if len(w) > 1]
        for word in words:
            search_results = search_documents(keyword=word)
            if search_results:
                break 

    if not search_results:
        return {
            "answer": "죄송합니다. 관련된 문서 정보가 데이터베이스에 존재하지 않습니다. 다른 키워드로 검색해 보시겠어요?",
            "results": []
        }
        
    best_match_id = search_results[0]["capture_id"]
    
    try:
        # [Fix 5] 미들웨어 라우터 직접 우회 문제를 방지하기 위해 분리된 순수 파이썬 로직 함수 사용
        final_answer = _generate_answer_logic(capture_id=best_match_id, user_question=user_question)
    except HTTPException as e:
        final_answer = f"시스템 안내: {e.detail}"
    except Exception as e:
        final_answer = f"내부 오류가 발생했습니다: {str(e)}"
    
    return {
        "answer": final_answer,
        "results": search_results
    }