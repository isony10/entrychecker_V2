import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from analyzer import analyze_journal


class TaxCodeTests(unittest.TestCase):
    def analyze(self, rows):
        result = analyze_journal(pd.DataFrame(rows), [], {}, 'AND', {})
        return pd.DataFrame(result["rows"])

    def test_taxable_sales_with_output_vat(self):
        df = self.analyze([
            {"전표번호": 1, "계정과목": "외상매출금", "차변금액": 1100, "대변금액": 0},
            {"전표번호": 1, "계정과목": "제품매출", "차변금액": 0, "대변금액": 1000},
            {"전표번호": 1, "계정과목": "부가세예수금", "차변금액": 0, "대변금액": 100},
        ])

        self.assertEqual(df.loc[1, "Tx코드"], "TX01")
        self.assertEqual(df.loc[1, "Tx분류"], "과세매출")
        self.assertEqual(df.loc[2, "Tx코드"], "TX91")

    def test_zero_rate_sales(self):
        df = self.analyze([
            {"전표번호": 2, "계정과목": "제품매출", "적요": "수출 매출", "차변금액": 0, "대변금액": 1000},
        ])

        self.assertEqual(df.loc[0, "Tx코드"], "TX02")
        self.assertEqual(df.loc[0, "Tx분류"], "영세율매출")

    def test_exempt_sales(self):
        df = self.analyze([
            {"전표번호": 3, "계정과목": "매출", "적요": "면세 도서 판매", "차변금액": 0, "대변금액": 1000},
        ])

        self.assertEqual(df.loc[0, "Tx코드"], "TX03")
        self.assertEqual(df.loc[0, "Tx분류"], "면세매출")

    def test_taxable_purchase_with_input_vat(self):
        df = self.analyze([
            {"전표번호": 4, "계정과목": "소모품비", "차변금액": 1000, "대변금액": 0},
            {"전표번호": 4, "계정과목": "부가세대급금", "차변금액": 100, "대변금액": 0},
            {"전표번호": 4, "계정과목": "보통예금", "차변금액": 0, "대변금액": 1100},
        ])

        self.assertEqual(df.loc[0, "Tx코드"], "TX11")
        self.assertEqual(df.loc[0, "Tx분류"], "과세매입")
        self.assertEqual(df.loc[1, "Tx코드"], "TX92")

    def test_allocation_purchase(self):
        df = self.analyze([
            {"전표번호": 5, "계정과목": "지급수수료", "적요": "과면세 공통매입 안분", "차변금액": 1000, "대변금액": 0},
        ])

        self.assertEqual(df.loc[0, "Tx코드"], "TX12")
        self.assertEqual(df.loc[0, "Tx분류"], "안분매입")

    def test_exempt_purchase(self):
        df = self.analyze([
            {"전표번호": 6, "계정과목": "상품", "적요": "면세 농산물 매입", "차변금액": 1000, "대변금액": 0},
        ])

        self.assertEqual(df.loc[0, "Tx코드"], "TX13")
        self.assertEqual(df.loc[0, "Tx분류"], "면세매입")

    def test_non_deductible_purchase(self):
        df = self.analyze([
            {"전표번호": 7, "계정과목": "접대비", "적요": "거래처 접대", "차변금액": 1000, "대변금액": 0},
        ])

        self.assertEqual(df.loc[0, "Tx코드"], "TX14")
        self.assertEqual(df.loc[0, "Tx분류"], "불공제매입(과세)")


if __name__ == "__main__":
    unittest.main()
