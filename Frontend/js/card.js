// =============================================
// CARD.JS
// 결과 카드 그리기 관련 로직
// =============================================

// - Top-3 candidate JSON 받아서 카드 3개 생성
// - 각 카드에 표시할 것들
//   · doc_type 아이콘 (📋과제 / 🧾영수증 / 🎓장학금)
//   · deadline → D-day 계산해서 표시
//   · submission 내용
//   · evidence_text 하이라이트
//   · confidence 0.8 미만이면 "확인 필요" 배지
//   · original_image_url → "원본 보기" 버튼
// - no_answer일 때 안내 메시지 표시


// =============================================
// 상수 정의
// =============================================

// doc_type별 아이콘 매핑
const DOC_TYPE_ICON = {
  assignment:  '📋',
  receipt:     '🧾',
  scholarship: '🎓',
  notice:      '📢',
};

// doc_type별 한글 라벨 매핑
const DOC_TYPE_LABEL = {
  assignment:  '과제',
  receipt:     '영수증',
  scholarship: '장학금',
  notice:      '공지',
};

// confidence 임계값 — 이 미만이면 "확인 필요" 배지 표시
const CONFIDENCE_THRESHOLD = 0.8;

// D-day 긴급도 기준 (단위: 일)
const DDAY_URGENT = 2;  // D-2 이하 → 빨강
const DDAY_SOON   = 7;  // D-3 ~ D-7 → 주황


// =============================================
// D-day 계산
// =============================================

/**
 * deadline 날짜 문자열(YYYY-MM-DD)을 받아서 D-day 숫자를 반환
 * @param {string|null} deadlineStr
 * @returns {number|null} - 오늘 기준 남은 일수 (음수면 지난 것)
 */
function calcDday(deadlineStr) {
  if (!deadlineStr) return null;

  const today    = new Date();
  today.setHours(0, 0, 0, 0);

  const deadline = new Date(deadlineStr);
  deadline.setHours(0, 0, 0, 0);

  const diffMs   = deadline - today;
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  return diffDays;
}

/**
 * D-day 숫자를 텍스트로 변환
 * @param {number|null} days
 * @returns {string}
 */
function formatDday(days) {
  if (days === null)  return '날짜 미상';
  if (days === 0)     return 'D-DAY';
  if (days > 0)       return `D-${days}`;
  return `D+${Math.abs(days)}`;  // 마감 지난 경우
}

/**
 * D-day 숫자에 따라 CSS 클래스 반환
 * @param {number|null} days
 * @returns {string}
 */
function getDdayClass(days) {
  if (days === null || days < 0) return 'dday--urgent';
  if (days <= DDAY_URGENT)       return 'dday--urgent';
  if (days <= DDAY_SOON)         return 'dday--soon';
  return 'dday--normal';
}


// =============================================
// 카드 HTML 생성
// =============================================

/**
 * candidate 객체 하나를 받아서 카드 HTML 문자열 반환
 * @param {Object} candidate
 * @returns {string} HTML string
 */
function createCardHTML(candidate) {
  const {
    rank,
    doc_type,
    deadline,
    submission,
    evidence_text,
    confidence,
    original_image_url,
  } = candidate;

  // doc_type 아이콘 / 라벨
  const icon  = DOC_TYPE_ICON[doc_type]  || '📄';
  const label = DOC_TYPE_LABEL[doc_type] || doc_type;

  // D-day 계산
  const ddayNum   = calcDday(deadline);
  const ddayText  = formatDday(ddayNum);
  const ddayClass = getDdayClass(ddayNum);

  // 마감일 표시 텍스트
  const deadlineText = deadline
    ? `${deadline} (${ddayText})`
    : '마감일 정보 없음';

  // 제출물 표시 텍스트
  const submissionText = submission || '정보 없음';

  // confidence 낮을 때 "확인 필요" 배지
  const warningBadge = (confidence !== undefined && confidence < CONFIDENCE_THRESHOLD)
    ? `<span class="badge-warning">확인 필요</span>`
    : '';

  // evidence_text 하이라이트
  const evidenceHTML = evidence_text
    ? `<div class="result-card__evidence">${evidence_text}</div>`
    : '';

  // 원본 보기 버튼
  const originalBtn = original_image_url
    ? `<a class="btn--original" href="${original_image_url}" target="_blank" rel="noopener">
         🖼️ 원본 보기
       </a>`
    : '';

  return `
    <div class="result-card" data-rank="${rank}" data-doc-type="${doc_type}">

      <!-- 카드 상단: 아이콘 + 제목 + D-day -->
      <div class="result-card__header">
        <div class="result-card__title-row">
          <span class="result-card__icon">${icon}</span>
          <span class="result-card__title">${label}</span>
        </div>
        <span class="dday ${ddayClass}">${ddayText}</span>
      </div>

      <!-- 카드 본문 필드 -->
      <div class="result-card__body">
        <div class="result-card__field">
          <span class="result-card__field-label">마감</span>
          <span class="result-card__field-value">${deadlineText}</span>
        </div>
        <div class="result-card__field">
          <span class="result-card__field-label">제출물</span>
          <span class="result-card__field-value">${submissionText}</span>
        </div>
      </div>

      <!-- evidence_text 하이라이트 -->
      ${evidenceHTML}

      <!-- 카드 하단: 확인 필요 배지 + 원본 보기 버튼 -->
      <div class="result-card__footer">
        ${warningBadge}
        ${originalBtn}
      </div>

    </div>
  `;
}


// =============================================
// 응답 정규화
// =============================================
 
/**
 * 워크플로우 응답을 Dev C 설계 구조로 정규화
 * Build_Result_Cards → cards / Build_No_Answer → status 필드명 대응
 *
 * @param {Object} raw - 워크플로우 원본 응답
 * @returns {Object} - 정규화된 응답
 */
function normalizeResponse(raw) {
  if (!raw) return { answer: 'no_answer', reason: 'no_result' };
 
  // no_answer 처리
  // 워크플로우: { status: 'no_answer', ... }
  // 설계:      { answer: 'no_answer', ... }
  if (raw.status === 'no_answer' || raw.answer === 'no_answer') {
    return {
      answer:     'no_answer',
      reason:     raw.reason     || 'no_result',
      suggestion: raw.suggestion || '날짜 범위를 늘려보세요',
    };
  }
 
  // 정상 응답 처리
  // 워크플로우: { status: 'success', cards: [...] }
  // 설계:      { candidates: [...] }
  const candidates = raw.candidates || raw.cards || [];
 
  if (candidates.length === 0) {
    return { answer: 'no_answer', reason: 'no_result' };
  }
 
  return { candidates };
}


// =============================================
// 카드 렌더링 — 외부에서 호출하는 메인 함수
// =============================================

/**
 * Top-3 candidate 배열을 받아서 카드 목록을 화면에 렌더링
 * search.js에서 API 응답을 받은 후 이 함수를 호출
 *
 * @param {Object} response - API 응답 JSON (워크플로우 원본)
 */
function renderCards(response) {
  const cardList = document.getElementById('card-list');
  const noAnswer = document.getElementById('no-answer');
 
  // 렌더링 전 초기화
  cardList.innerHTML = '';
  noAnswer.hidden    = true;
 
  // 응답 정규화 (워크플로우 구조 → Dev C 설계 구조)
  const normalized = normalizeResponse(response);
 
  // no_answer 처리
  if (normalized.answer === 'no_answer') {
    noAnswer.hidden = false;
    return;
  }
 
  // 카드 생성 및 삽입
  normalized.candidates.forEach((candidate) => {
    cardList.insertAdjacentHTML('beforeend', createCardHTML(candidate));
  });
}


// =============================================
// 카드 초기화 — 검색 전 빈 상태로 되돌릴 때 사용
// =============================================

function clearCards() {
  const cardList = document.getElementById('card-list');
  const noAnswer = document.getElementById('no-answer');
  cardList.innerHTML = '';
  noAnswer.hidden    = true;
}