/* ===== EntryChecker main.js – 2025-07-26 (Final Integrated Version) ===== */

let logicTree = { id: 0, type: 'group', op: 'AND', items: [] };
let nextId = 1;
const ruleTitles = {
  weekend_txn: '주말·공휴일 거래', amount_over: '금액 조건', keyword_search: '특정 키워드',
  party_freq: '거래처별 거래 횟수', round_million: '백만단위 이하 0',
  uniform_account: '동일 계정 전표세트', unbalanced_set: '차/대변 불일치 세트',
  tax_mismatch: 'Tx코드 검증 불일치'
};

let dataHeaders = [], journalData = [], originalJournalData = [], lastRuleMap = {};

const $file = document.getElementById('file-upload');
const $fileName = document.getElementById('file-name');
const $runAnalysis = document.getElementById('run-analysis');
const $runAiAnalysis = document.getElementById('run-ai-analysis');
const $aiInstruction = document.getElementById('ai-instruction');
const $aiInstructionError = document.getElementById('ai-instruction-error');
const $aiDataConsent = document.getElementById('ai-data-consent');
const $logicTree = document.getElementById('logic-tree');
const $log = document.getElementById('log-content');
const $taxSummary = document.getElementById('tax-summary');
const $tableContainer = document.getElementById('table-container');
const $tableWrap = $tableContainer;
const $chkSet = document.getElementById('chk-whole-voucher');
const $chkOnly = document.getElementById('chk-show-matching-only');
const $loading = document.getElementById('loading');
let lastTaxSummary = [];
let lastTaxValidation = null;

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
function formatWon(v) { return Number(v || 0).toLocaleString(); }
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[ch]);
}

function renderAiReport(report) {
  const meta = report.analysis_metadata || {};
  const risk = report.overall_risk || '중간';
  const riskStyle = risk === '높음' ? 'text-red-300 border-red-400/40 bg-red-500/10'
    : risk === '낮음' ? 'text-emerald-300 border-emerald-400/40 bg-emerald-500/10'
      : 'text-amber-300 border-amber-400/40 bg-amber-500/10';
  const findings = Array.isArray(report.findings) ? report.findings : [];
  const metrics = Array.isArray(report.key_metrics) ? report.key_metrics : [];
  const listSection = (title, items) => {
    if (!Array.isArray(items) || !items.length) return '';
    return `<div class="border-t border-slate-700 pt-3"><h5 class="font-bold text-sm text-violet-200 mb-1">${escapeHtml(title)}</h5><ul class="list-disc pl-5 text-sm text-slate-300 space-y-1">${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>`;
  };

  const article = document.createElement('article');
  article.className = 'my-3 border border-violet-400/40 rounded-xl overflow-hidden bg-slate-900 font-sans shadow-lg';
  article.innerHTML = `
      <div class="px-4 py-3 bg-violet-500/10 border-b border-violet-400/30 flex flex-wrap items-center gap-3">
        <h4 class="font-bold text-violet-200"><i class="fas fa-wand-magic-sparkles mr-2"></i>AI 전체 시트 분석 결과</h4>
        <span class="px-2 py-1 rounded-full border text-xs font-bold ${riskStyle}">종합 위험도 ${escapeHtml(risk)}</span>
        <span class="ml-auto text-xs text-slate-400">${formatWon(meta.analyzed_rows)}행 · ${escapeHtml(meta.model || '')}</span>
      </div>
      <div class="p-4 space-y-4">
        <p class="text-sm leading-6 text-slate-200">${escapeHtml(report.executive_summary || '')}</p>
        ${metrics.length ? `<div class="grid grid-cols-1 md:grid-cols-3 gap-2">${metrics.map(metric => `
          <div class="border border-slate-700 rounded-lg p-3 bg-slate-800">
            <div class="text-xs text-slate-400">${escapeHtml(metric.name)}</div>
            <div class="font-bold text-white mt-1">${escapeHtml(metric.value)}</div>
            <div class="text-xs text-slate-300 mt-1">${escapeHtml(metric.interpretation)}</div>
          </div>`).join('')}</div>` : ''}
        <div>
          <h5 class="font-bold text-sm text-violet-200 mb-2">주요 발견사항 (${formatWon(findings.length)}건)</h5>
          <div class="space-y-2">${findings.length ? findings.map(finding => {
            const severity = finding.severity || '중간';
            const severityStyle = severity === '높음' ? 'text-red-300 bg-red-500/10' : severity === '낮음' ? 'text-emerald-300 bg-emerald-500/10' : 'text-amber-300 bg-amber-500/10';
            const rows = Array.isArray(finding.row_numbers) ? finding.row_numbers : [];
            return `<div class="border border-slate-700 rounded-lg p-3 bg-slate-800/70">
              <div class="flex items-center gap-2"><span class="text-xs font-bold px-2 py-1 rounded ${severityStyle}">${escapeHtml(severity)}</span><strong class="text-sm text-white">${escapeHtml(finding.title)}</strong></div>
              <p class="text-sm text-slate-300 mt-2">${escapeHtml(finding.description)}</p>
              <p class="text-xs text-slate-400 mt-2"><strong>근거 행:</strong> ${rows.length ? rows.map(escapeHtml).join(', ') : '특정 행 없음'}</p>
              <p class="text-xs text-slate-300 mt-1"><strong>근거:</strong> ${escapeHtml(finding.evidence)}</p>
              <p class="text-xs text-violet-300 mt-1"><strong>권고 절차:</strong> ${escapeHtml(finding.recommendation)}</p>
            </div>`;
          }).join('') : '<p class="text-sm text-slate-400">보고된 주요 발견사항이 없습니다.</p>'}</div>
        </div>
        ${listSection('전체 패턴', report.patterns)}
        ${listSection('Tx·부가세 검토사항', report.tax_review)}
        ${listSection('분석 한계', report.limitations)}
        <p class="text-xs text-slate-500 border-t border-slate-700 pt-3">AI 결과는 감사·세무 결론이 아니며, 원본 증빙과 거래 사실을 확인해야 합니다.</p>
      </div>
  `;
  $log.prepend(article);
}

async function responseError(res) {
  const text = await res.text();
  try { return JSON.parse(text).error || text; } catch (_) { return text; }
}

async function runAiSheetAnalysis() {
  const f = $file.files[0];
  if (!f) { logMsg('파일을 먼저 선택하세요.', 'error'); return; }
  const instruction = $aiInstruction.value.trim();
  if (!instruction) {
    $aiInstructionError.classList.remove('hidden');
    $aiInstruction.classList.add('border-red-500', 'ring-2', 'ring-red-100');
    $aiInstruction.focus();
    logMsg('AI에게 요청할 분석 내용을 입력해주세요.', 'error');
    return;
  }
  if (!$aiDataConsent.checked) { logMsg('Vertex AI 데이터 전송 확인에 체크해주세요.', 'error'); return; }

  const fd = new FormData();
  fd.append('file', f);
  fd.append('instruction', instruction);
  fd.append('data_transfer_consent', 'true');
  showLoading(true);
  logMsg('Vertex AI가 전체 시트를 검토하고 있습니다. 파일 크기에 따라 시간이 걸릴 수 있습니다.', 'info');
  try {
    const res = await fetch('/ai_analyze_sheet', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await responseError(res));
    const report = await res.json();
    renderAiReport(report);
    const meta = report.analysis_metadata || {};
    const usage = meta.token_usage || {};
    const traffic = usage.traffic_type || meta.service_tier || 'unknown';
    logMsg(
      `AI 전체 분석 완료 – ${formatWon(meta.analyzed_rows)}행 검토 · ` +
      `토큰 입력 ${formatWon(usage.prompt_tokens)} / 출력 ${formatWon(usage.output_tokens)} / ` +
      `총 ${formatWon(usage.total_tokens)} (출력 상한 ${formatWon(meta.max_output_tokens)}토큰 · ${traffic})`,
      'success'
    );
  } catch (e) {
    logMsg('AI 전체 분석 오류: ' + e.message, 'error');
  } finally {
    showLoading(false);
  }
}

function renderTaxSummary(summary = [], validation = null) {
  lastTaxSummary = summary;
  lastTaxValidation = validation;
  if (!summary.length) {
    $taxSummary.classList.add('hidden');
    $taxSummary.innerHTML = '';
    return;
  }
  const validationHtml = validation ? `
      <div class="px-3 py-2 border-b text-xs flex items-center gap-3 ${validation.mismatch > 0 ? 'bg-red-50' : 'bg-green-50'}">
        <span class="font-bold ${validation.mismatch > 0 ? 'text-red-700' : 'text-green-700'}">
          <i class="fas ${validation.mismatch > 0 ? 'fa-triangle-exclamation' : 'fa-circle-check'} mr-1"></i>Tx코드 검증
        </span>
        <span class="text-gray-600">대사 ${formatWon(validation.checked)}건</span>
        <span class="text-green-700">일치 ${formatWon(validation.match)}건</span>
        <span class="${validation.mismatch > 0 ? 'text-red-700 font-bold' : 'text-gray-600'}">불일치 ${formatWon(validation.mismatch)}건</span>
        ${validation.manual > 0 ? `<span class="text-amber-700">추천없음(수동확인) ${formatWon(validation.manual)}건</span>` : ''}
        ${validation.mismatch > 0 ? `<span class="text-gray-500 ml-auto">'Tx코드 검증 불일치' 조건으로 해당 분개를 강조할 수 있습니다.</span>` : ''}
      </div>` : '';
  $taxSummary.classList.remove('hidden');
  $taxSummary.innerHTML = `
    <div class="border rounded-lg overflow-hidden">
      <div class="px-3 py-2 bg-gray-50 border-b flex items-center justify-between">
        <h4 class="font-bold text-sm text-gray-700">Tx 추천 요약</h4>
        <span class="text-xs text-gray-500">자동 추천값입니다. 신고 전 수동 검토가 필요합니다.</span>
      </div>${validationHtml}
      <div class="overflow-x-auto">
        <table class="w-full text-xs text-left">
          <thead class="bg-white">
            <tr>
              <th class="p-2 border-b">추천코드</th>
              <th class="p-2 border-b">분류</th>
              <th class="p-2 border-b text-right">분개수</th>
              <th class="p-2 border-b text-right">차변합계</th>
              <th class="p-2 border-b text-right">대변합계</th>
            </tr>
          </thead>
          <tbody>
            ${summary.map(r => `
              <tr class="border-b last:border-b-0">
                <td class="p-2 font-semibold">${r.code}</td>
                <td class="p-2">${r.label}</td>
                <td class="p-2 text-right">${formatWon(r.count)}</td>
                <td class="p-2 text-right">${formatWon(r.debit_sum)}</td>
                <td class="p-2 text-right">${formatWon(r.credit_sum)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>`;
}

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

const preferredTableHeaders = [
  '전표일자', '전표번호', '계정코드', '계정과목', '부가세코드',
  '차변금액', '대변금액', '거래처코드', 'Tx추천코드', 'Tx분류',
  'Tx신뢰도', 'Tx근거', 'Tx검증', '검토상태', '승인일자'
];

function getDisplayHeaders(headers) {
  const preferred = preferredTableHeaders.filter(header => headers.includes(header));
  const preferredSet = new Set(preferred);
  return [...preferred, ...headers.filter(header => !preferredSet.has(header))];
}

function renderTable(rows, hi = new Set(), ruleMap = {}) {
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
  const headers = getDisplayHeaders(dataHeaders);
  const head = `<thead class="bg-gray-100"><tr>${headers.map(h => `<th class="p-2 border-b font-semibold whitespace-nowrap">${h}</th>`).join('')}</tr></thead>`;
  const body = `<tbody>${rows.map((row, idx) => {
    const originalIndex = row.__idx;
    const isHighlighted = hi.has(idx);
    const cls = isHighlighted ? 'highlight' : '';
    return `<tr class="border-b hover:bg-gray-50 ${cls}">${headers.map(c => {
      if (c === '검토상태') {
        const value = row[c] || '미검토';
        if (!row['Tx추천코드']) return '<td class="p-2 whitespace-nowrap"></td>';
        return `<td class="p-2 whitespace-nowrap"><select class="review-status border rounded px-1 py-0.5 text-xs bg-white" data-row-index="${originalIndex}">
          ${['미검토', '확인완료', '수정필요', '보류'].map(opt => `<option value="${opt}" ${value === opt ? 'selected' : ''}>${opt}</option>`).join('')}
        </select></td>`;
      }
      if (c === 'Tx검증') {
        const v = String(row[c] ?? '');
        if (v.startsWith('불일치')) return `<td class="p-2 whitespace-nowrap text-red-600 font-bold">${v}</td>`;
        if (v === '일치') return `<td class="p-2 whitespace-nowrap text-green-600">${v}</td>`;
        if (v.startsWith('추천없음')) return `<td class="p-2 whitespace-nowrap text-amber-600">${v}</td>`;
        return `<td class="p-2 whitespace-nowrap">${v}</td>`;
      }
      if (lastTaxValidation && c === lastTaxValidation.source_col) {
        const v = String(row[c] ?? '');
        if (String(row['Tx검증'] ?? '').startsWith('불일치'))
          return `<td class="p-2 whitespace-nowrap text-red-600 line-through" title="원본 코드 (수정 제시됨)">${v}</td>`;
        return `<td class="p-2 whitespace-nowrap">${v}</td>`;
      }
      if (c === 'Tx추천코드' && String(row['Tx검증'] ?? '').startsWith('불일치')) {
        const v = String(row[c] ?? '');
        return `<td class="p-2 whitespace-nowrap text-green-700 font-bold" title="시스템이 제시한 수정 코드">${v} <span class="text-[10px] bg-green-100 text-green-800 px-1 rounded">수정제시</span></td>`;
      }
      return `<td class="p-2 whitespace-nowrap">${row[c] ?? ''}</td>`;
    }).join('')}</tr>`;
  }).join('')}</tbody>`;
  tbl.innerHTML = head + body;
  $tableWrap.innerHTML = ''; $tableWrap.appendChild(tbl); adjustColumnWidths(tbl);
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
        renderTaxSummary(data.tax_summary || [], data.tax_validation);
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

document.addEventListener('DOMContentLoaded', () => {
    renderTree();
    $aiInstruction.addEventListener('input', () => {
        if (!$aiInstruction.value.trim()) return;
        $aiInstructionError.classList.add('hidden');
        $aiInstruction.classList.remove('border-red-500', 'ring-2', 'ring-red-100');
    });
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
            renderTaxSummary(data.tax_summary || [], data.tax_validation);
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
    };
    $runAnalysis.onclick = runRuleBasedAnalysis;
    $runAiAnalysis.onclick = runAiSheetAnalysis;
    $tableContainer.onchange = e => {
        const sel = e.target.closest('.review-status');
        if (!sel) return;
        const rowIndex = parseInt(sel.dataset.rowIndex);
        if (originalJournalData[rowIndex]) originalJournalData[rowIndex]['검토상태'] = sel.value;
        if (journalData[rowIndex]) journalData[rowIndex]['검토상태'] = sel.value;
    };
    document.getElementById('add-condition-btn').onclick = () => { const sel = document.getElementById('condition-select').value; logicTree.items.push(newCond(sel)); renderTree(); };
    document.getElementById('add-group-btn').onclick = () => { logicTree.items.push(newGroup()); renderTree(); };
    logMsg('EntryChecker가 준비되었습니다. 파일을 업로드하고 분석을 시작하세요.');
});
