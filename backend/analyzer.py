import pandas as pd
import re
import holidays
import json
from pathlib import Path

KR_HOLIDAYS = holidays.KR()  # 대한민국 공휴일

DATE_COL_ALIASES = ('전표일자', '거래일자', '일자', '날짜')
VOUCHER_COL_ALIASES = ('전표번호', '전표 no', '전표NO', 'voucher_no')
ACCOUNT_COL_ALIASES = ('계정과목', '계정명', '계정')
DEBIT_COL_ALIASES = ('차변금액', '차변', '차변 금액')
CREDIT_COL_ALIASES = ('대변금액', '대변', '대변 금액')
EXISTING_TAX_COL_ALIASES = ('부가세코드', 'Tx코드', '세무코드', '부가세유형', 'tax_code')

TAX_RULES_PATH = Path(__file__).with_name('tax_rules.json')


def _load_tax_rules():
    with TAX_RULES_PATH.open(encoding='utf-8') as f:
        return json.load(f)


TAX_RULES = _load_tax_rules()
TAX_CODE_LABELS = TAX_RULES['labels']
TAX_KEYWORDS = TAX_RULES['keyword_groups']
TAX_CONFIDENCE = TAX_RULES['confidence']


def _find_col(df, candidates):
    normalized = {str(col).strip().lower(): col for col in df.columns}
    for candidate in candidates:
        found = normalized.get(str(candidate).strip().lower())
        if found is not None:
            return found
    return None


def _amount_series(df, candidates):
    col = _find_col(df, candidates)
    if col is None:
        return pd.Series(0, index=df.index, dtype='float64')
    return (
        df[col]
        .astype(str)
        .str.replace(',', '', regex=False)
        .str.strip()
        .replace({'': 0, 'nan': 0, 'None': 0})
        .pipe(pd.to_numeric, errors='coerce')
        .fillna(0)
    )


def _text_series(df, candidates):
    col = _find_col(df, candidates)
    if col is None:
        return pd.Series('', index=df.index, dtype='object')
    return df[col].fillna('').astype(str)


def _contains_any(text, keywords):
    return any(keyword.lower() in text for keyword in keywords)


def _make_row_text(df):
    text_cols = [
        col for col in df.columns
        if df[col].dtype == 'object' or pd.api.types.is_string_dtype(df[col])
    ]
    if not text_cols:
        return pd.Series('', index=df.index, dtype='object')
    return (
        df[text_cols]
        .fillna('')
        .astype(str)
        .agg(' '.join, axis=1)
        .str.lower()
    )


def _add_or_replace_column(df, name, values, after_col=None):
    if name in df.columns:
        df[name] = values
        return
    if after_col in df.columns:
        df.insert(df.columns.get_loc(after_col) + 1, name, values)
    else:
        df[name] = values


def add_tax_recommendations(df):
    """전표 단위 부가세 라인과 계정/적요 키워드로 Tx 추천코드를 붙인다."""
    account_col = _find_col(df, ACCOUNT_COL_ALIASES)
    voucher_col = _find_col(df, VOUCHER_COL_ALIASES)
    account_text = _text_series(df, ACCOUNT_COL_ALIASES).str.lower()
    row_text = _make_row_text(df)

    tax_codes = pd.Series('', index=df.index, dtype='object')
    tax_confidence = pd.Series('', index=df.index, dtype='object')
    tax_reasons = pd.Series('', index=df.index, dtype='object')
    group_keys = df[voucher_col] if voucher_col is not None else pd.Series(df.index, index=df.index)

    for _, group in df.groupby(group_keys, dropna=False, sort=False):
        idx = group.index
        group_text = ' '.join(row_text.loc[idx].tolist())
        group_accounts = account_text.loc[idx]
        has_output_vat = group_accounts.str.contains('부가세예수', na=False).any()
        has_input_vat = group_accounts.str.contains('부가세대급|부가세대급금|선급부가세', regex=True, na=False).any()

        for row_idx in idx:
            text = row_text.at[row_idx]
            acct = account_text.at[row_idx]
            debit = df.at[row_idx, '차변금액']
            credit = df.at[row_idx, '대변금액']
            is_negative = debit < 0 or credit < 0
            adjustment_note = ' + 음수 금액(취소/차감 가능성)' if is_negative else ''

            if '부가세예수' in acct:
                tax_codes.at[row_idx] = 'TX91'
                tax_confidence.at[row_idx] = TAX_CONFIDENCE['vat_line']
                tax_reasons.at[row_idx] = '부가세예수금 계정'
                continue

            if re.search(r'부가세대급|선급부가세', acct):
                tax_codes.at[row_idx] = 'TX92'
                tax_confidence.at[row_idx] = TAX_CONFIDENCE['vat_line']
                tax_reasons.at[row_idx] = '부가세대급금 계정'
                continue

            if credit != 0 and _contains_any(acct, TAX_KEYWORDS['sales']):
                if _contains_any(text, TAX_KEYWORDS['zero_rate']):
                    tax_codes.at[row_idx] = 'TX02'
                    tax_confidence.at[row_idx] = (
                        TAX_CONFIDENCE['negative_adjustment']
                        if is_negative else TAX_CONFIDENCE['zero_rate_keyword']
                    )
                    tax_reasons.at[row_idx] = '영세율/수출 관련 단서' + adjustment_note
                elif _contains_any(text, TAX_KEYWORDS['exempt']):
                    tax_codes.at[row_idx] = 'TX03'
                    tax_confidence.at[row_idx] = (
                        TAX_CONFIDENCE['negative_adjustment']
                        if is_negative else TAX_CONFIDENCE['exempt_keyword']
                    )
                    tax_reasons.at[row_idx] = '면세 관련 단서' + adjustment_note
                else:
                    tax_codes.at[row_idx] = 'TX01'
                    tax_confidence.at[row_idx] = (
                        TAX_CONFIDENCE['negative_adjustment']
                        if is_negative else
                        TAX_CONFIDENCE['sales_with_output_vat']
                        if has_output_vat else TAX_CONFIDENCE['sales_account_only']
                    )
                    tax_reasons.at[row_idx] = '매출 계정' + (' + 같은 전표 부가세예수금' if has_output_vat else '') + adjustment_note
                continue

            if debit != 0 and _contains_any(acct, TAX_KEYWORDS['purchase']):
                if _contains_any(text, TAX_KEYWORDS['non_deductible']):
                    tax_codes.at[row_idx] = 'TX14'
                    tax_confidence.at[row_idx] = (
                        TAX_CONFIDENCE['negative_adjustment']
                        if is_negative else TAX_CONFIDENCE['non_deductible_keyword']
                    )
                    tax_reasons.at[row_idx] = '불공제 매입 관련 단서' + adjustment_note
                elif _contains_any(text, TAX_KEYWORDS['allocation']):
                    tax_codes.at[row_idx] = 'TX12'
                    tax_confidence.at[row_idx] = (
                        TAX_CONFIDENCE['negative_adjustment']
                        if is_negative else TAX_CONFIDENCE['allocation_keyword']
                    )
                    tax_reasons.at[row_idx] = '공통매입/안분 관련 단서' + adjustment_note
                elif _contains_any(text, TAX_KEYWORDS['exempt']):
                    tax_codes.at[row_idx] = 'TX13'
                    tax_confidence.at[row_idx] = (
                        TAX_CONFIDENCE['negative_adjustment']
                        if is_negative else TAX_CONFIDENCE['exempt_purchase_keyword']
                    )
                    tax_reasons.at[row_idx] = '면세 매입 관련 단서' + adjustment_note
                else:
                    tax_codes.at[row_idx] = 'TX11'
                    tax_confidence.at[row_idx] = (
                        TAX_CONFIDENCE['negative_adjustment']
                        if is_negative else
                        TAX_CONFIDENCE['purchase_with_input_vat']
                        if has_input_vat else TAX_CONFIDENCE['purchase_account_only']
                    )
                    tax_reasons.at[row_idx] = '매입/비용 계정' + (' + 같은 전표 부가세대급금' if has_input_vat else '') + adjustment_note

    review_status = tax_codes.map(lambda code: '미검토' if code else '')
    _add_or_replace_column(df, 'Tx추천코드', tax_codes, after_col=account_col)
    _add_or_replace_column(df, 'Tx분류', tax_codes.map(TAX_CODE_LABELS).fillna(''), after_col='Tx추천코드')
    _add_or_replace_column(
        df,
        'Tx신뢰도',
        tax_confidence.map(lambda v: f'{int(v)}%' if v != '' else ''),
        after_col='Tx분류',
    )
    _add_or_replace_column(df, 'Tx근거', tax_reasons, after_col='Tx신뢰도')
    _add_or_replace_column(df, '검토상태', review_status, after_col='Tx근거')
    return df


def validate_tax_codes(df):
    """파일에 이미 입력된 부가세 코드를 Tx추천코드와 대사해 불일치를 표시한다."""
    col = _find_col(df, EXISTING_TAX_COL_ALIASES)
    if col is None or 'Tx추천코드' not in df.columns:
        return None

    existing = df[col].fillna('').astype(str).str.strip().str.upper()
    recommended = df['Tx추천코드'].fillna('').astype(str)

    # 원본 코드 열을 추천코드 바로 앞으로 옮겨 나란히 비교할 수 있게 한다
    moved = df.pop(col)
    df.insert(df.columns.get_loc('Tx추천코드'), col, moved)

    result = pd.Series('', index=df.index, dtype='object')
    both = (existing != '') & (recommended != '')
    match_mask = both & (existing == recommended)
    mismatch_mask = both & (existing != recommended)
    only_existing = (existing != '') & (recommended == '')

    result[match_mask] = '일치'
    result[mismatch_mask] = '불일치'
    result[only_existing] = '추천없음(수동확인)'

    _add_or_replace_column(df, 'Tx검증', result, after_col='Tx근거')
    return {
        'checked': int(both.sum()),
        'match': int(match_mask.sum()),
        'mismatch': int(mismatch_mask.sum()),
        'manual': int(only_existing.sum()),
        'source_col': col,
    }


def build_tax_summary(df):
    if 'Tx추천코드' not in df.columns:
        return []

    summary = []
    for code, label in TAX_CODE_LABELS.items():
        mask = df['Tx추천코드'].fillna('') == code
        if not mask.any():
            continue
        summary.append({
            'code': code,
            'label': label,
            'count': int(mask.sum()),
            'debit_sum': int(round(df.loc[mask, '차변금액'].sum())),
            'credit_sum': int(round(df.loc[mask, '대변금액'].sum())),
        })
    return summary

def _parse_dates(series):
    """YYYYMMDD ‧ 엑셀 직렬값 ‧ 문자열 등 어떤 형태든 datetime64로."""
    # 이미 datetime 형이면 그대로
    if pd.api.types.is_datetime64_any_dtype(series):
        return series

    s = series.copy()

    # 숫자형: 엑셀 직렬값 or 8자리(YYYYMMDD)
    if pd.api.types.is_numeric_dtype(s):
        s_str = s.astype('Int64').astype(str)
        dt = pd.Series(pd.NaT, index=s.index)

        # 8자리 → YYYYMMDD 포맷
        ymd_mask = s_str.str.fullmatch(r'\d{8}')
        if ymd_mask.any():
            dt.loc[ymd_mask] = pd.to_datetime(
                s_str[ymd_mask], format='%Y%m%d', errors='coerce'
            )

        # 그 외 숫자 → 엑셀 직렬값
        serial_mask = ~ymd_mask
        if serial_mask.any():
            dt.loc[serial_mask] = pd.to_datetime(
                s[serial_mask], unit='D', origin='1899-12-30', errors='coerce'
            )
        return dt

    # 문자열
    raw = s.astype(str).str.strip().str.replace(r'[./]', '-', regex=True)
    dt = pd.to_datetime(raw, errors='coerce')
    ymd_mask = dt.isna() & raw.str.fullmatch(r'\d{8}')
    if ymd_mask.any():
        dt.loc[ymd_mask] = pd.to_datetime(raw[ymd_mask], format='%Y%m%d', errors='coerce')
    return dt

def flag_weekend_txn(df, date_col=None):
    """
    토·일 또는 한국 공휴일이면 True. 그 외는 False.
    """
    date_col = date_col or _find_col(df, DATE_COL_ALIASES)
    if date_col is None:
        return pd.Series(False, index=df.index)

    dt = _parse_dates(df[date_col])

    is_weekend = dt.dt.weekday.isin([5, 6])          # 토(5), 일(6)
    is_holiday = dt.apply(lambda d: d.date() in KR_HOLIDAYS if pd.notna(d) else False)
    return is_weekend | is_holiday         # 둘 중 하나면 강조



def flag_amount_over(df, op, thr, is_debit=True):
    col = '차변금액' if is_debit else '대변금액'

    if   op == '>':  return df[col] >  thr
    elif op == '>=': return df[col] >= thr
    elif op == '==': return df[col] == thr
    elif op == '<=': return df[col] <= thr
    elif op == '<':  return df[col] <  thr
    else:            return pd.Series(False, index=df.index)

def flag_keyword(df, keywords):
    kw_list = [k.strip() for k in keywords.split(',') if k.strip()]
    if not kw_list:
        return pd.Series(False, index=df.index)

    pattern = '|'.join(map(re.escape, kw_list))
    # 계정과목 + 적요 열 모두 검색, 대소문자 무시
    subject = _text_series(df, ACCOUNT_COL_ALIASES)
    desc    = df.get('적요', pd.Series('', index=df.index)).astype(str)

    return subject.str.contains(pattern, case=False, na=False) | \
           desc.str.contains(pattern, case=False, na=False)

def flag_party_freq(df, op, thr):
    """전표세트 기준 거래 횟수 조건."""
    if '거래처코드' not in df.columns:
        return pd.Series(False, index=df.index)

    tmp = df[['거래처코드', '전표일자', '전표번호']].dropna(subset=['거래처코드'])
    sets = tmp.drop_duplicates()
    counts = sets.groupby('거래처코드').size()
    freq = df['거래처코드'].map(counts).fillna(0)

    if   op == '>':  return freq >  thr
    elif op == '>=': return freq >= thr
    elif op == '==': return freq == thr
    elif op == '<=': return freq <= thr
    elif op == '<':  return freq <  thr
    else:            return pd.Series(False, index=df.index)

def flag_round_million(df):
    """차/대변 금액이 1,000,000원 단위일 때."""
    debit = df['차변금액'].abs()
    credit = df['대변금액'].abs()
    m_debit = (debit != 0) & (debit % 1_000_000 == 0)
    m_credit = (credit != 0) & (credit % 1_000_000 == 0)
    return m_debit | m_credit

def flag_uniform_account(df):
    """전표세트 내 계정과목이 모두 동일한 경우."""
    if not {'전표일자', '전표번호', '계정과목'}.issubset(df.columns):
        return pd.Series(False, index=df.index)
    grouped = df.groupby(['전표일자', '전표번호'])['계정과목'].nunique()
    target_sets = set(grouped[grouped == 1].index)
    idx = list(zip(df['전표일자'], df['전표번호']))
    return pd.Series([(k in target_sets) for k in idx], index=df.index)

def flag_tax_mismatch(df):
    """입력된 부가세 코드와 Tx추천코드가 서로 다른 분개."""
    if 'Tx검증' not in df.columns:
        return pd.Series(False, index=df.index)
    return df['Tx검증'].astype(str).str.startswith('불일치')

def flag_unbalanced_set(df):
    """전표세트 차변 합과 대변 합이 일치하지 않음."""
    if not {'전표일자', '전표번호', '차변금액', '대변금액'}.issubset(df.columns):
        return pd.Series(False, index=df.index)
    sums = df.groupby(['전표일자', '전표번호'])[['차변금액', '대변금액']].sum()
    bad_sets = set(sums.index[sums['차변금액'] != sums['대변금액']])
    idx = list(zip(df['전표일자'], df['전표번호']))
    return pd.Series([(k in bad_sets) for k in idx], index=df.index)

def analyze_journal(
    df,
    active_rules,
    rule_values,
    logic_op: str = 'AND',
    logic_tree: dict | None = None,
):
    df = df.copy()

    # ───────────────── 1. 숫자 열 변환 ──────────────────
    df['차변금액'] = _amount_series(df, DEBIT_COL_ALIASES)
    df['대변금액'] = _amount_series(df, CREDIT_COL_ALIASES)
    add_tax_recommendations(df)
    tax_validation = validate_tax_codes(df)
    tax_summary = build_tax_summary(df)

    # ───────────────── 2. 규칙별 mask 계산 ──────────────────
    masks = []  # 모든 mask 리스트 (순서 유지)
    rule_map = {i: [] for i in df.index}  # index → [규칙 번호]
    rule_no = 1  # 1부터 부여
    rule_masks: dict[str, pd.Series] = {}

    if not (logic_tree and logic_tree.get('items')):
        # 주말·공휴일
        if 'weekend_txn' in active_rules:
            m = flag_weekend_txn(df)
            rule_masks['weekend_txn'] = m
            masks.append(m)
            for idx in m[m].index:
                rule_map[idx].append(rule_no)
        rule_no += 1

        # 금액 조건
        if 'amount_over' in active_rules:
            cond = rule_values.get('amount_over', {})
            op = cond.get('op', '>')
            thr = float(cond.get('value', 0))
            target = cond.get('target', 'debit')
            m = flag_amount_over(df, op, thr, is_debit=(target != 'credit'))
            rule_masks['amount_over'] = m
            masks.append(m)
            for idx in m[m].index:
                rule_map[idx].append(rule_no)
        rule_no += 1

        # 키워드 조건
        if 'keyword_search' in active_rules:
            cond = rule_values.get('keyword_search', {})
            kw = cond.get('value', '') if isinstance(cond, dict) else cond
            mode = cond.get('mode', 'include') if isinstance(cond, dict) else 'include'
            m = flag_keyword(df, kw)
            if mode == 'exclude':
                m = ~m
            rule_masks['keyword_search'] = m
            masks.append(m)
            for idx in m[m].index:
                rule_map[idx].append(rule_no)
        rule_no += 1

        # 거래처 빈도 조건
        if 'party_freq' in active_rules:
            cond = rule_values.get('party_freq', {})
            op = cond.get('op', '>=')
            thr = float(cond.get('value', 0))
            m = flag_party_freq(df, op, thr)
            rule_masks['party_freq'] = m
            masks.append(m)
            for idx in m[m].index:
                rule_map[idx].append(rule_no)
        rule_no += 1

        # 백만단위 이하 모두 0
        if 'round_million' in active_rules:
            m = flag_round_million(df)
            rule_masks['round_million'] = m
            masks.append(m)
            for idx in m[m].index:
                rule_map[idx].append(rule_no)
        rule_no += 1

        # 동일 계정과목 세트
        if 'uniform_account' in active_rules:
            m = flag_uniform_account(df)
            rule_masks['uniform_account'] = m
            masks.append(m)
            for idx in m[m].index:
                rule_map[idx].append(rule_no)
        rule_no += 1

        # 차변대변 불일치 세트
        if 'unbalanced_set' in active_rules:
            m = flag_unbalanced_set(df)
            rule_masks['unbalanced_set'] = m
            masks.append(m)
            for idx in m[m].index:
                rule_map[idx].append(rule_no)
        rule_no += 1

        # Tx코드 검증 불일치
        if 'tax_mismatch' in active_rules:
            m = flag_tax_mismatch(df)
            rule_masks['tax_mismatch'] = m
            masks.append(m)
            for idx in m[m].index:
                rule_map[idx].append(rule_no)
        rule_no += 1

    # ───────────────── 3. 모든 mask 결합 ────────────────────
    def eval_node(node) -> pd.Series:
        nonlocal rule_no
        if not node:
            return pd.Series(False, index=df.index)
        if node.get('type') == 'cond':
            rule = node.get('rule')
            if rule == 'weekend_txn':
                m = flag_weekend_txn(df)
            elif rule == 'amount_over':
                op = node.get('op', '>')
                thr = float(node.get('value', 0))
                target = node.get('target', 'debit')
                m = flag_amount_over(df, op, thr, is_debit=(target != 'credit'))
            elif rule == 'keyword_search':
                kw = node.get('value', '')
                mode = node.get('mode', 'include')
                m = flag_keyword(df, kw)
                if mode == 'exclude':
                    m = ~m
            elif rule == 'party_freq':
                op = node.get('op', '>=')
                thr = float(node.get('value', 0))
                m = flag_party_freq(df, op, thr)
            elif rule == 'round_million':
                m = flag_round_million(df)
            elif rule == 'uniform_account':
                m = flag_uniform_account(df)
            elif rule == 'unbalanced_set':
                m = flag_unbalanced_set(df)
            elif rule == 'tax_mismatch':
                m = flag_tax_mismatch(df)
            else:
                m = pd.Series(False, index=df.index)
            for idx in m[m].index:
                rule_map[idx].append(rule_no)
            rule_no += 1
            return m

        items = [eval_node(it) for it in node.get('items', [])]
        if not items:
            return pd.Series(False, index=df.index)
        op = node.get('op', 'AND').upper()
        result = items[0].copy()
        for m in items[1:]:
            if op == 'OR':
                result = result | m
            else:
                result = result & m
        return result

    if logic_tree and logic_tree.get('items'):
        final_mask = eval_node(logic_tree)
    elif not masks:
        final_mask = pd.Series(False, index=df.index)
    elif logic_op.upper() == 'OR':
        final_mask = masks[0]
        for m in masks[1:]:
            final_mask = final_mask | m
    else:  # 기본 AND
        final_mask = masks[0]
        for m in masks[1:]:
            final_mask = final_mask & m

    flagged = list(final_mask[final_mask].index)

    df_disp = df.copy()
    for col in ('차변금액', '대변금액'):
        if col in df_disp.columns:
            df_disp[col] = df_disp[col].apply(lambda v: f"{int(round(v)):,}")

    # ───────────────── 4. 결과 패키징 ──────────────────────
    return {
        "headers": list(df.columns),
        "rows": df_disp.to_dict('records'),
        "tax_summary": tax_summary,
        "tax_validation": tax_validation,
        "flagged_indices": flagged,
        "rule_map": {str(k): v for k, v in rule_map.items()}
    }


