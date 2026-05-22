// =============================================
// SEARCH.JS
// 검색 관련 로직
// =============================================

// - 입력창 텍스트 읽기
// - 예시 칩 버튼 클릭 시 질문 자동 입력
// - Dev D search webhook으로 질문 전송
// - 응답 JSON을 card.js로 넘기기
// - no_answer 응답 처리


// =============================================
// 상수 정의
// =============================================

// Dev D에게 받은 search webhook URL로 교체
const SEARCH_WEBHOOK_URL = 'http://localhost:5678/webhook/odiduji/query';


// =============================================
// 검색 요청 전송
// =============================================

/**
 * 질문 텍스트를 search webhook으로 POST 전송
 * 응답 JSON을 card.js의 renderCards()로 넘김
 *
 * @param {string} query - 사용자 질문 텍스트
 */
async function sendSearchRequest(query) {
  if (!query || query.trim() === '') return;

  // 검색 시작 전 카드 초기화
  clearCards();

  // 로딩 상태 표시
  setSearchLoading(true);

  try {
    const response = await fetch(SEARCH_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw_query: query.trim() }),
    });

    if (!response.ok) {
      throw new Error(`서버 오류: ${response.status}`);
    }

    const data = await response.json();

    // card.js의 renderCards()로 응답 전달
    renderCards(data);

  } catch (error) {
    console.error('[search.js] 검색 요청 실패:', error);

    // 오류 시 no_answer 처리
    renderCards({ answer: 'no_answer' });

  } finally {
    // 로딩 상태 해제
    setSearchLoading(false);
  }
}


// =============================================
// 로딩 상태 처리
// =============================================

/**
 * 검색 버튼 로딩 상태 전환
 * @param {boolean} isLoading
 */
function setSearchLoading(isLoading) {
  const searchBtn   = document.getElementById('search-btn');
  const searchInput = document.getElementById('search-input');

  if (isLoading) {
    searchBtn.textContent = '검색 중...';
    searchBtn.disabled    = true;
    searchInput.disabled  = true;
  } else {
    searchBtn.textContent = '검색';
    searchBtn.disabled    = false;
    searchInput.disabled  = false;
  }
}


// =============================================
// 이벤트 등록 — 외부에서 호출하는 초기화 함수
// =============================================

/**
 * 검색 영역 이벤트 전체 등록
 * app.js의 init()에서 호출
 */
function initSearch() {
  const searchBtn   = document.getElementById('search-btn');
  const searchInput = document.getElementById('search-input');
  const chipGroup   = document.getElementById('chip-group');

  // 검색 버튼 클릭
  searchBtn.addEventListener('click', () => {
    const query = searchInput.value;
    sendSearchRequest(query);
  });

  // 입력창 엔터 키
  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const query = searchInput.value;
      sendSearchRequest(query);
    }
  });

  // 예시 칩 버튼 클릭 시 질문 자동 입력 후 검색
  chipGroup.addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;

    const query = chip.dataset.query;

    // 입력창에 질문 자동 입력
    searchInput.value = query;

    // 바로 검색 실행
    sendSearchRequest(query);
  });
}