// =============================================
// APP.JS — 전체 흐름 컨트롤타워
// =============================================

// ── 탭 전환 ──
function initTabs() {
  const tabs   = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.tab-panel');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;

      // 탭 활성화
      tabs.forEach(t => t.classList.remove('tab-btn--active'));
      tab.classList.add('tab-btn--active');

      // 패널 전환
      panels.forEach(p => {
        if (p.id === `panel-${target}`) {
          p.classList.remove('tab-panel--hidden');
        } else {
          p.classList.add('tab-panel--hidden');
        }
      });

      // 질문하기 탭 진입 시 업로드 상태 반영
      if (target === 'query') {
        const notice  = document.getElementById('query-notice');
        const indexed = document.getElementById('index-status').dataset.status === 'indexed';
        if (notice) notice.hidden = indexed;
      }
    });
  });
}


// ── upload.js 상태 연동 ──
const _originalSetIndexStatus = setIndexStatus;

window.setIndexStatus = function(status) {
  _originalSetIndexStatus(status);
};


// ── search.js 상태 연동 ──
const _originalSetSearchLoading = setSearchLoading;

window.setSearchLoading = function(isLoading) {
  _originalSetSearchLoading(isLoading);
};


// ── 초기화 ──
function init() {
  initTabs();
  initUpload();
  initSearch();
  console.log('[app.js] 초기화 완료');
}

document.addEventListener('DOMContentLoaded', init);
