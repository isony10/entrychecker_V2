import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import app
from backend.vertex_analyzer import (
    FLEX_HEADERS,
    MANUAL_AI_ANALYSIS_INSTRUCTIONS,
    MAX_OUTPUT_TOKENS,
    REPORT_SCHEMA,
    SERVICE_TIER,
    SheetTooLargeError,
    VertexConfigurationError,
    _load_service_account_info,
    _token_usage,
    build_system_instruction,
    load_vertex_config,
    prepare_sheet_payload,
)


class VertexPayloadTests(unittest.TestCase):
    def test_manual_instructions_are_included_in_system_instruction(self):
        combined = build_system_instruction()

        self.assertIn(MANUAL_AI_ANALYSIS_INSTRUCTIONS, combined)
        self.assertIn("같은 전표번호를 가진 모든 행은 하나의 전표세트", combined)
        self.assertIn("전체 행의 차변금액 합계와 대변금액 합계", combined)
        self.assertIn("시트 행번호", combined)
        self.assertIn("'행'이라는 단어", combined)
        self.assertIn("전표번호만 사용", combined)

    def test_finding_schema_uses_voucher_numbers_instead_of_row_numbers(self):
        finding_schema = REPORT_SCHEMA["properties"]["findings"]["items"]

        self.assertIn("voucher_numbers", finding_schema["properties"])
        self.assertIn("voucher_numbers", finding_schema["required"])
        self.assertNotIn("row_numbers", finding_schema["properties"])

    def test_default_model_is_supported_vertex_model(self):
        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "test-project"}, clear=True):
            self.assertEqual(load_vertex_config().model, "gemini-3.1-flash-lite")

    def test_output_token_limit_is_8192(self):
        self.assertEqual(MAX_OUTPUT_TOKENS, 8192)

    def test_service_tier_is_flex_paygo(self):
        self.assertEqual(SERVICE_TIER, "flex")
        self.assertEqual(FLEX_HEADERS["X-Vertex-AI-LLM-Request-Type"], "shared")
        self.assertEqual(
            FLEX_HEADERS["X-Vertex-AI-LLM-Shared-Request-Type"],
            "flex",
        )

    def test_project_can_come_from_service_account_json(self):
        credentials_json = json.dumps(
            {
                "project_id": "json-project",
                "private_key": "test-key",
                "client_email": "test@example.com",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
        with patch.dict(
            "os.environ",
            {"GOOGLE_SERVICE_ACCOUNT_JSON": credentials_json},
            clear=True,
        ):
            self.assertEqual(load_vertex_config().project, "json-project")
            self.assertEqual(_load_service_account_info()["client_email"], "test@example.com")

    def test_invalid_service_account_json_has_clear_error(self):
        with patch.dict(
            "os.environ",
            {"GOOGLE_SERVICE_ACCOUNT_JSON": "not-json"},
            clear=True,
        ):
            with self.assertRaisesRegex(VertexConfigurationError, "올바른 JSON"):
                load_vertex_config()

    def test_token_usage_is_extracted_from_vertex_response(self):
        response = SimpleNamespace(
            usage_metadata=SimpleNamespace(
                prompt_token_count=120,
                candidates_token_count=80,
                total_token_count=200,
                traffic_type=SimpleNamespace(value="ON_DEMAND_FLEX"),
            )
        )

        self.assertEqual(
            _token_usage(response),
            {
                "prompt_tokens": 120,
                "output_tokens": 80,
                "total_tokens": 200,
                "traffic_type": "ON_DEMAND_FLEX",
            },
        )

    def test_payload_contains_every_row_without_sheet_row_numbers(self):
        df = pd.DataFrame([
            {"전표번호": "A1", "계정과목": "제품매출", "대변금액": "1,000"},
            {"전표번호": "A2", "계정과목": "접대비", "차변금액": "500"},
        ])

        payload, serialized = prepare_sheet_payload(df, "sample.xlsx")

        self.assertEqual(payload["profile"]["row_count"], 2)
        self.assertTrue(all("시트행번호" not in row for row in payload["rows"]))
        self.assertEqual([row["전표번호"] for row in payload["rows"]], ["A1", "A2"])
        self.assertEqual(payload["rows"][1]["계정과목"], "접대비")
        self.assertEqual(json.loads(serialized)["rows"], payload["rows"])

    def test_voucher_balance_groups_rows_with_the_same_voucher_number(self):
        df = pd.DataFrame([
            {"전표일자": "2024-01-01", "전표번호": "A1", "차변금액": "100", "대변금액": "0"},
            {"전표일자": "2024-01-02", "전표번호": "A1", "차변금액": "20", "대변금액": "120"},
            {"전표일자": "2024-01-03", "전표번호": "A2", "차변금액": "100", "대변금액": "0"},
            {"전표일자": "2024-01-03", "전표번호": "A2", "차변금액": "0", "대변금액": "90"},
        ])

        payload, _ = prepare_sheet_payload(df, "sample.xlsx")
        balance = payload["profile"]["voucher_balance"]

        self.assertEqual(balance["voucher_set_count"], 2)
        self.assertEqual(balance["balanced_set_count"], 1)
        self.assertEqual(balance["unbalanced_set_count"], 1)
        self.assertEqual(
            balance["unbalanced_sets"],
            [{
                "voucher_number": "A2",
                "debit_sum": 100.0,
                "credit_sum": 90.0,
                "difference": 10.0,
            }],
        )

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

    def test_default_sample_is_served_and_previewable(self):
        sample_response = self.client.get('/sample/default')

        self.assertEqual(sample_response.status_code, 200)
        self.assertIn('text/csv', sample_response.content_type)
        sample_bytes = sample_response.data
        sample_response.close()

        preview_response = self.client.post(
            '/preview',
            data={
                'file': (
                    io.BytesIO(sample_bytes),
                    '분개장(간소).csv',
                ),
            },
            content_type='multipart/form-data',
        )
        payload = preview_response.get_json()

        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(len(payload['rows']), 31)
        self.assertIn('전표일자', payload['headers'])

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
    def test_route_requires_ai_instruction(self, analyze_mock):
        response = self.client.post(
            "/ai_analyze_sheet",
            data={
                "file": (self._file(), "sample.csv"),
                "data_transfer_consent": "true",
                "instruction": "   ",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"],
            "AI에게 요청할 분석 내용을 입력해주세요.",
        )
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
