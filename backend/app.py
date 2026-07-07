import os
from flask import Flask, request, render_template, jsonify
from flask import Response
import pandas as pd
import math
import json
from analyzer import analyze_journal

app = Flask(__name__,
            static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'static'),
            template_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates'))

@app.route('/')
def index():
    return render_template('index.html')

# NaN 제거 함수
def clean_nan(obj):
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj

@app.route('/analyze', methods=['POST'])
def analyze():
    file = request.files['file']
    filename = file.filename
    active_rules = json.loads(request.form['active_rules'])
    rule_values = json.loads(request.form['values'])

    try:
        lower_name = filename.lower()
        if lower_name.endswith('.csv'):
            last_error = None
            for encoding in ('utf-8-sig', 'cp949', 'euc-kr'):
                try:
                    file.seek(0)
                    df = pd.read_csv(file, encoding=encoding)
                    break
                except UnicodeDecodeError as exc:
                    last_error = exc
            else:
                raise last_error or ValueError("CSV encoding could not be detected")
        elif lower_name.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file, engine='openpyxl')
        else:
            return "Unsupported file type", 400

        result = analyze_journal(df, active_rules, rule_values)
        cleaned = clean_nan(result)

        return Response(json.dumps(cleaned, ensure_ascii=False), mimetype='application/json')

    except Exception as e:
        return f"File read error: {str(e)}", 400

if __name__ == '__main__':
    app.run(debug=True, port=8000)
