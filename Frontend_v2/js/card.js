// =============================================
// CARD.JS — 결과 카드 그리기
// =============================================

const DOC_TYPE_ICON = {
  assignment:  '📋',
  receipt:     '🧾',
  scholarship: '🎓',
  notice:      '📢',
  place:       '📍',
};

const DOC_TYPE_LABEL = {
  assignment:  '과제',
  receipt:     '영수증',
  scholarship: '장학금',
  notice:      '학사 공지',
  place:       '장소',
};

const CONFIDENCE_THRESHOLD = 0.8;
const DDAY_URGENT = 2;
const DDAY_SOON   = 7;


function calcDday(str) {
  if (!str) return null;
  const today    = new Date(); today.setHours(0,0,0,0);
  const deadline = new Date(str); deadline.setHours(0,0,0,0);
  return Math.ceil((deadline - today) / 86400000);
}

function formatDday(d) {
  if (d === null) return '날짜 미상';
  if (d === 0)    return 'D-DAY';
  if (d > 0)      return `D-${d}`;
  return `D+${Math.abs(d)}`;
}

function getDdayClass(d) {
  if (d === null || d < 0)  return 'dday--urgent';
  if (d <= DDAY_URGENT)     return 'dday--urgent';
  if (d <= DDAY_SOON)       return 'dday--soon';
  return 'dday--normal';
}


function createCardHTML(candidate, rank) {
  const { doc_type, deadline, submission, evidence_text, confidence, original_image_url } = candidate;

  const icon  = DOC_TYPE_ICON[doc_type]  || '📄';
  const label = DOC_TYPE_LABEL[doc_type] || doc_type;

  const ddayNum   = calcDday(deadline);
  const ddayText  = formatDday(ddayNum);
  const ddayClass = getDdayClass(ddayNum);

  const deadlineText   = deadline    ? `${deadline} (${ddayText})` : '마감일 정보 없음';
  const submissionText = submission  || '정보 없음';

  const warningBadge = (confidence !== undefined && confidence < CONFIDENCE_THRESHOLD)
    ? `<div class="badge-warning">⚠️ 확인 필요</div>` : '';

  const evidenceHTML = evidence_text
    ? `<div class="result-card__evidence">${evidence_text}</div>` : '';

  // 썸네일: original_image_url 있으면 이미지, 없으면 플레이스홀더
  const thumbInner = original_image_url
    ? `<img class="result-card__thumb-img" src="${original_image_url}" alt="원본"
            onclick="openModal('${original_image_url}')" />
       <span class="result-card__thumb-zoom">🔍</span>`
    : `<div class="result-card__thumb-placeholder">${icon}</div>`;

  return `
    <div class="result-card" data-rank="${rank}">
      <!-- 왼쪽: 원본 이미지 썸네일 -->
      <div class="result-card__thumb">${thumbInner}</div>

      <!-- 오른쪽: 내용 -->
      <div class="result-card__body">
        <div class="result-card__top">
          <div class="result-card__type">
            <span class="result-card__type-icon">${icon}</span>
            <span>${label}</span>
          </div>
          <span class="dday ${ddayClass}">${ddayText}</span>
        </div>

        <div class="result-card__field">
          <span class="result-card__field-label">마감</span>
          <span class="result-card__field-value">${deadlineText}</span>
        </div>

        <div class="result-card__field">
          <span class="result-card__field-label">제출물</span>
          <span class="result-card__field-value">${submissionText}</span>
        </div>

        ${evidenceHTML}
        ${warningBadge}
      </div>
    </div>
  `;
}


// 응답 정규화
function normalizeResponse(raw) {
  if (!raw) return { answer: 'no_answer', reason: 'no_result' };

  if (raw.status === 'no_answer' || raw.answer === 'no_answer') {
    return {
      answer:     'no_answer',
      reason:     raw.reason     || 'no_result',
      suggestion: raw.suggestion || '날짜 범위를 늘려보세요',
    };
  }

  // confidence 높은 순 정렬
  const candidates = (raw.candidates || raw.cards || [])
    .sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
    .slice(0, 3);

  if (candidates.length === 0) return { answer: 'no_answer', reason: 'no_result' };
  return { candidates };
}


// 카드 렌더링 (외부 호출)
function renderCards(response) {
  const cardList = document.getElementById('card-list');
  const noAnswer = document.getElementById('no-answer');
  const notice   = document.getElementById('query-notice');

  cardList.innerHTML = '';
  noAnswer.hidden    = true;
  if (notice) notice.hidden = true;

  const normalized = normalizeResponse(response);

  if (normalized.answer === 'no_answer') {
    noAnswer.hidden = false;
    return;
  }

  normalized.candidates.forEach((c, i) => {
    cardList.insertAdjacentHTML('beforeend', createCardHTML(c, i + 1));
  });
}


function clearCards() {
  const cardList = document.getElementById('card-list');
  const noAnswer = document.getElementById('no-answer');
  cardList.innerHTML = '';
  noAnswer.hidden    = true;
}
