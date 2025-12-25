# 채용 공고 모니터링 시스템

한국의 주요 채용 사이트(잡코리아, 사람인, 원티드)를 자동으로 모니터링하고, 원하는 직무와 매칭되는 공고가 올라오면 알림을 보내는 Python 프로젝트입니다.

## 주요 기능

- 🔍 **자동 채용 공고 파싱**: 잡코리아, 사람인, 원티드에서 자동으로 공고 수집
- 🎯 **스마트 매칭**: 키워드 기반 유사도 계산으로 원하는 직무와 매칭
- 🔔 **다양한 알림 방식**: 터미널 출력, 이메일 알림 지원
- ⏰ **자동 스케줄링**: 설정한 주기마다 자동으로 체크
- 📝 **중복 방지**: 이미 본 공고는 다시 알림하지 않음

## 설치 방법

### 1. 저장소 클론 및 디렉토리 이동

```bash
cd /home/qq/recruit
```

### 2. 가상 환경 생성 (권장)

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. Chrome 브라우저 설치 (선택사항)

**원티드(Wanted) 사이트를 사용하려면** Chrome 또는 Chromium 브라우저가 필요합니다.

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install chromium-browser
# 또는
sudo apt-get install chromium
```

#### Linux (WSL)
```bash
# WSL에서는 GUI 브라우저가 없으므로 headless 모드로 작동합니다
sudo apt-get update
sudo apt-get install chromium-browser
```

#### macOS
```bash
brew install --cask google-chrome
```

#### Windows
[Chrome 다운로드 페이지](https://www.google.com/chrome/)에서 설치

## 설정 방법

### 1. config.yaml 설정

`config.yaml` 파일을 열어서 다음을 설정하세요:

```yaml
# 원하는 직무 키워드
job_keywords:
  - "Python"
  - "백엔드 개발자"
  - "Django"
  - "Flask"

# 제외할 키워드
exclude_keywords:
  - "인턴"
  - "신입만"

# 모니터링할 사이트
sites:
  - jobkorea
  - saramin
  - wanted

# 스케줄 설정 (한국시간 KST 기준)
schedule:
  # 방법 1: 특정 시간에만 체크
  # times:
  #   - "09:00"
  #   - "12:00"
  #   - "15:00"
  #   - "18:00"
  
  # 방법 2: 시간 범위와 주기로 체크 (권장)
  start_time: "09:00"      # 시작 시간 (KST)
  end_time: "18:00"        # 종료 시간 (KST)
  interval_minutes: 60     # 체크 주기 (분 단위)
  
  # 방법 3: 24시간 주기로 체크
  # interval_minutes: 60

# 알림 설정
notifications:
  terminal: true  # 터미널 출력
  email:
    enabled: true  # 이메일 알림 활성화
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    from_email: "your_email@gmail.com"
    to_email: "recipient@gmail.com"
    password: "your_app_password"  # Gmail 앱 비밀번호
```

### 2. 환경 변수 설정 (선택사항)

이메일 설정을 환경 변수로 관리하려면 `.env` 파일을 생성하세요:

```bash
cp .env.example .env
```

`.env` 파일을 편집:

```
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=recipient@gmail.com
```

**Gmail 앱 비밀번호 생성 방법:**
1. Google 계정 설정 → 보안
2. 2단계 인증 활성화
3. 앱 비밀번호 생성
4. 생성된 비밀번호를 `EMAIL_PASSWORD`에 입력

## 사용 방법

### 기본 실행

```bash
python main.py
```

프로그램이 실행되면:
1. 설정한 스케줄에 따라 자동으로 채용 사이트를 체크합니다
2. 매칭되는 새로운 공고가 발견되면 터미널에 출력하고 이메일로 알림을 보냅니다
3. `Ctrl+C`로 종료할 수 있습니다

### 스케줄 설정 방법

#### 방법 1: 특정 시간에만 체크
```yaml
schedule:
  times:
    - "09:00"  # 오전 9시
    - "12:00"  # 정오
    - "15:00"  # 오후 3시
    - "18:00"  # 오후 6시
```

#### 방법 2: 시간 범위와 주기로 체크 (권장)
```yaml
schedule:
  start_time: "09:00"      # 오전 9시부터
  end_time: "18:00"        # 오후 6시까지
  interval_minutes: 60     # 1시간마다 체크
```

이 설정은 **한국시간(KST, UTC+9) 기준**으로 작동합니다.

#### 방법 3: 24시간 주기로 체크
```yaml
schedule:
  interval_minutes: 60  # 1시간마다 체크 (24시간)
```

### 일회성 실행 (스케줄링 없이)

```python
from recruit import JobScheduler
import yaml

with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

scheduler = JobScheduler(config)
scheduler.check_jobs()  # 한 번만 체크
```

## 출력 예시

```
================================================================================
🚀 새로운 채용 공고 발견! (3개)
================================================================================

[1] Python 백엔드 개발자 채용
    회사: (주)테크스타트업
    링크: https://www.jobkorea.co.kr/...
    출처: jobkorea
    유사도: 85.00%
    매칭 키워드: Python
    상세: Python, Django, REST API...

[2] 백엔드 개발자 (Django)
    회사: 스타트업B
    링크: https://www.saramin.co.kr/...
    출처: saramin
    유사도: 72.50%
    매칭 키워드: 백엔드 개발자
    상세: Django, PostgreSQL...

================================================================================
```

## 프로젝트 구조

```
recruit/
├── recruit/            # 메인 패키지
│   ├── __init__.py    # 패키지 초기화
│   ├── parser.py      # 채용 사이트 파서
│   ├── matcher.py     # 직무 매칭 로직
│   ├── notifier.py    # 알림 시스템
│   └── scheduler.py   # 스케줄러 모듈
├── tests/             # 테스트 코드 (선택사항)
│   └── __init__.py
├── main.py            # 메인 실행 스크립트
├── config.yaml        # 설정 파일
├── requirements.txt   # 패키지 의존성
├── .env.example       # 환경 변수 예시
├── .gitignore
└── README.md
```

## 커스터마이징

### 새로운 채용 사이트 추가

코드를 수정하지 않고 `config.yaml`에 설정만 추가하면 새로운 사이트를 모니터링할 수 있습니다.

**모든 사이트(기본 사이트 포함)는 동일한 방식으로 설정됩니다.**

#### 설정 방법

`config.yaml`의 `sites_config` 섹션에 사이트를 추가하세요:

##### 방법 1: 간단한 선택자 (Simple Strategy)

일반적인 사이트에 적합합니다:

```yaml
sites_config:
  - name: "mysite"
    url_template: "https://example.com/search?q={keyword}"
    method: "http"
    base_url: "https://example.com"
    selectors:
      job_list: "div.job-item"
      title: "a.job-title"
      company: "span.company-name"
      link: "a.job-title"
      detail: "p.job-detail"  # 선택사항
```

##### 방법 2: 구조적 추출 (Structured Strategy)

복잡한 DOM 구조나 CSS-in-JS를 사용하는 사이트에 적합합니다:

```yaml
sites_config:
  - name: "complexsite"
    url_template: "https://example.com/search?q={keyword}"
    method: "http"
    base_url: "https://example.com"
    selectors:
      job_list: "div[data-component='JobCard']"
      extraction:
        strategy: "structured"
        # 링크 필터 설정
        link_filter:
          selector: "a[href*='/jobs/']"  # 기본 선택자
          has_child: "span[data-element='Typography']"  # Typography 자식이 있는 링크만
          not_has_attribute:
            name: "data-component"
            value: "CompanyLogo"  # 로고 링크 제외
        title:
          link_index: 0  # 첫 번째 링크
          span_selector: "span[data-element='Typography']"
          class_pattern: "size18"  # 클래스에 포함된 패턴
        company:
          link_index: 1  # 두 번째 링크
          span_selector: "span[data-element='Typography']"
          class_pattern: "size16"
          max_length: 50  # 회사명 최대 길이
      detail: ""
```

**구조적 추출 옵션:**
- `link_filter`: 링크 필터 설정 (dictionary)
  - `selector`: 기본 CSS 선택자
  - `has_child`: 특정 자식 요소가 있는 경우만 (CSS 선택자)
  - `not_has_child`: 특정 자식 요소가 없는 경우만
  - `has_attribute`: 특정 속성이 있는 경우만 (문자열 또는 {name, value})
  - `not_has_attribute`: 특정 속성이 없거나 값이 다른 경우만
  - `has_text`: 특정 텍스트를 포함하는 경우만
  - `not_has_text`: 특정 텍스트를 포함하지 않는 경우만
- `title.link_index`: 제목이 있는 링크의 인덱스 (0부터 시작)
- `title.span_selector`: 링크 내부의 span 선택자
- `title.class_pattern`: 클래스명에 포함될 패턴 (예: "size18")
- `company.*`: 회사명도 동일한 방식으로 설정

**간단한 필터 예시:**
```yaml
# 단순 선택자만 사용 (하위 호환)
link_filter: "a[href*='/jobs/']"

# 자식 요소 체크
link_filter:
  selector: "a[href*='/jobs/']"
  has_child: "span.title"

# 여러 조건 조합
link_filter:
  selector: "a"
  has_child: "h3"
  not_has_text: "광고"
  has_attribute:
    name: "data-job-id"
```

#### 예시 1: HTTP 방식 (일반 사이트)

```yaml
sites_config:
  - name: "techjob"
    url_template: "https://techjob.com/search?keyword={keyword}"
    method: "http"
    base_url: "https://techjob.com"
    selectors:
      job_list: "div.job-card"
      title: "h3.job-title"
      company: "span.company"
      link: "a.job-link"
      detail: "p.description"
```

#### 예시 2: Selenium 방식 (JavaScript 사이트)

```yaml
sites_config:
  - name: "modernsite"
    url_template: "https://modernsite.com/jobs?search={keyword}"
    method: "selenium"  # JavaScript로 동적 렌더링되는 사이트
    base_url: "https://modernsite.com"
    selectors:
      job_list: "div[data-testid='job-card']"
      title: "h2.job-title"
      company: "div.company-name"
      link: "a.job-link"
```

#### CSS 선택자 찾는 방법

1. 브라우저에서 사이트 열기
2. F12 (개발자 도구) 열기
3. Elements 탭에서 원하는 요소 선택
4. 우클릭 → Copy → Copy selector

#### 주의사항

- `name`은 고유해야 합니다
- `url_template`에서 `{keyword}`는 자동으로 검색 키워드로 대체됩니다
- `method: "selenium"` 사용 시 Chrome/Chromium이 필요합니다
- 선택자가 정확하지 않으면 공고를 찾지 못할 수 있습니다
- 기본 사이트(jobkorea, saramin, wanted)도 `sites_config`에서 설정을 변경할 수 있습니다

### 알림 방식 추가

`recruit/notifier.py`에 새로운 알림 메서드를 추가하고 `notify()` 메서드에서 호출하세요.

예: Slack, Discord, Telegram 등

## 주의사항

1. **사이트 정책 준수**: 각 채용 사이트의 이용약관을 확인하고 준수하세요. 과도한 요청은 IP 차단을 받을 수 있습니다.
2. **요청 간격**: `interval_minutes`를 너무 짧게 설정하지 마세요 (최소 30분 권장).
3. **Chrome 브라우저**: JavaScript 기반 사이트 파싱을 위해 Chrome/Chromium이 필요합니다. 없어도 다른 사이트는 정상 작동합니다.
4. **시간대 설정**: 스케줄은 한국시간(KST, UTC+9) 기준으로 작동합니다.

## 문제 해결

### 파싱이 안 될 때
- 사이트 구조가 변경되었을 수 있습니다. 파서 코드를 업데이트해야 할 수 있습니다.
- 네트워크 연결을 확인하세요.

### 이메일이 안 갈 때
- Gmail 앱 비밀번호가 올바른지 확인하세요.
- 2단계 인증이 활성화되어 있는지 확인하세요.
- 방화벽에서 SMTP 포트(587)가 차단되지 않았는지 확인하세요.

## 라이선스

이 프로젝트는 개인 사용 목적으로 만들어졌습니다.

