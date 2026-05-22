// UPLOAD.JS
// 업로드 관련 로직


// - 파일 선택 이벤트 처리
// - drag & drop 이벤트 처리
// - Dev D webhook으로 이미지 전송
// - 응답 받아서 상태 배지 업데이트
//   (처리중 → 완료 or 실패)




// =============================================
// UPLOAD.JS
// 업로드 관련 로직
// =============================================

// - 파일 선택 이벤트 처리
// - drag & drop 이벤트 처리
// - Dev D webhook으로 이미지 전송
// - 응답 받아서 상태 배지 업데이트
//   (처리중 → 완료 or 실패)


// =============================================
// 상수 정의
// =============================================

// Dev D에게 받은 upload webhook URL로 교체
const UPLOAD_WEBHOOK_URL = 'http://localhost:5678/webhook/odiduji/upload';

// 허용 파일 타입
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];

// 최대 파일 크기 (10MB)
const MAX_FILE_SIZE = 10 * 1024 * 1024;

// 최대 업로드 장수
const MAX_FILE_COUNT = 30;

// =============================================
// 상태 배지 업데이트
// =============================================

/**
 * 인덱싱 상태 배지 텍스트 + data-status 변경
 * CSS에서 data-status 값에 따라 색상 자동 전환
 *
 * @param {'idle'|'processing'|'indexed'|'failed'} status
 */
function setIndexStatus(status) {
  const indexStatus = document.getElementById('index-status');
  const statusText  = document.getElementById('status-text');

  const statusLabel = {
    idle:       '대기 중',
    processing: '분석 중...',
    indexed:    '인덱싱 완료',
    failed:     '처리 실패',
  };

  indexStatus.dataset.status = status;
  statusText.textContent     = statusLabel[status] || '대기 중';
}


// =============================================
// 파일 유효성 검사
// =============================================

/**
 * 파일 타입 / 크기 검사
 * @param {File} file
 * @returns {{ valid: boolean, reason: string }}
 */
function validateFile(file) {
  if (!ALLOWED_TYPES.includes(file.type)) {
    return { valid: false, reason: '이미지 파일만 업로드할 수 있어요 (JPG, PNG, WEBP)' };
  }
  if (file.size > MAX_FILE_SIZE) {
    return { valid: false, reason: '파일 크기는 10MB 이하만 가능해요' };
  }
  return { valid: true, reason: '' };
}


// =============================================
// 파일 목록 UI 업데이트
// =============================================

/**
 * 업로드된 파일 이름을 파일 목록에 추가
 * @param {File} file
 */
function addFileListItem(file) {
  const fileList = document.getElementById('file-list');
  const li       = document.createElement('li');
  li.className   = 'file-list__item';
  li.textContent = file.name;
  fileList.appendChild(li);
}

/**
 * 파일 목록 초기화
 */
function clearFileList() {
  document.getElementById('file-list').innerHTML = '';
}


// =============================================
// 파일 업로드 전송
// =============================================

/**
 * 파일 배열을 순서대로 upload webhook으로 전송
 * @param {File[]} files
 */
async function uploadFiles(files) {
  if (!files || files.length === 0) return;

  // 최대 30장 제한
  if (files.length > MAX_FILE_COUNT) {
    alert(`한 번에 최대 ${MAX_FILE_COUNT}장까지 업로드할 수 있어요.\n현재 선택: ${files.length}장`);
    return;
  }

  clearFileList();
  setIndexStatus('processing');

  let hasError = false;

  for (const file of files) {

    // 유효성 검사
    const { valid, reason } = validateFile(file);
    if (!valid) {
      console.warn(`[upload.js] 파일 거부: ${file.name} — ${reason}`);
      alert(`${file.name}\n${reason}`);
      hasError = true;
      continue;
    }

    // 파일 목록 UI에 추가
    addFileListItem(file);

    // FormData로 감싸서 webhook에 POST
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(UPLOAD_WEBHOOK_URL, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`서버 오류: ${response.status}`);
      }

    } catch (error) {
      console.error(`[upload.js] 업로드 실패: ${file.name}`, error);
      hasError = true;
    }
  }

  // 전송 완료 후 배지 업데이트
  setIndexStatus(hasError ? 'failed' : 'indexed');
}


// =============================================
// 이벤트 등록 — 외부에서 호출하는 초기화 함수
// =============================================

/**
 * 업로드 영역 이벤트 전체 등록
 * app.js의 init()에서 호출
 */
function initUpload() {
  const dropZone  = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');

  // ── 파일 선택 버튼 ──
  fileInput.addEventListener('change', (e) => {
    const files = Array.from(e.target.files);
    uploadFiles(files);

    // 같은 파일 재업로드 가능하도록 input 초기화
    e.target.value = '';
  });

  // drop-zone 클릭 시 파일 선택창 열기
  dropZone.addEventListener('click', (e) => {
    // label 클릭은 이미 input과 연결되어 있으므로 중복 방지
    if (e.target.tagName === 'LABEL' || e.target.tagName === 'INPUT') return;
    fileInput.click();
  });


  // ── drag & drop ──

  // 드래그가 drop-zone 위에 올라왔을 때
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });

  // 드래그가 drop-zone을 벗어났을 때
  dropZone.addEventListener('dragleave', (e) => {
    // 자식 요소로 이동하는 경우 제외
    if (dropZone.contains(e.relatedTarget)) return;
    dropZone.classList.remove('drag-over');
  });

  // 파일을 drop-zone에 놓았을 때
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');

    const files = Array.from(e.dataTransfer.files);
    uploadFiles(files);
  });
}