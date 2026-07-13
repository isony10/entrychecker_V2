"""잘못된 TX코드 검증 규칙(wrong_tax_code) 자체 검증 스크립트.

sample/검증데이터.csv 에는 규칙별로 일부러 심은 오류 전표와, 걸리면 안 되는
정상 전표(오탐 방지)가 들어 있다. 각 행의 '예상 결과'를 실제 검출 결과와
대조해 PASS/FAIL을 출력한다.

실행:  python3 verify_tax_codes.py
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from analyzer import analyze_journal  # noqa: E402

# 행 순서대로 기대하는 TX검증 사유의 부분 문자열. '' 이면 '걸리면 안 됨'.
EXPECTED = [
    ('N1 정상 과세매출 - 외상매출금', ''),
    ('N1 정상 과세매출 - 제품매출', ''),
    ('N1 정상 과세매출 - 부가세예수금', ''),
    ('S-A 매출세액 누락 - 외상매출금', ''),
    ('S-A 매출세액 누락 - 제품매출', '부가세예수금 라인 없음'),
    ('S-B 매출세액 불일치 - 외상매출금', ''),
    ('S-B 매출세액 불일치 - 제품매출', ''),
    ('S-B 매출세액 불일치 - 부가세예수금', '매출세액 불일치'),
    ('S-C 대응매출 없음 - 보통예금', ''),
    ('S-C 대응매출 없음 - 부가세예수금', '과세매출 없음'),
    ('P-A 매입세액 누락 - 소모품비', '부가세대급금 라인 없음'),
    ('P-A 매입세액 누락 - 보통예금', ''),
    ('P-B 매입세액 불일치 - 상품', ''),
    ('P-B 매입세액 불일치 - 부가세대급금', '매입세액 불일치'),
    ('P-B 매입세액 불일치 - 외상매입금', ''),
    ('P-C 대응매입 없음 - 부가세대급금', '과세매입 없음'),
    ('P-C 대응매입 없음 - 보통예금', ''),
    ('N3 채권 회수(오탐방지) - 보통예금', ''),
    ('N3 채권 회수(오탐방지) - 외상매출금', ''),
    ('N4 면세매출(정상) - 현금', ''),
    ('N4 면세매출(정상) - 제품매출', ''),
    ('N5 부가세 0원 라인(정상) - 미수금', ''),
    ('N5 부가세 0원 라인(정상) - 교육수입', ''),
    ('N5 부가세 0원 라인(정상) - 부가세예수금', ''),
    ('G 그룹핑 2/1 정상 - 외상매출금', ''),
    ('G 그룹핑 2/1 정상 - 제품매출', ''),
    ('G 그룹핑 2/1 정상 - 부가세예수금', ''),
    ('G 그룹핑 2/2 세액누락 - 외상매출금', ''),
    ('G 그룹핑 2/2 세액누락 - 제품매출', '부가세예수금 라인 없음'),
]


def main():
    csv_path = os.path.join(os.path.dirname(__file__), 'sample', '검증데이터.csv')
    df = pd.read_csv(csv_path)

    result = analyze_journal(df, ['wrong_tax_code'], {})
    rows = result['rows']

    assert len(rows) == len(EXPECTED), (
        f'행 수 불일치: CSV {len(rows)} vs 기대 {len(EXPECTED)}')

    header = f'{"#":>2} {"판정":<4} {"시나리오":<34} {"Tx":<5} {"검출된 TX검증"}'
    print(header)
    print('-' * len(header) * 2)

    passed = failed = 0
    for i, (desc, expect) in enumerate(EXPECTED):
        actual = rows[i].get('TX검증', '') or ''
        tx = rows[i].get('Tx코드', '')
        if expect:
            ok = expect in actual              # 걸려야 하고, 사유가 맞아야 함
        else:
            ok = (actual == '')                # 걸리면 안 됨
        passed += ok
        failed += (not ok)
        mark = 'PASS' if ok else 'FAIL'
        print(f'{i:>2} {mark:<4} {desc:<34} {tx:<5} {actual}')

    print('-' * len(header) * 2)
    total = passed + failed
    print(f'결과: {passed}/{total} PASS' + ('' if failed == 0 else f', {failed} FAIL'))
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
