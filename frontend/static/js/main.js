/* ===== EntryChecker main.js – 2025‑07‑15 ===== */

const rules = [
  { id: 'weekend_txn', name: '주말·공휴일 거래', type: 'boolean', enabled: false },
  { id: 'amount_over',     name: '금액 초과',       type: 'input',   value: 10000000, enabled: false },
  { id: 'keyword_search',  name: '특정 키워드',     type: 'input',   value: '가지급금,대여금', enabled: false },
  { id: 'wrong_tax_code',  name: '잘못된 TX코드',   type: 'boolean', enabled: false }
];

const fileInput       = document.getElementById('file-upload');
const runBtn          = document.getElementById('run-analysis');
const ruleList        = document.getElementById('rule-list');
const tableContainer  = document.getElementById('table-container');
const logContent      = document.getElementById('log-content');
const chkWholeVoucher = document.getElementById('chk-whole-voucher');
const loadingBadge    = document.getElementById('loading');

let dataHeaders = [];
let journalData = [];

/* ---------- 규칙 카드 렌더 ---------- */
function renderRules() {
  ruleList.innerHTML = '';
  rules.forEach((r, i) => {
    const card = document.createElement('div');
    card.className = `rule-card p-4 border rounded-lg cursor-pointer ${r.enabled ? 'active' : ''}`;
    card.onclick = () => { r.enabled = !r.enabled; renderRules(); };

    let html = `<h4 class="font-bold">${i + 1}. ${r.name}</h4>`;
    if (r.type === 'input') {
      html += `<input type="text" value="${r.value}" class="mt-2 w-full p-1 border rounded"
                 onclick="event.stopPropagation();"
                 oninput="rules[${i}].value=this.value">`;
    }
    card.innerHTML = html;
    ruleList.appendChild(card);
  });
}

/* ---------- 로그 ---------- */
function log(msg, type='info') {
  const p = document.createElement('p');
  p.textContent = '> ' + msg;
  if (type === 'error')   p.classList.add('text-red-400');
  if (type === 'success') p.classList.add('text-green-400');
  logContent.prepend(p);
}

/* ---------- 테이블 ---------- */
function renderTable(rows, highlightSet=new Set(), ruleMap={}) {
  if (!rows.length) {
    tableContainer.innerHTML = '<p class="text-gray-500">표시할 데이터가 없습니다.</p>';
    return;
  }

  const table = document.createElement('table');
  table.className = 'w-full text-sm text-left border';

  /* 헤더 */
  const thead = document.createElement('thead');
  thead.className = 'bg-gray-100';
  let headRow = '<tr><th class="p-2 border-b w-12">조건</th>';
  dataHeaders.forEach(h => headRow += `<th class="p-2 border-b">${h}</th>`);
  headRow += '</tr>';
  thead.innerHTML = headRow;
  table.appendChild(thead);

  /* 본문 */
  const tbody = document.createElement('tbody');
  rows.forEach((row, idx) => {
    const cond = (ruleMap[idx] || []).join(',');
    const hi   = highlightSet.has(idx) ? 'highlight' : '';
    let tr = `<tr class="border-b hover:bg-gray-50 ${hi}"><td class="p-2 text-center">${cond}</td>`;
    dataHeaders.forEach(col => tr += `<td class="p-2">${row[col] ?? ''}</td>`);
    tr += '</tr>';
    tbody.insertAdjacentHTML('beforeend', tr);
  });
  table.appendChild(tbody);

  tableContainer.innerHTML = '';
  tableContainer.appendChild(table);
}

/* ---------- 파일 선택 ---------- */
fileInput.addEventListener('change', async e => {
  const file = e.target.files[0];
  if (!file) return;

  log(`파일 선택: ${file.name}`, 'info');

  // 규칙 없이 백엔드 호출 → 미리보기와 Tx코드 생성
  await fetchAndRender(file, [], {});
});

/* ---------- 분석 실행 ---------- */
runBtn.addEventListener('click', async () => {
  const file = fileInput.files[0];
  if (!file) { log('파일을 먼저 선택하세요.', 'error'); return; }

  const active = rules.filter(r => r.enabled).map(r => r.id);
  const vals = {};
  rules.forEach(r => { if (r.enabled && r.type === 'input') vals[r.id] = r.value; });

  await fetchAndRender(file, active, vals);
});

/* ---------- 공통 fetch ---------- */
async function fetchAndRender(file, activeRules, ruleVals) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('active_rules', JSON.stringify(activeRules));
  fd.append('values', JSON.stringify(ruleVals));

  loadingBadge.classList.remove('hidden');
  try {
    const res = await fetch('/analyze', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    dataHeaders = data.headers;
    journalData = data.rows;

    /* 하이라이트 셋 만들기 */
    let hiSet = new Set(data.flagged_indices);
    if (chkWholeVoucher.checked && hiSet.size) {
      const vouchers = new Set([...hiSet].map(i => journalData[i]['전표번호']));
      journalData.forEach((r,i)=>{ if (vouchers.has(r['전표번호'])) hiSet.add(i); });
    }

    /* rule_map → key가 문자열이라 Number로 변환 */
    const rMap = {};
    for (const k in data.rule_map) rMap[+k] = data.rule_map[k];

    renderTable(journalData, hiSet, rMap);
    log(`분석 완료 – Tx코드 생성, ${[...hiSet].length}행 하이라이트`, 'success');
  } catch (e) {
    log('분석 오류: ' + e.message, 'error');
  } finally {
    loadingBadge.classList.add('hidden');
  }
}

/* 규칙 카드 초기화 */
renderRules();
