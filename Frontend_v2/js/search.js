// =============================================
// SEARCH.JS — 검색 관련 로직
// =============================================

const SEARCH_WEBHOOK_URL = 'http://localhost:5678/webhook/odiduji/query';

// ── MOCK 데이터 ──
const MOCK_CANDIDATES = {
  '이번 주 마감 과제': [
    {
      doc_type:           'assignment',
      deadline:           '2026-05-23',
      submission:         'ERD 수정본, 보고서 PDF',
      evidence_text:      '제출 기한: 5월 23일 자정까지 LMS에 제출',
      confidence:         0.95,
      original_image_url: null,
    },
    {
      doc_type:           'assignment',
      deadline:           '2026-05-25',
      submission:         '발표 PPT',
      evidence_text:      '5월 25일 오전 9시까지 이메일 제출 요망',
      confidence:         0.88,
      original_image_url: null,
    },
    {
      doc_type:           'notice',
      deadline:           '2026-05-28',
      submission:         null,
      evidence_text:      '수강신청 정정 기간: 5월 28일까지',
      confidence:         0.72,
      original_image_url: null,
    },
  ],
  '2만 원 이상 영수증': [
    {
      doc_type:           'receipt',
      deadline:           null,
      submission:         null,
      evidence_text:      '결제금액: 23,500원 / 스타벅스 강남점 / 2026-05-10',
      confidence:         0.97,
      original_image_url: null,
    },
    {
      doc_type:           'receipt',
      deadline:           null,
      submission:         null,
      evidence_text:      '총 결제금액: 45,000원 / 교보문고 / 2026-05-08',
      confidence:         0.91,
      original_image_url: null,
    },
    {
      doc_type:           'receipt',
      deadline:           null,
      submission:         null,
      evidence_text:      '결제: 28,000원 / 올리브영 / 2026-05-05',
      confidence:         0.85,
      original_image_url: null,
    },
  ],
  '장학금 제출물': [
    {
      doc_type:           'scholarship',
      deadline:           '2026-05-30',
      submission:         '장학금 신청서, 성적증명서, 재학증명서',
      evidence_text:      '교내 장학금 신청 마감: 5월 30일 / 필요서류: 신청서·성적증명서·재학증명서',
      confidence:         0.93,
      original_image_url: null,
    },
    {
      doc_type:           'scholarship',
      deadline:           '2026-06-05',
      submission:         '자기소개서, 추천서',
      evidence_text:      '외부 장학재단 접수 기간: ~6월 5일 / 자기소개서 및 추천서 필수',
      confidence:         0.87,
      original_image_url: null,
    },
    {
      doc_type:           'notice',
      deadline:           '2026-05-31',
      submission:         '신청서',
      evidence_text:      '근로장학생 모집 마감 5월 31일, 학생처 방문 접수',
      confidence:         0.76,
      original_image_url: null,
    },
  ],
};

// 기본 Mock (질문이 위 키에 없을 때)
const DEFAULT_MOCK = [
  {
    doc_type:           'assignment',
    deadline:           '2026-05-24',
    submission:         '최종 보고서',
    evidence_text:      '5월 24일까지 팀 과제 최종본 제출',
    confidence:         0.90,
    original_image_url: null,
  },
  {
    doc_type:           'scholarship',
    deadline:           '2026-05-29',
    submission:         '신청서, 성적증명서',
    evidence_text:      '장학금 신청 마감: 5월 29일 오후 5시',
    confidence:         0.83,
    original_image_url: null,
  },
  {
    doc_type:           'receipt',
    deadline:           null,
    submission:         null,
    evidence_text:      '결제금액: 32,000원 / 2026-05-12',
    confidence:         0.78,
    original_image_url: null,
  },
];


async function sendSearchRequest(query) {
  if (!query || query.trim() === '') return;

  clearCards();
  setSearchLoading(true);

  try {
    // ── MOCK (테스트용, 실제 연동 시 아래 주석 해제하고 mock 삭제) ──
    await new Promise(r => setTimeout(r, 700));

    const candidates = MOCK_CANDIDATES[query.trim()] || DEFAULT_MOCK;
    renderCards({ candidates });

    // ── 실제 연동 시 아래 코드로 교체 ──
    // const res = await fetch(SEARCH_WEBHOOK_URL, {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({ raw_query: query.trim() }),
    // });
    // if (!res.ok) throw new Error(`서버 오류: ${res.status}`);
    // const data = await res.json();
    // renderCards(data);

  } catch (err) {
    console.error('[search.js]', err);
    renderCards({ answer: 'no_answer' });
  } finally {
    setSearchLoading(false);
  }
}

function setSearchLoading(isLoading) {
  const btn   = document.getElementById('search-btn');
  const input = document.getElementById('search-input');
  btn.textContent = isLoading ? '검색 중...' : '검색';
  btn.disabled    = isLoading;
  input.disabled  = isLoading;
}

function initSearch() {
  const btn       = document.getElementById('search-btn');
  const input     = document.getElementById('search-input');
  const chipGroup = document.getElementById('chip-group');

  btn.addEventListener('click', () => sendSearchRequest(input.value));

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendSearchRequest(input.value);
  });

  chipGroup.addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    input.value = chip.dataset.query;
    sendSearchRequest(chip.dataset.query);
  });
}
