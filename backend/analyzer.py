import pandas as pd
import re
import holidays

KR_HOLIDAYS = holidays.KR()  # 대한민국 공휴일

DATE_COL_ALIASES = ('전표일자', '거래일자', '일자', '날짜')
VOUCHER_COL_ALIASES = ('전표번호', '전표 no', '전표NO', 'voucher_no')
ACCOUNT_COL_ALIASES = ('계정과목', '계정명', '계정')
DEBIT_COL_ALIASES = ('차변금액', '차변', '차변 금액')
CREDIT_COL_ALIASES = ('대변금액', '대변', '대변 금액')

TAX_CODE_LABELS = {
    'TX01': '과세매출',
    'TX02': '영세율매출',
    'TX03': '면세매출',
    'TX11': '과세매입',
    'TX12': '안분매입',
    'TX13': '면세매입',
    'TX14': '불공제매입(과세)',
    'TX91': '매출부가세',
    'TX92': '매입부가세',
    'TX00': '대상외',
}

ZERO_RATE_KEYWORDS = ('영세', '수출', '직수출', '간접수출', '내국신용장', '구매확인서', '국외')
EXEMPT_KEYWORDS = ('면세', '비과세', '토지', '보험료', '의료', '교육', '도서', '미가공', '농산', '수산', '축산', '주택임대')
NON_DEDUCTIBLE_KEYWORDS = ('불공제', '접대', '접대비', '승용차', '비영업용', '업무무관', '간이영수증', '개인카드')
ALLOCATION_KEYWORDS = ('안분', '공통매입', '공통', '겸영', '과면세', '공통비')
SALES_KEYWORDS = ('매출', '수입수수료', '임대수익', '용역수익')
PURCHASE_KEYWORDS = (
    '매입', '상품', '원재료', '재료', '외주', '복리후생비', '소모품', '운반비',
    '광고', '임차', '지급수수료', '수선', '여비', '교육훈련', '차량', '통신',
    '전력', '수도', '도서', '보험', '접대'
)


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


def add_tax_codes(df):
    """전표 단위 부가세 라인과 계정/적요 키워드로 Tx코드를 추정해 붙인다."""
    account_col = _find_col(df, ACCOUNT_COL_ALIASES)
    voucher_col = _find_col(df, VOUCHER_COL_ALIASES)
    account_text = _text_series(df, ACCOUNT_COL_ALIASES).str.lower()
    row_text = _make_row_text(df)

    tax_codes = pd.Series('TX00', index=df.index, dtype='object')
    tax_reasons = pd.Series('세금코드 대상 계정 아님', index=df.index, dtype='object')
    group_keys = df[voucher_col] if voucher_col is not None else pd.Series(df.index, index=df.index)

    for _, group in df.groupby(group_keys, dropna=False, sort=False):
        idx = group.index
        group_text = ' '.join(row_text.loc[idx].tolist())
        group_accounts = account_text.loc[idx]
        has_output_vat = group_accounts.str.contains('부가세예수', na=False).any()
        has_input_vat = group_accounts.str.contains('부가세대급|선급부가세', regex=True, na=False).any()

        for row_idx in idx:
            text = row_text.at[row_idx]
            acct = account_text.at[row_idx]
            context = f'{text} {group_text}'
            debit = df.at[row_idx, '차변금액']
            credit = df.at[row_idx, '대변금액']

            if '부가세예수' in acct:
                tax_codes.at[row_idx] = 'TX91'
                tax_reasons.at[row_idx] = '부가세예수금 계정'
                continue

            if re.search(r'부가세대급|선급부가세', acct):
                tax_codes.at[row_idx] = 'TX92'
                tax_reasons.at[row_idx] = '부가세대급금 계정'
                continue

            if credit > 0 and _contains_any(acct, SALES_KEYWORDS):
                if _contains_any(context, ZERO_RATE_KEYWORDS):
                    tax_codes.at[row_idx] = 'TX02'
                    tax_reasons.at[row_idx] = '영세율/수출 관련 단서'
                elif _contains_any(context, EXEMPT_KEYWORDS):
                    tax_codes.at[row_idx] = 'TX03'
                    tax_reasons.at[row_idx] = '면세 관련 단서'
                else:
                    tax_codes.at[row_idx] = 'TX01'
                    tax_reasons.at[row_idx] = '매출 계정' + (' + 같은 전표 부가세예수금' if has_output_vat else '')
                continue

            if debit > 0 and _contains_any(acct, PURCHASE_KEYWORDS):
                if _contains_any(context, NON_DEDUCTIBLE_KEYWORDS):
                    tax_codes.at[row_idx] = 'TX14'
                    tax_reasons.at[row_idx] = '불공제 매입 관련 단서'
                elif _contains_any(context, ALLOCATION_KEYWORDS):
                    tax_codes.at[row_idx] = 'TX12'
                    tax_reasons.at[row_idx] = '공통매입/안분 관련 단서'
                elif _contains_any(context, EXEMPT_KEYWORDS):
                    tax_codes.at[row_idx] = 'TX13'
                    tax_reasons.at[row_idx] = '면세 매입 관련 단서'
                else:
                    tax_codes.at[row_idx] = 'TX11'
                    tax_reasons.at[row_idx] = '매입/비용 계정' + (' + 같은 전표 부가세대급금' if has_input_vat else '')

    _add_or_replace_column(df, 'Tx코드', tax_codes, after_col=account_col)
    _add_or_replace_column(df, 'Tx분류', tax_codes.map(TAX_CODE_LABELS), after_col='Tx코드')
    _add_or_replace_column(df, 'Tx근거', tax_reasons, after_col='Tx분류')
    return df

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
    return dt.dt.weekday.isin([5, 6]) | is_holiday         # 둘 중 하나면 강조



def flag_amount_over(df, threshold):
    return (df['차변금액'] > threshold) | (df['대변금액'] > threshold)

def flag_keyword(df, keywords):
    kw_list = [k.strip() for k in keywords.split(',') if k.strip()]
    if not kw_list:
        return pd.Series(False, index=df.index)
    pattern = '|'.join(re.escape(k) for k in kw_list)
    return _text_series(df, ACCOUNT_COL_ALIASES).str.contains(pattern, na=False)

def analyze_journal(df, active_rules, rule_values):
    df = df.copy()

    # 숫자 열 안전 변환
    df['차변금액'] = _amount_series(df, DEBIT_COL_ALIASES)
    df['대변금액'] = _amount_series(df, CREDIT_COL_ALIASES)
    add_tax_codes(df)

    flags      = pd.Series(False, index=df.index)
    rule_map   = {i: [] for i in df.index}  # index → [rule 번호]

    # rule 번호는 1부터
    def add_rule(series, num):
        nonlocal flags, rule_map
        match_idx = series[series].index
        flags |= series
        for idx in match_idx:
            rule_map[idx].append(num)

    rule_num = 1
    if 'weekend_txn' in active_rules:
        add_rule(flag_weekend_txn(df), rule_num)
    rule_num += 1


    if 'amount_over' in active_rules:
        thr = float(rule_values.get('amount_over', 0))
        add_rule(flag_amount_over(df, thr), rule_num)
    rule_num += 1

    if 'keyword_search' in active_rules:
        kw = rule_values.get('keyword_search', '')
        add_rule(flag_keyword(df, kw), rule_num)

    flagged_idx = flags[flags].index.tolist()
    headers = list(df.columns)
    rows    = df.to_dict('records')

    return {
        "headers": headers,
        "rows": rows,
        "flagged_indices": flagged_idx,
        "rule_map": {str(k): v for k, v in rule_map.items()}  # JSON 직렬화 위해 str key
    }
