// =============================================
// SEARCH.JS — 검색 관련 로직
// =============================================

const SEARCH_WEBHOOK_URL = 'http://localhost:5678/webhook/odiduji/query';

async function sendSearchRequest(query) {
  if (!query || query.trim() === '') return;

  clearCards();
  setSearchLoading(true);

  try {
    const res = await fetch(SEARCH_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw_query: query.trim() }),
    });

    if (!res.ok) throw new Error(`서버 오류: ${res.status}`);
    const data = await res.json();

    // 워크플로우 에러 응답 (status:'error') 구분
    if (data?.status === 'error') {
      console.error('[search.js] 워크플로우 에러:', data.error_code, data.message);
      renderCards({ answer: 'no_answer', reason: data.error_code });
      return;
    }

    renderCards(data);

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