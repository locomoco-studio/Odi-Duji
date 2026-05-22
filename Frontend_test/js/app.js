// =============================================
// APP.JS — 전체 흐름 컨트롤타워
// =============================================

// ── 이미지 확대 모달 (upload.js, card.js 공용) ──
function openModal(src) {
  const modal = document.getElementById('img-modal');
  const img   = document.getElementById('modal-img');
  img.src      = src;
  modal.hidden = false;
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('img-modal').hidden = true;
  document.getElementById('modal-img').src    = '';
  document.body.style.overflow = '';
}


// ── 탭 전환 ──
function initTabs() {
  const tabs   = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.tab-panel');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;

      tabs.forEach(t => t.classList.remove('tab-btn--active'));
      tab.classList.add('tab-btn--active');

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
// 인덱싱 완료 시 질문하기 탭이 열려 있어도 안내 메시지 즉시 숨김
const _originalSetIndexStatus = setIndexStatus;
window.setIndexStatus = function(status) {
  _originalSetIndexStatus(status);
  if (status === 'indexed') {
    const notice = document.getElementById('query-notice');
    if (notice) notice.hidden = true;
  }
};


// ── 초기화 ──
function init() {
  initTabs();
  initUpload();
  initSearch();

  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-backdrop').addEventListener('click', closeModal);

  console.log('[app.js] 초기화 완료');
}

document.addEventListener('DOMContentLoaded', init);
