import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from analyzer import analyze_journal


class TaxCodeTests(unittest.TestCase):
    def analyze(self, rows):
        result = analyze_journal(pd.DataFrame(rows), [], {}, 'AND', {})
        return result, pd.DataFrame(result["rows"])

    def test_taxable_sales_with_output_vat(self):
        result, df = self.analyze([
            {"전표번호": 1, "계정과목": "외상매출금", "차변금액": 1100, "대변금액": 0},
            {"전표번호": 1, "계정과목": "제품매출", "차변금액": 0, "대변금액": 1000},
            {"전표번호": 1, "계정과목": "부가세예수금", "차변금액": 0, "대변금액": 100},
        ])

        self.assertEqual(df.loc[1, "Tx추천코드"], "TX01")
        self.assertEqual(df.loc[1, "Tx분류"], "과세매출")
        self.assertEqual(df.loc[1, "Tx신뢰도"], "90%")
        self.assertEqual(df.loc[1, "검토상태"], "미검토")
        self.assertEqual(df.loc[2, "Tx추천코드"], "TX91")
        self.assertTrue(any(r["code"] == "TX01" and r["credit_sum"] == 1000 for r in result["tax_summary"]))

    def test_zero_rate_sales(self):
        _, df = self.analyze([
            {"전표번호": 2, "계정과목": "제품매출", "적요": "수출 매출", "차변금액": 0, "대변금액": 1000},
        ])

        self.assertEqual(df.loc[0, "Tx추천코드"], "TX02")
        self.assertEqual(df.loc[0, "Tx분류"], "영세율매출")

    def test_exempt_sales(self):
        _, df = self.analyze([
            {"전표번호": 3, "계정과목": "매출", "적요": "면세 도서 판매", "차변금액": 0, "대변금액": 1000},
        ])

        self.assertEqual(df.loc[0, "Tx추천코드"], "TX03")
        self.assertEqual(df.loc[0, "Tx분류"], "면세매출")

    def test_taxable_purchase_with_input_vat(self):
        _, df = self.analyze([
            {"전표번호": 4, "계정과목": "소모품비", "차변금액": 1000, "대변금액": 0},
            {"전표번호": 4, "계정과목": "부가세대급금", "차변금액": 100, "대변금액": 0},
            {"전표번호": 4, "계정과목": "보통예금", "차변금액": 0, "대변금액": 1100},
        ])

        self.assertEqual(df.loc[0, "Tx추천코드"], "TX11")
        self.assertEqual(df.loc[0, "Tx분류"], "과세매입")
        self.assertEqual(df.loc[0, "Tx신뢰도"], "85%")
        self.assertEqual(df.loc[1, "Tx추천코드"], "TX92")

    def test_allocation_purchase(self):
        _, df = self.analyze([
            {"전표번호": 5, "계정과목": "지급수수료", "적요": "과면세 공통매입 안분", "차변금액": 1000, "대변금액": 0},
        ])

        self.assertEqual(df.loc[0, "Tx추천코드"], "TX12")
        self.assertEqual(df.loc[0, "Tx분류"], "안분매입")

    def test_exempt_purchase(self):
        _, df = self.analyze([
            {"전표번호": 6, "계정과목": "상품", "적요": "면세 농산물 매입", "차변금액": 1000, "대변금액": 0},
        ])

        self.assertEqual(df.loc[0, "Tx추천코드"], "TX13")
        self.assertEqual(df.loc[0, "Tx분류"], "면세매입")

    def test_non_deductible_purchase(self):
        _, df = self.analyze([
            {"전표번호": 7, "계정과목": "접대비", "적요": "거래처 접대", "차변금액": 1000, "대변금액": 0},
        ])

        self.assertEqual(df.loc[0, "Tx추천코드"], "TX14")
        self.assertEqual(df.loc[0, "Tx분류"], "불공제매입(과세)")

    def test_event_expense_is_taxable_purchase_candidate(self):
        _, df = self.analyze([
            {"전표번호": 8, "계정과목": "전시회비", "차변금액": 1000, "대변금액": 0},
        ])

        self.assertEqual(df.loc[0, "Tx추천코드"], "TX11")
        self.assertEqual(df.loc[0, "Tx분류"], "과세매입")

    def test_negative_purchase_is_adjustment_candidate(self):
        _, df = self.analyze([
            {"전표번호": 9, "계정과목": "지급수수료", "차변금액": -12254, "대변금액": 0},
        ])

        self.assertEqual(df.loc[0, "Tx추천코드"], "TX11")
        self.assertEqual(df.loc[0, "Tx신뢰도"], "55%")
        self.assertIn("취소/차감 가능성", df.loc[0, "Tx근거"])

    def test_non_deductible_keyword_does_not_contaminate_other_rows(self):
        _, df = self.analyze([
            {"전표번호": 10, "계정과목": "접대비", "적요": "거래처 접대", "차변금액": 1000, "대변금액": 0},
            {"전표번호": 10, "계정과목": "전시회비", "적요": "전시 부스 임차", "차변금액": 2000, "대변금액": 0},
        ])

        self.assertEqual(df.loc[0, "Tx추천코드"], "TX14")
        self.assertEqual(df.loc[1, "Tx추천코드"], "TX11")

    def test_clear_non_vat_line_has_blank_tax_fields(self):
        result, df = self.analyze([
            {"전표번호": 11, "계정과목": "보통예금", "차변금액": 1000, "대변금액": 0},
        ])

        self.assertEqual(df.loc[0, "Tx추천코드"], "")
        self.assertEqual(df.loc[0, "Tx분류"], "")
        self.assertEqual(df.loc[0, "Tx신뢰도"], "")
        self.assertEqual(df.loc[0, "Tx근거"], "")
        self.assertEqual(df.loc[0, "검토상태"], "")
        self.assertEqual(result["tax_summary"], [])


if __name__ == "__main__":
    unittest.main()
