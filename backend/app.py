import sys
import os
from flask import Flask, request, render_template, jsonify, Response
import pandas as pd
import math
import json

if __name__ == "__main__":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.analyzer import analyze_journal
from backend.vertex_analyzer import (
    VertexAnalysisError,
    VertexConfigurationError,
    analyze_sheet_with_vertex,
)

app = Flask(__name__,
            static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'static'),
            template_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates'))

@app.route('/')
def index():
    return render_template('index.html')

def clean_nan(obj):
    if isinstance(obj, dict): return {k: clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean_nan(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)): return None
    return obj

def read_file_to_df(file):
    filename = file.filename
    lower_name = filename.lower()
    if lower_name.endswith('.csv'):
        enc_try = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']
        for enc in enc_try:
            try:
                file.seek(0)
                # dtype=str 옵션을 추가하여 모든 데이터를 문자열로 읽어옵니다.
                df = pd.read_csv(file, encoding=enc, sep=None, engine='python', dtype=str).fillna('')
                if not df.empty and len(df.columns) > 0: return df
            except Exception: continue
        raise ValueError("CSV 파일을 읽는 데 실패했습니다. 인코딩 또는 구분자를 확인해주세요.")
    elif lower_name.endswith(('.xls', '.xlsx')):
        file.seek(0)
        # dtype=str 옵션을 추가하여 모든 데이터를 문자열로 읽어옵니다.
        return pd.read_excel(file, engine='openpyxl', dtype=str).fillna('')
    else:
        raise ValueError("지원하지 않는 파일 형식입니다. CSV 또는 Excel 파일을 업로드해주세요.")
@app.route('/preview', methods=['POST'])
def preview():
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다.'}), 400
    file = request.files['file']
    try:
        df = read_file_to_df(file)
        analyzed = analyze_journal(df, [], {}, 'AND', {})
        headers = analyzed['headers']
        rows = analyzed['rows']
        result = {'headers': headers, 'rows': rows, 'tax_summary': analyzed.get('tax_summary', []), 'tax_validation': analyzed.get('tax_validation')}
        cleaned = clean_nan(result)
        return Response(json.dumps(cleaned, ensure_ascii=False), mimetype='application/json')
    except Exception as e:
        return jsonify({'error': f'파일 파싱 오류: {str(e)}'}), 400

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files: return "파일이 없습니다.", 400
    file = request.files['file']
    try:
        active_rules = json.loads(request.form['active_rules'])
        rule_values = json.loads(request.form['values'])
        logic_op = request.form.get('logic_op', 'AND')
        logic_tree = json.loads(request.form.get('logic_tree', '{}'))
        df = read_file_to_df(file)
        result = analyze_journal(df, active_rules, rule_values, logic_op, logic_tree)
        cleaned = clean_nan(result)
        return Response(json.dumps(cleaned, ensure_ascii=False), mimetype='application/json')
    except Exception as e:
        return f"분석 중 오류 발생: {str(e)}", 500


@app.route('/ai_analyze_sheet', methods=['POST'])
def ai_analyze_sheet():
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다.'}), 400
    if request.form.get('data_transfer_consent') != 'true':
        return jsonify({'error': 'Vertex AI 데이터 전송 확인이 필요합니다.'}), 400
    instruction = request.form.get('instruction', '').strip()
    if not instruction:
        return jsonify({'error': 'AI에게 요청할 분석 내용을 입력해주세요.'}), 400

    file = request.files['file']
    try:
        df = read_file_to_df(file)
        report = analyze_sheet_with_vertex(
            df,
            file.filename,
            instruction,
        )
        return jsonify(clean_nan(report))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except VertexConfigurationError as e:
        return jsonify({'error': str(e)}), 503
    except VertexAnalysisError as e:
        return jsonify({'error': str(e)}), 502

if __name__ == '__main__':
    # 호스트를 '0.0.0.0'으로 지정해야 클라우드 호스팅 환경에서 외부 접근이 가능하다
    app.run(host='0.0.0.0', debug=True, port=8000)
