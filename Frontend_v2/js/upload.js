// =============================================
// UPLOAD.JS — 업로드 관련 로직
// =============================================

const UPLOAD_WEBHOOK_URL = 'http://localhost:5678/webhook/odiduji/upload';
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
const MAX_FILE_SIZE = 10 * 1024 * 1024;
const MAX_FILE_COUNT = 30;

// doc_type 배지 라벨
const DOC_TYPE_BADGE = {
  assignment:  '과제',
  notice:      '학사 공지',
  scholarship: '장학금',
  receipt:     '영수증',
  place:       '장소',
};

// 에러 사유 배지 라벨
const ERROR_BADGE = {
  upload_failed:   '업로드 실패',
  classify_failed: '분류 실패',
  extract_failed:  '추출 실패',
  low_confidence:  '확인 필요',
  invalid_file:    '파일 오류',
};

// 성공 아이템 Map: capture_id → { li, file, dataUrl }
const successItems = new Map();


// ── 상태 배지 ──
function setIndexStatus(status) {
  const el   = document.getElementById('index-status');
  const text = document.getElementById('status-text');
  const labels = {
    idle:       '대기 중',
    processing: '분석 중...',
    indexed:    '인덱싱 완료',
    failed:     '처리 실패',
  };
  el.dataset.status  = status;
  text.textContent   = labels[status] || '대기 중';
}


// ── 섹션 표시/숨김 ──
function updateSections() {
  const successSection = document.getElementById('success-section');
  const failSection    = document.getElementById('fail-section');
  const successGrid    = document.getElementById('success-grid');
  const failGrid       = document.getElementById('fail-grid');

  successSection.hidden = successGrid.children.length === 0;
  failSection.hidden    = failGrid.children.length === 0;
}


// ── 성공 썸네일 추가 ──
function addSuccessThumb(file, dataUrl, docType, captureId) {
  const grid = document.getElementById('success-grid');

  const li = document.createElement('li');
  li.className = 'thumb-item';
  li.dataset.captureId = captureId;

  // 썸네일 이미지 (클릭 시 모달)
  const img = document.createElement('img');
  img.className = 'thumb-item__img';
  img.src = dataUrl;
  img.alt = file.name;
  img.addEventListener('click', () => openModal(dataUrl));

  // doc_type 배지 (왼쪽 상단)
  const typeBadge = document.createElement('span');
  typeBadge.className = 'thumb-item__type-badge';
  typeBadge.textContent = DOC_TYPE_BADGE[docType] || docType;

  // X 삭제 버튼 (오른쪽 상단)
  const removeBtn = document.createElement('button');
  removeBtn.className = 'thumb-item__remove';
  removeBtn.textContent = '✕';
  removeBtn.setAttribute('aria-label', '삭제');
  removeBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    li.remove();
    successItems.delete(captureId);
    updateSections();
  });

  li.appendChild(img);
  li.appendChild(typeBadge);
  li.appendChild(removeBtn);
  grid.appendChild(li);

  successItems.set(captureId, { li, file, dataUrl });
  updateSections();
}


// ── 실패 썸네일 추가 ──
function addFailThumb(file, dataUrl, errorType) {
  const grid = document.getElementById('fail-grid');

  const li = document.createElement('li');
  li.className = 'thumb-item';

  const img = document.createElement('img');
  img.className = 'thumb-item__img';
  img.src = dataUrl;
  img.alt = file.name;

  // 에러 배지 (오른쪽 상단)
  const errBadge = document.createElement('span');
  errBadge.className = 'thumb-item__err-badge';
  errBadge.textContent = ERROR_BADGE[errorType] || '처리 실패';

  li.appendChild(img);
  li.appendChild(errBadge);
  grid.appendChild(li);

  updateSections();
  return li;
}


// ── 실패 그리드 초기화 (새 업로드 시) ──
function clearFailGrid() {
  document.getElementById('fail-grid').innerHTML = '';
  updateSections();
}


// ── 파일 유효성 검사 ──
function validateFile(file) {
  if (!ALLOWED_TYPES.includes(file.type))
    return { valid: false, reason: 'invalid_file' };
  if (file.size > MAX_FILE_SIZE)
    return { valid: false, reason: 'invalid_file' };
  return { valid: true, reason: '' };
}


// ── FileReader → dataUrl ──
function readAsDataUrl(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.readAsDataURL(file);
  });
}


// ── 파일 업로드 메인 ──
async function uploadFiles(files) {
  if (!files || files.length === 0) return;

  if (files.length > MAX_FILE_COUNT) {
    alert(`한 번에 최대 ${MAX_FILE_COUNT}장까지 업로드할 수 있어요.\n현재 선택: ${files.length}장`);
    return;
  }

  // 새 업로드 시 실패 그리드만 초기화 (성공은 유지)
  clearFailGrid();
  setIndexStatus('processing');

  let hasError = false;

  for (const file of files) {
    const { valid, reason } = validateFile(file);
    const dataUrl = await readAsDataUrl(file);

    if (!valid) {
      addFailThumb(file, dataUrl, reason);
      hasError = true;
      continue;
    }

    try {
      const formData = new FormData();
      formData.append('file', file);

      // ── MOCK (테스트용, 실제 연동 시 아래 주석 해제하고 mock 삭제) ──
      await new Promise(r => setTimeout(r, 800));

      // 파일마다 doc_type 순환, 3개 중 1개는 실패로 분기
      const docTypes = ['assignment', 'notice', 'scholarship', 'receipt', 'place'];
      const errTypes = ['upload_failed', 'classify_failed', 'extract_failed'];
      const totalCount = successItems.size + document.getElementById('fail-grid').children.length;
      const isFail = totalCount % 3 === 2;

      if (isFail) {
        throw new Error(errTypes[totalCount % errTypes.length]);
      }

      const data = {
        doc_type:   docTypes[totalCount % docTypes.length],
        capture_id: `img_${Date.now()}`,
      };

      // ── 실제 연동 시 아래 코드로 교체 ──
      // const res = await fetch(UPLOAD_WEBHOOK_URL, {
      //   method: 'POST',
      //   body: formData,
      // });
      // if (!res.ok) throw new Error('upload_failed');
      // const data = await res.json();

      // 워크플로우 응답에서 doc_type, capture_id 파싱
      const docType   = data?.doc_type   || data?.capture_record?.doc_type   || 'notice';
      const captureId = data?.capture_id || data?.capture_record?.capture_id || `img_${Date.now()}`;

      addSuccessThumb(file, dataUrl, docType, captureId);

    } catch (err) {
      console.error('[upload.js]', err);
      const errType = err.message === 'classify_failed' ? 'classify_failed'
                    : err.message === 'extract_failed'  ? 'extract_failed'
                    : 'upload_failed';
      addFailThumb(file, dataUrl, errType);
      hasError = true;
    }
  }

  setIndexStatus(hasError && successItems.size === 0 ? 'failed' : 'indexed');
}


// ── 이미지 확대 모달 ──
function openModal(src) {
  const modal = document.getElementById('img-modal');
  const img   = document.getElementById('modal-img');
  img.src     = src;
  modal.hidden = false;
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('img-modal').hidden = true;
  document.getElementById('modal-img').src    = '';
  document.body.style.overflow = '';
}


// ── 초기화 ──
function initUpload() {
  const dropZone  = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');

  fileInput.addEventListener('change', (e) => {
    uploadFiles(Array.from(e.target.files));
    e.target.value = '';
  });

  dropZone.addEventListener('click', (e) => {
    if (e.target.tagName === 'LABEL' || e.target.tagName === 'INPUT') return;
    fileInput.click();
  });

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });

  dropZone.addEventListener('dragleave', (e) => {
    if (dropZone.contains(e.relatedTarget)) return;
    dropZone.classList.remove('drag-over');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    uploadFiles(Array.from(e.dataTransfer.files));
  });

  // 모달 닫기
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-backdrop').addEventListener('click', closeModal);
}
