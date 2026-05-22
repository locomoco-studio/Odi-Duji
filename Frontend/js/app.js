// =============================================
// APP.JS
// 전체 흐름을 연결하는 컨트롤타워
// =============================================

// - 페이지 로드 시 초기화
// - upload.js / search.js / card.js 연결
// - 각 단계 상태 관리
//   (idle → uploading → indexed → searching → result)


// =============================================
// 앱 상태 관리
// =============================================

/**
 * 앱 전체 상태
 *
 * idle       → 초기 상태, 아무것도 안 한 상태
 * uploading  → 파일 업로드 + 인덱싱 진행 중
 * indexed    → 인덱싱 완료, 검색 가능한 상태
 * searching  → 검색 요청 진행 중
 * result     → 검색 결과 표시 중
 */
const AppState = {
  current: 'idle',

  /**
   * 상태 전환
   * @param {'idle'|'uploading'|'indexed'|'searching'|'result'} next
   */
  set(next) {
    console.log(`[app.js] 상태 전환: ${this.current} → ${next}`);
    this.current = next;
    AppState.onStateChange(next);
  },

  /**
   * 상태 변경 시 UI 업데이트
   * @param {string} state
   */
  onStateChange(state) {
    const searchSection = document.getElementById('search-section');
    const resultSection = document.getElementById('result-section');

    switch (state) {

      // 초기 상태 — 검색 영역 / 결과 영역 숨김
      case 'idle':
        searchSection.style.display = 'none';
        resultSection.style.display = 'none';
        break;

      // 업로드 중 — 검색 영역 비활성화
      case 'uploading':
        searchSection.style.display = 'none';
        resultSection.style.display = 'none';
        break;

      // 인덱싱 완료 — 검색 영역 표시
      case 'indexed':
        searchSection.style.display = 'block';
        resultSection.style.display = 'none';
        break;

      // 검색 중 — 결과 영역 표시 (로딩 상태)
      case 'searching':
        resultSection.style.display = 'block';
        break;

      // 결과 표시
      case 'result':
        resultSection.style.display = 'block';
        break;
    }
  },
};


// =============================================
// upload.js 상태 연동
// =============================================

/**
 * upload.js의 setIndexStatus()를 감싸서
 * AppState도 함께 전환하는 래퍼 함수
 *
 * upload.js의 uploadFiles() 안에서
 * setIndexStatus() 호출 시 이 함수가 대신 실행됨
 */
const _originalSetIndexStatus = setIndexStatus;

window.setIndexStatus = function (status) {
  _originalSetIndexStatus(status);

  if (status === 'processing') AppState.set('uploading');
  if (status === 'indexed')    AppState.set('indexed');
  if (status === 'failed')     AppState.set('idle');
};


// =============================================
// search.js 상태 연동
// =============================================

/**
 * search.js의 setSearchLoading()을 감싸서
 * AppState도 함께 전환하는 래퍼 함수
 */
const _originalSetSearchLoading = setSearchLoading;

window.setSearchLoading = function (isLoading) {
  _originalSetSearchLoading(isLoading);

  if (isLoading)  AppState.set('searching');
  if (!isLoading) AppState.set('result');
};


// =============================================
// 페이지 초기화
// =============================================

/**
 * 페이지 로드 시 실행
 * upload.js / search.js 이벤트 등록
 * 초기 UI 상태 설정
 */
function init() {
  // 초기 상태: 검색 영역 / 결과 영역 숨김
  AppState.set('idle');

  // upload.js 이벤트 등록
  initUpload();

  // search.js 이벤트 등록
  initSearch();

  console.log('[app.js] 초기화 완료');
}

// DOM 로드 완료 후 init 실행
document.addEventListener('DOMContentLoaded', init);