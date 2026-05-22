import os
import json
import sys
import requests
from dotenv import load_dotenv

# ==========================================
# ⚙️ 1. 환경변수 (.env) 중앙 집중식 로드 설정
# ==========================================
# 스크립트 실행 위치에 관계없이 backend/.env 또는 루트 .env를 유연하게 찾습니다.
current_dir = os.path.dirname(os.path.abspath(__file__))  # data/data/
project_root = os.path.dirname(os.path.dirname(current_dir))  # odi-duji/ 최상위

# 탐색할 .env 경로 후보 리스트
env_candidates = [
    os.path.join(project_root, 'backend', '.env'),  # 1순위: backend/.env
    os.path.join(project_root, '.env'),           # 2순위: 루트/.env
    os.path.join(current_dir, '.env')              # 3순위: 현재 폴더/.env
]

env_loaded = False
for env_path in env_candidates:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"[Info] 환경변수 파일을 성공적으로 로드했습니다: {env_path}")
        env_loaded = True
        break

if not env_loaded:
    # 후보지에 없을 경우 시스템 환경변수 기본 로드 시도
    load_dotenv()
    print("[Warning] 지정된 경로에서 .env 파일을 찾지 못해 기본 환경변수 로드를 시도합니다.")


# ==========================================
# 🧠 2. Solar API 기반 정보 추출 핵심 함수
# ==========================================
def call_solar_api_for_extraction(extracted_text: str, schema_json: dict) -> dict:
    """
    Upstage Document Parse(OCR) 결과물에서 정의된 JSON 스키마 구조에 맞게
    핵심 정보와 팩트 체크용 근거 문장(Evidence)을 추출합니다.
    """
    # 환경변수 값 매핑
    api_key = os.getenv("UPSTAGE_API_KEY")
    solar_url = os.getenv("SOLAR_API_URL", "https://api.upstage.ai/v1/solar/chat/completions")
    
    # 💡 [보안 및 동기화 고정] 백엔드 지침에 따라 'solar-pro'를 기본값으로 지정합니다.
    solar_model = os.getenv("SOLAR_MODEL_NAME", "solar-pro")
    
    if not api_key:
        print("[Error] Upstage API Key가 환경변수(UPSTAGE_API_KEY)에 설정되지 않았습니다.", file=sys.stderr)
        return {}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 구조화된 고정 정보 추출을 위한 시스템 및 유저 통합 프롬프트 빌드
    prompt = f"""
    당신은 제공된 [문서 본문]에서 사용자가 지정한 [추출 스키마] 구조에 맞게 핵심 정보만을 엄격하게 골라내는 정보 추출(Information Extraction) 전문가입니다.

    [작동 규칙]
    1. 외부 지식이나 추측을 완전히 배제하고, 철저히 [문서 본문]에 적힌 텍스트만을 기반으로 스키마의 값을 채우세요.
    2. [추출 스키마]에 정의된 모든 Key를 포함한 JSON 객체 하나만 출력해야 합니다.
    3. 값을 추출할 때, 어떤 문장이나 단어를 보고 이 값을 도출했는지 매칭되는 원본 문장을 'evidence_text' 필드 등에 정확히 함께 기록해 주세요.

    [문서 본문]
    {extracted_text}

    [추출 스키마]
    {json.dumps(schema_json, ensure_ascii=False)}
    """
    
    payload = {
        "model": solar_model,  # 💡 .env에 등록된 'solar-pro'가 일관되게 주입됩니다.
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,    # 정보 추출의 정밀도와 팩트 유지를 위해 온도를 0으로 통제합니다.
        "response_format": {"type": "json_object"}  # 완벽한 JSON 출력을 보장하는 옵션
    }
    
    try:
        print(f"[API Call] Solar API 호출 중... 모델명: {solar_model}")
        response = requests.post(solar_url, headers=headers, json=payload, timeout=20)
        
        if response.status_code == 200:
            result_content = response.json()['choices'][0]['message']['content']
            # 정상적인 JSON 구조인지 파싱 검증 후 반환
            return json.loads(result_content)
        else:
            print(f"[API Error] Status Code: {response.status_code}, Response: {response.text}", file=sys.stderr)
            return {}
            
    except json.JSONDecodeError as jde:
        print(f"[Parsing Error] Solar 응답을 JSON 객체로 파싱하지 못했습니다: {str(jde)}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"[Connection Error] Solar API 호출 실패: {str(e)}", file=sys.stderr)
        return {}


# ==========================================
# 🚀 3. n8n CLI 실행 파이프라인 엔트리포인트
# ==========================================
if __name__ == "__main__":
    """
    n8n 워크플로우 파이프라인에서 인자를 받아 독립 실행할 수 있도록 지원하는 메인 로직입니다.
    예시: python extract_important_texts.py "<문서텍스트>" "<스키마JSON문자열>"
    """
    if len(sys.argv) < 3:
        # 테스트용 임시 모크 데이터 작동 가드
        sample_text = "컴퓨터네트워크 과제3 제출 안내. 마감일은 2026년 6월 20일 정보공학관 403호 제출."
        sample_schema = {"assignment_name": "과제명", "due_date": "마감일"}
        print("[Info] 인자가 입력되지 않아 테스트 모드로 실행합니다.")
        test_result = call_solar_api_for_extraction(sample_text, sample_schema)
        print("테스트 결과:", json.dumps(test_result, ensure_ascii=False, indent=2))
    else:
        # n8n으로부터 수신한 인자 파싱
        input_text = sys.argv[1]
        try:
            input_schema = json.loads(sys.argv[2])
            extracted_json = call_solar_api_for_extraction(input_text, input_schema)
            # n8n 표준 출력을 위해 JSON 한 줄로 프린트
            print(json.dumps(extracted_json, ensure_ascii=False))
        except Exception as ex:
            print(json.dumps({"status": "error", "message": f"파이프라인 구동 실패: {str(ex)}"}))