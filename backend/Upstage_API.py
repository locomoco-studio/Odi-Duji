import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import requests

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
    
    # Upstage Solar API 설정
    api_key = "up_fSlRNKC2B3kNUAwHTzxmopAkRW9QY"
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
# 💬 4. GET /query : 하드코딩을 제거하고 유연성을 높인 통합 질의 핸들러
# ==========================================
@app.get("/query")
def unified_query(user_question: str):
    """
    사용자의 자연어 질문을 분석하여 데이터베이스에서 최적의 문서를 찾아내고,
    Solar LLM을 통해 답변을 생성하여 검색 결과 리스트와 함께 반환합니다.
    """
    # 전처리: 양끝 공백 제거
    clean_question = user_question.strip()
    if not clean_question:
        return {
            "answer": "질문이 비어 있습니다. 궁금한 점을 입력해 주세요.",
            "results": []
        }

    # 🚀 [1차 시도] 입력된 문장 전체를 기반으로 1차 검색 시도
    print(f"[Query Pipeline] 1차 검색 시도 키워드: '{clean_question}'")
    search_results = search_documents(keyword=clean_question)
    
    # 🚀 [2차 시도] 1차 결과가 없고 문장이 길 경우, 단어별 유연 Fallback 검색 진행
    if not search_results:
        # 공백 기준으로 단어를 쪼갠 후, 조사나 특수문자 등 노이즈가 섞인 짧은 단어 필터링
        words = [w for w in clean_question.split() if len(w) > 1]
        print(f"[Query Pipeline] 1차 검색 실패. 2차 분할 키워드 후보: {words}")
        
        # 쪼개진 단어들 중 가장 핵심이 될 만한 첫 번째 단어 혹은 주요 키워드로 재검색
        for word in words:
            search_results = search_documents(keyword=word)
            if search_results:
                print(f"[Query Pipeline] 2차 검색 성공! 매칭 키워드: '{word}'")
                break  # 유효한 검색 결과를 찾으면 루프 탈출

    # 🚀 [최종 예외 처리] 2차 검색까지 돌렸으나 데이터베이스에 아무것도 없는 경우
    if not search_results:
        print(f"[Query Pipeline] 최종 검색 실패. DB 내 관련 문서 없음.")
        return {
            "user_question": user_question,
            "answer": "죄송합니다. 관련된 문서 정보가 데이터베이스에 존재하지 않습니다. 다른 키워드로 검색해 보시겠어요?",
            "results": []  # 프론트엔드가 크래시 나지 않도록 빈 리스트 구조 유지
        }
        
    # 검색된 결과 중 가장 상단(최신순 혹은 매칭 점수가 높은) 문서의 ID 추출
    best_match_id = search_results[0]["capture_id"]
    
    # Upstage Solar LLM 답변 생성 함수 호출
    ai_response = generate_answer(capture_id=best_match_id, user_question=user_question)
    
    # 프론트엔드 UI(card.js) 렌더링 규격에 맞춰 복합 객체 형태로 최종 반환
    return {
        "answer": ai_response["answer"],
        "results": search_results
    }