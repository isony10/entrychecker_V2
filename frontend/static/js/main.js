/* ===== EntryChecker main.js – 2025-07-26 (Final Integrated Version) ===== */

let logicTree = { id: 0, type: 'group', op: 'AND', items: [] };
let nextId = 1;
const ruleTitles = {
  weekend_txn: '주말·공휴일 거래', amount_over: '금액 조건', keyword_search: '특정 키워드',
  party_freq: '거래처별 거래 횟수', round_million: '백만단위 이하 0',
  uniform_account: '동일 계정 전표세트', unbalanced_set: '차/대변 불일치 세트'
};

let dataHeaders = [], journalData = [], originalJournalData = [], lastRuleMap = {};

const $file = document.getElementById('file-upload');
const $fileName = document.getElementById('file-name');
const $runAnalysis = document.getElementById('run-analysis');
const $runAiVoucherAnalysis = document.getElementById('run-ai-voucher-analysis');
const $logicTree = document.getElementById('logic-tree');
const $log = document.getElementById('log-content');
const $tableContainer = document.getElementById('table-container');
const $aiVoucherResultsContainer = document.getElementById('ai-voucher-results-container');
const $tableWrap = $tableContainer;
const $aiVoucherResults = $aiVoucherResultsContainer;
const $chkSet = document.getElementById('chk-whole-voucher');
const $chkOnly = document.getElementById('chk-show-matching-only');
const $loading = document.getElementById('loading');
const $modal = document.getElementById('ai-modal');
const $modalBody = document.getElementById('modal-body');
const $closeModalBtn = document.getElementById('close-modal-btn');

function newGroup() { return { id: nextId++, type: 'group', op: 'AND', items: [] }; }
function newCond(rule) {
  const cond = { id: nextId++, type: 'cond', rule };
  if (rule === 'amount_over') { cond.op = '>'; cond.value = 0; cond.target = 'debit'; }
  else if (rule === 'party_freq') { cond.op = '>='; cond.value = 0; }
  else if (rule === 'keyword_search') { cond.value = ''; cond.mode = 'include'; }
  return cond;
}

function renderTree() {
  $logicTree.innerHTML = '';
  $logicTree.appendChild(renderGroup(logicTree));
}

function renderGroup(g) {
  const wrap = document.createElement('div');
  wrap.className = 'border p-2 rounded bg-gray-50';
  wrap.dataset.groupId = g.id;
  const header = document.createElement('div');
  header.className = 'flex items-center gap-2 mb-1';
  if (g !== logicTree) {
    const handle = Object.assign(document.createElement('span'), { textContent: '\u2630', className: 'cursor-move select-none text-gray-400' });
    header.appendChild(handle);
  }
  const sel = document.createElement('select');
  sel.className = 'font-bold text-sm border-gray-300 rounded';
  ['AND', 'OR'].forEach(op => { const o = document.createElement('option'); o.value = op; o.textContent = op; if (g.op === op) o.selected = true; sel.appendChild(o); });
  sel.onchange = () => { g.op = sel.value; };
  header.appendChild(sel);
  if (g !== logicTree) {
    const del = document.createElement('button');
    del.innerHTML = '<i class="fas fa-trash-alt"></i>';
    del.className = 'text-xs text-red-500 hover:text-red-700 ml-auto';
    del.onclick = () => { deleteItem(logicTree, g.id); renderTree(); };
    header.appendChild(del);
  }
  wrap.appendChild(header);
  const items = document.createElement('div');
  items.className = 'pl-4 space-y-1';
  items.dataset.groupId = g.id;
  g.items.forEach(it => items.appendChild(renderItem(it)));
  wrap.appendChild(items);
  new Sortable(items, { group: 'nested', animation: 150, filter: 'input,select,textarea', preventOnFilter: false, onEnd: evt => {
    const from = findGroupById(logicTree, parseInt(evt.from.dataset.groupId));
    const to = findGroupById(logicTree, parseInt(evt.to.dataset.groupId));
    const [moved] = from.items.splice(evt.oldIndex, 1);
    to.items.splice(evt.newIndex, 0, moved);
  }});
  return wrap;
}

function renderItem(item) {
  if (item.type === 'group') return renderGroup(item);
  const d = document.createElement('div');
  d.className = 'border rounded px-2 py-1 flex items-center gap-2 bg-white';
  d.dataset.itemId = item.id;
  const handle = Object.assign(document.createElement('span'), { textContent: '\u2630', className: 'cursor-move select-none text-gray-400' });
  d.appendChild(handle);
  const label = Object.assign(document.createElement('span'), { textContent: ruleTitles[item.rule] || item.rule, className: 'text-sm flex-grow' });
  d.appendChild(label);
  if (item.rule === 'amount_over' || item.rule === 'party_freq') {
    const sel = document.createElement('select'); sel.className = 'border rounded px-1 py-0.5 text-xs';
    ['>', '>=', '==', '<=', '<'].forEach(op => { const o = document.createElement('option'); o.value = op; o.textContent = op; if (item.op === op) o.selected = true; sel.appendChild(o); });
    sel.onchange = () => { item.op = sel.value; };
    const inp = document.createElement('input'); inp.type = 'number'; inp.className = 'border rounded w-20 px-1 py-0.5 text-xs'; inp.value = item.value; inp.oninput = () => { item.value = parseFloat(inp.value || 0); };
    if (item.rule === 'amount_over') {
        const dcSel = document.createElement('select'); dcSel.className = 'border rounded px-1 py-0.5 text-xs';
        [['debit', '차변'], ['credit', '대변']].forEach(([v, t]) => { const o = document.createElement('option'); o.value = v; o.textContent = t; if (item.target === v) o.selected = true; dcSel.appendChild(o); });
        dcSel.onchange = () => { item.target = dcSel.value; };
        d.appendChild(dcSel);
    }
    d.appendChild(sel); d.appendChild(inp);
  } else if (item.rule === 'keyword_search') {
    const modeSel = document.createElement('select'); modeSel.className = 'border rounded px-1 py-0.5 text-xs';
    [['include', '포함'], ['exclude', '제외']].forEach(([v, t]) => { const o = document.createElement('option'); o.value = v; o.textContent = t; if (item.mode === v) o.selected = true; modeSel.appendChild(o); });
    modeSel.onchange = () => { item.mode = modeSel.value; };
    const inp = document.createElement('input'); inp.type = 'text'; inp.className = 'border rounded w-28 px-1 py-0.5 text-xs'; inp.value = item.value || ''; inp.oninput = () => { item.value = inp.value; };
    d.appendChild(modeSel); d.appendChild(inp);
  }
  const del = document.createElement('button'); del.innerHTML = '<i class="fas fa-trash-alt"></i>'; del.className = 'text-xs text-red-500 hover:text-red-700 ml-2'; del.onclick = () => { deleteItem(logicTree, item.id); renderTree(); };
  d.appendChild(del);
  return d;
}

function findGroupById(tree, id) { if (tree.id === id) return tree; for (const it of tree.items) { if (it.type === 'group') { const r = findGroupById(it, id); if (r) return r; } } return null; }
function deleteItem(tree, id) { tree.items = tree.items.filter(it => { if (it.id === id) return false; if (it.type === 'group') deleteItem(it, id); return true; }); }
function collectRuleIds(tree, set = new Set()) { for (const it of tree.items) { if (it.type === 'cond') set.add(it.rule); else if (it.type === 'group') collectRuleIds(it, set); } return set; }
function collectValues(tree, vals = {}) { for (const it of tree.items) { if (it.type === 'cond') { if (it.rule === 'keyword_search') vals[it.rule] = { value: it.value, mode: it.mode }; else if (it.rule === 'amount_over') vals[it.rule] = { op: it.op, value: it.value, target: it.target }; else if (it.rule === 'party_freq') vals[it.rule] = { op: it.op, value: it.value }; } else if (it.type === 'group') collectValues(it, vals); } return vals; }

function logMsg(msg, type = 'info') { const p = document.createElement('p'); p.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`; if (type === 'error') p.classList.add('text-red-400'); if (type === 'success') p.classList.add('text-green-400'); $log.prepend(p); }
function showLoading(show) { $loading.classList.toggle('hidden', !show); $loading.classList.toggle('flex', show); }

function adjustColumnWidths(tbl) {
  const rows = Array.from(tbl.rows);
  if (!rows.length) return;
  const colCount = rows[0].cells.length;
  const max = Array(colCount).fill(0);
  rows.forEach(r => {
    Array.from(r.cells).forEach((c, i) => {
      const w = c.scrollWidth;
      if (w > max[i]) max[i] = w;
    });
  });
  rows.forEach(r => {
    Array.from(r.cells).forEach((c, i) => {
      c.style.minWidth = max[i] + 'px';
      c.style.whiteSpace = 'nowrap';
    });
  });
}

function renderTable(rows, hi = new Set(), ruleMap = {}) {
  $aiVoucherResults.classList.add('hidden');
  $tableWrap.classList.remove('hidden');
  // Ensure the table container aligns to the start when displaying data
  $tableWrap.classList.remove('items-center', 'justify-center', 'flex');
  $tableWrap.classList.add('block');
  if (!rows.length) {
    // Revert to centered layout when showing the empty message
    $tableWrap.classList.remove('block');
    $tableWrap.classList.add('flex', 'items-center', 'justify-center');
    $tableWrap.innerHTML = '<p class="text-gray-500">표시할 데이터가 없습니다.</p>';
    return;
  }  const tbl = document.createElement('table'); tbl.className = 'text-sm text-left border-collapse';
  const headers = [...dataHeaders, 'AI 코칭'];
  const head = `<thead class="bg-gray-100"><tr>${headers.map(h => `<th class="p-2 border-b font-semibold whitespace-nowrap">${h}</th>`).join('')}</tr></thead>`;
  const body = `<tbody>${rows.map((row, idx) => {
    const originalIndex = row.__idx;
    const isHighlighted = hi.has(idx);
    const cls = isHighlighted ? 'highlight' : '';
    const ruleId = isHighlighted && ruleMap[originalIndex] ? ruleMap[originalIndex][0] : null;
    const ruleName = ruleId ? Object.keys(ruleTitles)[ruleId - 1] : '';
    const coachButton = isHighlighted ? `<button class="ai-coach-btn text-blue-500 hover:text-blue-700" data-row-index="${originalIndex}" data-rule-name="${ruleName}" title="AI 코치에게 물어보기"><i class="fas fa-user-md"></i></button>` : '';
    return `<tr class="border-b hover:bg-gray-50 ${cls}">${dataHeaders.map(c => `<td class="p-2 whitespace-nowrap">${row[c] ?? ''}</td>`).join('')}<td class="p-2 text-center whitespace-nowrap">${coachButton}</td></tr>`;
  }).join('')}</tbody>`;
  tbl.innerHTML = head + body;
  $tableWrap.innerHTML = ''; $tableWrap.appendChild(tbl); adjustColumnWidths(tbl);
}

function renderAiVoucherResults(results) {
    $tableWrap.classList.add('hidden');
    $aiVoucherResults.classList.remove('hidden');
    $aiVoucherResults.innerHTML = '';
    if (!results || results.length === 0) { $aiVoucherResults.innerHTML = '<p class="text-gray-500 text-center p-8">AI 분석 결과, 특별한 회계적 오류가 발견되지 않았습니다.</p>'; return; }
    const errorVouchers = results.filter(r => r.analysis.isError);
    if (errorVouchers.length === 0) { $aiVoucherResults.innerHTML = '<p class="text-green-600 font-semibold text-center p-8">AI 분석 완료! 모든 전표가 대차평형의 원리를 만족합니다.</p>'; return; }
    logMsg(`AI 전표세트 분석 완료. ${errorVouchers.length}개의 잠재적 오류 발견.`, 'success');
    errorVouchers.forEach(voucher => {
        const card = document.createElement('div');
        card.className = 'voucher-card bg-white p-4 rounded-lg shadow-md mb-4';
        const { analysis, entries } = voucher;
        let entriesHtml = '<table class="w-full text-xs mt-3 border-t pt-3">';
        entriesHtml += `<thead class="bg-gray-50"><tr>${['계정과목', '차변금액', '대변금액', '거래처', '적요'].map(h => `<th class="p-1 text-left font-medium whitespace-nowrap">${h}</th>`).join('')}</tr></thead><tbody>`;
        entries.forEach(e => { entriesHtml += `<tr class="border-b"><td class="p-1 whitespace-nowrap">${e['계정과목'] || ''}</td><td class="p-1 text-right whitespace-nowrap">${e['차변금액'] ? parseInt(e['차변금액']).toLocaleString() : ''}</td><td class="p-1 text-right whitespace-nowrap">${e['대변금액'] ? parseInt(e['대변금액']).toLocaleString() : ''}</td><td class="p-1 whitespace-nowrap">${e['거래처'] || ''}</td><td class="p-1 whitespace-nowrap">${e['적요'] || ''}</td></tr>`; });
        entriesHtml += '</tbody></table>';
        card.innerHTML = `<div class="flex justify-between items-start"><div><span class="text-xs bg-red-100 text-red-800 font-bold px-2 py-1 rounded-full">${analysis.errorType}</span><h4 class="text-lg font-bold mt-1">전표일자: ${voucher.date} / 전표번호: ${voucher.voucherNo}</h4></div></div><div class="mt-3 space-y-3"><div><h5 class="font-semibold text-gray-700">🚨 오류 원인</h5><p class="text-sm text-gray-600 bg-gray-50 p-2 rounded">${analysis.cause.replace(/\n/g, '<br>')}</p></div><div><h5 class="font-semibold text-gray-700">💡 해결 방안</h5><p class="text-sm text-gray-600 bg-gray-50 p-2 rounded">${analysis.solution.replace(/\n/g, '<br>')}</p></div></div><details class="mt-3 text-sm"><summary class="cursor-pointer text-blue-600">관련 분개 보기</summary>${entriesHtml}</details>`;
        $aiVoucherResults.appendChild(card);
    });
}

async function runRuleBasedAnalysis() {
    const f = $file.files[0];
    if (!f) { logMsg('파일을 먼저 선택하세요.', 'error'); return; }
    const activeRules = [...collectRuleIds(logicTree)];
    const vals = collectValues(logicTree);
    const fd = new FormData();
    fd.append('file', f); fd.append('active_rules', JSON.stringify(activeRules)); fd.append('values', JSON.stringify(vals)); fd.append('logic_op', 'AND'); fd.append('logic_tree', JSON.stringify(logicTree));
    showLoading(true);
    try {
        const res = await fetch('/analyze', { method: 'POST', body: fd });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        dataHeaders = data.headers; originalJournalData = data.rows;
        journalData = data.rows.map((r, i) => ({ ...r, __idx: i }));
        lastRuleMap = {}; for (const k in data.rule_map) lastRuleMap[+k] = data.rule_map[k];
        const flagged = new Set(data.flagged_indices);
        let hi = new Set(flagged);
        if ($chkSet.checked) {
            const keys = new Set([...flagged].map(i => `${journalData[i]['전표일자']}|${journalData[i]['전표번호']}`));
            journalData.forEach((r, i) => { if (keys.has(`${r['전표일자']}|${r['전표번호']}`)) hi.add(i); });
        }
        let rowsToDisplay = journalData;
        if ($chkOnly.checked) rowsToDisplay = rowsToDisplay.filter(r => hi.has(r.__idx));
        const displayedHighlightSet = new Set();
        rowsToDisplay.forEach((r, i) => { if (hi.has(r.__idx)) displayedHighlightSet.add(i); });
        renderTable(rowsToDisplay, displayedHighlightSet, lastRuleMap);
        logMsg(`규칙 기반 분석 완료 – Tx코드 생성, ${hi.size}개 분개 확인`, 'success');
    } catch (e) { logMsg('분석 오류: ' + e.message, 'error'); } finally { showLoading(false); }
}

async function runAiVoucherAnalysis() {
    const f = $file.files[0];
    if (!f) { logMsg('파일을 먼저 선택하세요.', 'error'); return; }
    const fd = new FormData();
    fd.append('file', f);
    showLoading(true);
    logMsg('AI 전표세트 분석을 시작합니다...', 'info');
    try {
        const res = await fetch('/ai_analyze_vouchers', { method: 'POST', body: fd });
        if (!res.ok) { const errData = await res.json(); throw new Error(errData.error || '서버 응답 오류'); }
        const data = await res.json();
        renderAiVoucherResults(data);
    } catch (e) { logMsg('AI 분석 오류: ' + e.message, 'error'); $aiVoucherResults.innerHTML = `<p class="text-red-500">${e.message}</p>`; } finally { showLoading(false); }
}

async function getAiCoaching(entryData, ruleName) {
    if (!ruleName) { logMsg('규칙 정보를 찾을 수 없어 AI 코칭을 호출할 수 없습니다.', 'error'); return; }
    $modalBody.innerHTML = '<div class="flex justify-center items-center p-8"><div class="loader"></div><span class="ml-4">AI 코치가 분석 중입니다...</span></div>';
    $modal.classList.remove('hidden');
    try {
        const res = await fetch('/ai_coach', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ entry_data: entryData, rule_name: ruleName }) });
        if (!res.ok) { const errData = await res.json(); throw new Error(errData.error || '서버 응답 오류'); }
        const data = await res.json();
        $modalBody.innerHTML = `<div class="mb-4"><span class="text-sm bg-yellow-100 text-yellow-800 font-bold px-2 py-1 rounded-full">${data.errorType}</span></div><div><h4 class="font-semibold text-gray-700 text-lg">🤔 원인 분석</h4><p class="text-base text-gray-600 mt-1 bg-gray-50 p-3 rounded-md">${data.cause}</p></div><div><h4 class="font-semibold text-gray-700 text-lg">✅ 해결 방안</h4><div class="text-base text-gray-600 mt-1 bg-gray-50 p-3 rounded-md">${data.solution}</div></div>`;
    } catch (e) { $modalBody.innerHTML = `<p class="text-red-500 p-4">AI 코칭 중 오류 발생: ${e.message}</p>`; logMsg('AI 코칭 오류: ' + e.message, 'error'); }
}

document.addEventListener('DOMContentLoaded', () => {
    renderTree();
    $file.onchange = async e => {
        const f = e.target.files[0];
        if (!f) return;
        $fileName.textContent = f.name;
        logMsg(`파일 선택: ${f.name}`, 'info');
        const fd = new FormData();
        fd.append('file', f);
        showLoading(true);
        try {
            const res = await fetch('/preview', { method: 'POST', body: fd });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            originalJournalData = data.rows;
            dataHeaders = data.headers;
            journalData = originalJournalData.map((r, i) => ({ ...r, __idx: i }));
            renderTable(journalData);
            logMsg('파일 파싱 및 미리보기 완료', 'success');
        } catch (err) {
            logMsg('파일 파싱 오류: ' + err.message, 'error');
            originalJournalData = [];
            dataHeaders = [];
            journalData = [];
            $tableContainer.innerHTML = `<p class="text-red-500">${err.message}</p>`;
        } finally {
            showLoading(false);
        }
    };    $runAnalysis.onclick = runRuleBasedAnalysis;
    $runAiVoucherAnalysis.onclick = runAiVoucherAnalysis;
    $closeModalBtn.onclick = () => $modal.classList.add('hidden');
    $modal.onclick = (e) => { if (e.target === $modal) $modal.classList.add('hidden'); };
    $tableContainer.onclick = e => { const btn = e.target.closest('.ai-coach-btn'); if (btn) { const rowIndex = parseInt(btn.dataset.rowIndex); const ruleName = btn.dataset.ruleName; const entryData = originalJournalData[rowIndex]; getAiCoaching(entryData, ruleName); } };
    document.getElementById('add-condition-btn').onclick = () => { const sel = document.getElementById('condition-select').value; logicTree.items.push(newCond(sel)); renderTree(); };
    document.getElementById('add-group-btn').onclick = () => { logicTree.items.push(newGroup()); renderTree(); };
    logMsg('EntryChecker가 준비되었습니다. 파일을 업로드하고 분석을 시작하세요.');
});
