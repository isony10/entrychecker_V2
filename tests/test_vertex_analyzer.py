import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import app
from backend.vertex_analyzer import SheetTooLargeError, prepare_sheet_payload


class VertexPayloadTests(unittest.TestCase):
    def test_payload_contains_every_row_and_sheet_row_numbers(self):
        df = pd.DataFrame([
            {"전표번호": "A1", "계정과목": "제품매출", "대변금액": "1,000"},
            {"전표번호": "A2", "계정과목": "접대비", "차변금액": "500"},
        ])

        payload, serialized = prepare_sheet_payload(df, "sample.xlsx")

        self.assertEqual(payload["profile"]["row_count"], 2)
        self.assertEqual([row["시트행번호"] for row in payload["rows"]], [2, 3])
        self.assertEqual(payload["rows"][1]["계정과목"], "접대비")
        self.assertEqual(json.loads(serialized)["rows"], payload["rows"])

    def test_row_limit_rejects_partial_analysis(self):
        df = pd.DataFrame([{"값": 1}, {"값": 2}])

        with self.assertRaises(SheetTooLargeError):
            prepare_sheet_payload(df, "sample.xlsx", max_rows=1)

    def test_character_limit_rejects_truncation(self):
        df = pd.DataFrame([{"적요": "가" * 100}])

        with self.assertRaises(SheetTooLargeError):
            prepare_sheet_payload(df, "sample.xlsx", max_input_chars=10)


class VertexRouteTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def _file(self):
        return io.BytesIO("전표번호,계정과목,차변금액\n1,접대비,1000\n".encode("utf-8-sig"))

    @patch("backend.app.analyze_sheet_with_vertex")
    def test_route_requires_explicit_transfer_consent(self, analyze_mock):
        response = self.client.post(
            "/ai_analyze_sheet",
            data={"file": (self._file(), "sample.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        analyze_mock.assert_not_called()

    @patch("backend.app.analyze_sheet_with_vertex")
    def test_route_returns_structured_report(self, analyze_mock):
        analyze_mock.return_value = {
            "overall_risk": "중간",
            "executive_summary": "추가 검토가 필요합니다.",
            "analysis_metadata": {"analyzed_rows": 1, "model": "test-model"},
        }

        response = self.client.post(
            "/ai_analyze_sheet",
            data={
                "file": (self._file(), "sample.csv"),
                "data_transfer_consent": "true",
                "instruction": "접대비 확인",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["overall_risk"], "중간")
        args = analyze_mock.call_args.args
        self.assertEqual(len(args[0]), 1)
        self.assertEqual(args[1], "sample.csv")
        self.assertEqual(args[2], "접대비 확인")


if __name__ == "__main__":
    unittest.main()
