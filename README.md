# EntryChecker: 분개장 분석 및 Tx 코드 검증 프로그램

## 1. 프로젝트 개요

**EntryChecker**는 회계감사 실무에서 주의 깊게 살펴봐야 할 분개장과 부가가치세 코드 오류를 찾는 웹 기반 분석 도구입니다.

감사인이 직접 검토 조건을 구성할 수 있는 규칙 엔진과 계정과목·적요·전표 구조를 활용한 Tx 코드 추천 및 검증 기능을 제공합니다.
선택적으로 Google Cloud Vertex AI를 연결하면 업로드한 시트의 모든 행을 AI가 종합 검토할 수 있습니다.

배포 주소: [https://entrychecker-v2.onrender.com/](https://entrychecker-v2.onrender.com/)

## 2. 주요 기능

### 규칙 기반 이상거래 분석

- 주말·공휴일 거래
- 차변 또는 대변 금액 조건
- 계정과목·적요 키워드 검색
- 거래처별 거래 횟수
- 백만원 단위 금액
- 전표세트 내 동일 계정
- 전표세트 차변·대변 불일치
- Tx 코드 검증 불일치

조건은 `AND` / `OR` 그룹으로 조합할 수 있으며, 조건에 맞는 분개만 보거나 해당 전표세트 전체를 강조할 수 있습니다.

### Tx 코드 추천

계정과목과 적요의 키워드, 같은 전표의 부가세예수금·부가세대급금 존재 여부를 바탕으로 다음 유형을 추천합니다.

- 과세매출, 영세율매출, 면세매출
- 과세매입, 안분매입, 면세매입, 불공제매입
- 매출부가세, 매입부가세

추천코드와 함께 분류, 신뢰도, 판단 근거, 검토상태를 표시합니다. 명확한 부가세 대상 외 분개에는 코드를 붙이지 않으며, 음수 금액은 취소·차감 가능성이 있는 낮은 신뢰도의 검토 대상으로 남깁니다.

### 기존 Tx 코드 검증

업로드 파일에 `부가세코드`, `Tx코드`, `세무코드`, `부가세유형`, `tax_code` 열이 있으면 원본 코드와 추천코드를 자동 대사합니다.

- 일치·불일치·추천없음 건수 요약
- 원본 코드와 수정 제시 코드를 나란히 표시
- 불일치 원본은 취소선, 수정 제시는 별도 배지로 강조
- `Tx코드 검증 불일치` 조건과 다른 감사 조건의 조합

추천 결과는 검토 보조 자료이며, 신고 또는 세무 판단 전에 증빙과 거래 사실을 확인해야 합니다.

### Vertex AI 전체 시트 분석

- 업로드한 모든 행에 원본 시트 행번호를 붙여 Gemini에 전달
- 중요 위험, 전체 패턴, Tx·부가세 검토사항과 추가 감사절차 제시
- 발견사항마다 근거 시트 행번호 표시
- JSON 스키마 기반의 일관된 분석 보고서
- 셀 내부의 문장을 명령으로 실행하지 않는 프롬프트 인젝션 방어 지침

이 기능을 실행하면 업로드 데이터가 설정된 Google Cloud 프로젝트로 전송되고 Vertex AI 사용 비용이 발생할 수 있습니다. AI 결과는 감사·세무 결론이 아닌 검토 보조자료입니다.

## 3. 사용 방법

1. 처음 접속하면 `분개장(간소).csv` 예제가 자동으로 열립니다. 다른 CSV 또는 XLSX 파일은 `분개장 불러오기`에서 선택합니다.
2. 미리보기에서 Tx 추천·검증 요약과 원본 분개를 확인합니다.
3. 좌측에서 분석 조건과 `AND` / `OR` 그룹을 구성합니다.
4. `규칙 기반 분석`을 실행합니다.
5. 강조된 분개와 Tx 불일치를 검토하고 검토상태를 기록합니다.
6. 열 제목을 클릭해 정렬하고, 제목을 드래그해 순서를 바꾸거나 오른쪽 경계선을 드래그해 너비를 조절합니다.
7. 필요한 경우 AI 분석 요청을 입력하고 데이터 전송 안내에 동의한 뒤 `AI 분석 실행`을 누릅니다. 일반 분석 로그는 좌측 하단 위쪽 패널, AI 보고서는 그 아래 전용 패널에 표시됩니다.

기본 예제 파일은 `sample/분개장(간소).csv`입니다. 실제 업무 파일은 저장소에 커밋하지 마세요.

## 4. 로컬 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m backend.app
```

브라우저에서 `http://127.0.0.1:8000/`으로 접속합니다.

### Vertex AI 설정

서비스 계정에는 필요한 최소한의 Vertex AI 호출 권한만 부여하세요. 운영 환경에서는 Secret File이나 비밀 환경변수를 사용하고, 로컬 `.env`는 Git에 올리지 않습니다.

저장소 루트의 `.env.example`을 `.env`로 복사하고 실제 값을 입력합니다. 앱은 시작할 때 `.env`를 자동으로 읽으며, `GOOGLE_SERVICE_ACCOUNT_JSON`에 한 줄로 저장된 서비스 계정 JSON을 Vertex 인증에 사용합니다. `.env`는 Git에서 제외됩니다.

```dotenv
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
VERTEX_MODEL=gemini-3.1-flash-lite
GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"your-project-id","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"service-account@your-project-id.iam.gserviceaccount.com","token_uri":"https://oauth2.googleapis.com/token"}'
```

기존 방식처럼 `GOOGLE_APPLICATION_CREDENTIALS`에 저장소 밖 JSON 파일 경로를 지정해도 계속 사용할 수 있습니다. `GOOGLE_SERVICE_ACCOUNT_JSON`이 있으면 그 값을 우선하여 인증 객체를 직접 만듭니다.

선택 안전장치:

- `VERTEX_MAX_ROWS` — 전체 분석 허용 행 수, 기본값 `20000`
- `VERTEX_MAX_INPUT_CHARS` — 모델에 보내는 JSON 최대 문자 수, 기본값 `3000000`
- AI 응답은 실행당 최대 `8192` 출력 토큰으로 제한되며, 완료 로그에 입력·출력·총 토큰 수가 표시됩니다.
- 요청은 Vertex AI Flex PayGo 전용 헤더를 사용합니다. Gemini 3.1 Flash-Lite의 `global` 엔드포인트에서 처리되며, 완료 로그의 트래픽 유형이 `ON_DEMAND_FLEX`인지 확인할 수 있습니다.

Render에서는 서비스 계정 JSON을 저장소에 커밋하지 말고 Secret File로 등록한 뒤, 그 파일 경로를 `GOOGLE_APPLICATION_CREDENTIALS`에 설정합니다. `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `VERTEX_MODEL`도 Render 환경변수로 등록합니다.

## 5. 테스트

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
```
