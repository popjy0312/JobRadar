# JobRadar 🎯

한국의 주요 채용 사이트를 자동으로 모니터링하고, 원하는 키워드와 매칭되는 공고가 올라오면 알림을 보내는 Python 프로젝트입니다.

## 주요 기능

- 🔍 **자동 채용 공고 파싱**: 잡코리아, 사람인, SK Careers 등 다양한 사이트 지원
- 🌐 **SPA 사이트 지원**: JavaScript 기반 사이트도 Selenium으로 파싱
- 🎯 **스마트 매칭**: 키워드 기반 유사도 계산으로 원하는 직무와 매칭
- 🔔 **다양한 알림 방식**: 터미널 출력, 이메일, 파일 저장 지원
- ⏰ **자동 스케줄링**: 설정한 주기마다 자동으로 체크
- 📝 **중복 방지**: 이미 본 공고는 다시 알림하지 않음
- 🛠️ **Selector Helper**: 새 사이트 추가를 위한 대화형 도우미 스크립트

## 지원 사이트

| 사이트 | 방식 | 상태 |
|--------|------|------|
| 잡코리아 (JobKorea) | HTTP | ✅ |
| 사람인 (Saramin) | HTTP | ✅ |
| SK Careers | Selenium (SPA) | ✅ |
| 커스텀 사이트 | 설정 추가로 확장 가능 | ✅ |

## 설치 방법

### 1. 저장소 클론

```bash
git clone https://github.com/popjy0312/JobRadar.git
cd JobRadar
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

### 4. Chrome/Chromium 설치 (SPA 사이트용)

**SK Careers 등 JavaScript 기반 사이트를 모니터링하려면** Chrome 또는 Chromium이 필요합니다.

```bash
# Ubuntu/Debian
sudo apt-get install chromium-browser

# macOS
brew install --cask google-chrome
```

> **Note**: Chrome이 없어도 HTTP 방식 사이트(잡코리아, 사람인)는 정상 작동합니다.

## 빠른 시작

### 1. config.yaml 설정

```yaml
# 원하는 직무 키워드
job_keywords:
  - "Python"
  - "백엔드"
  - "Django"

# 제외할 키워드
exclude_keywords:
  - "인턴"
  - "신입"

# 모니터링할 사이트
sites:
  - jobkorea
  - saramin
  - skcareers
```

### 2. 실행

```bash
python main.py
```

## 설정 상세

### config.yaml 구조

```yaml
# 검색 키워드
job_keywords:
  - "모의해킹"
  - "보안"

# 제외 키워드
exclude_keywords:
  - "인턴"
  - "신입"

# 사용할 사이트 목록
sites:
  - jobkorea
  - saramin
  - skcareers

# 사이트별 상세 설정
sites_config:
  - name: "jobkorea"
    url_template: "https://www.jobkorea.co.kr/Search/?stext={keyword}"
    method: "http"
    base_url: "https://www.jobkorea.co.kr"
    selectors:
      job_list: "div[data-sentry-component='CardJob']"
      # ... 상세 설정

  - name: "skcareers"
    url_template: "https://www.skcareers.com/Recruit"
    method: "selenium"  # JavaScript 사이트
    base_url: "https://www.skcareers.com"
    search:  # SPA 검색 설정
      selector: "#SearchText"
      action: "enter"
    selectors:
      job_list: "div.list-item"
      title: "h2.title"
      company: "div.company"
      link: "a.list-link.url"
      pagination:
        type: "infinite_scroll"
        max_pages: 3

# 스케줄 설정 (한국시간 KST 기준)
schedule:
  start_time: "09:00"
  end_time: "18:00"
  interval_minutes: 60

# 알림 설정
notifications:
  terminal: true
  email:
    enabled: false
  file:
    enabled: true
    output_dir: "output"
    format: "json"

# 유사도 임계값 (0.0 ~ 1.0)
similarity_threshold: 0.3
```

### 사이트 파싱 방식

#### HTTP 방식 (일반 사이트)
정적 HTML을 반환하는 사이트에 사용합니다.

```yaml
- name: "saramin"
  url_template: "https://www.saramin.co.kr/zf_user/search/recruit?searchword={keyword}"
  method: "http"
  selectors:
    job_list: "div.item_recruit"
    title: "h2.job_tit a"
    company: "strong.corp_name a"
    link: "h2.job_tit a"
```

#### Selenium 방식 (SPA 사이트)
JavaScript로 렌더링되는 사이트에 사용합니다.

```yaml
- name: "skcareers"
  url_template: "https://www.skcareers.com/Recruit"
  method: "selenium"
  search:  # 검색창 설정 (SPA용)
    selector: "#SearchText"
    action: "enter"
  selectors:
    job_list: "div.list-item"
    title: "h2.title"
    pagination:
      type: "infinite_scroll"  # 무한 스크롤
      max_pages: 3
```

### 페이지네이션 설정

```yaml
# URL 파라미터 방식
pagination:
  param: "page"      # ?page=1, ?page=2, ...
  max_pages: 3

# 무한 스크롤 방식
pagination:
  type: "infinite_scroll"
  max_pages: 3       # 스크롤 횟수
```

## Selector Helper 사용법 🛠️

새로운 사이트를 추가할 때 CSS 선택자를 쉽게 찾을 수 있는 대화형 도우미입니다.

### 기본 사용법

```bash
python selector_helper.py "https://example.com/jobs"
```

### 실행 예시

```bash
# 일반 사이트 (URL에 검색어 포함)
python selector_helper.py "https://www.saramin.co.kr/zf_user/search/recruit?searchword=python"

# SPA 사이트 (검색창 사용)
python selector_helper.py "https://www.skcareers.com/Recruit"

# 특정 키워드로 검색 테스트
python selector_helper.py "https://www.skcareers.com/Recruit" --search "Python"
```

### 대화형 프로세스

```
=== Recruit Site Configuration Helper ===

[Step 1] Initializing Browser...
Navigating to https://www.skcareers.com/Recruit...

[Step 2] Understanding Search Method
How does search work on this site?
1. URL changes with search keyword (e.g. ?search=python)
2. Search input field without URL change (SPA)
3. No search - this is a complete static list

Select (1-3): 2

✓ SPA search mode activated.
Found Search Inputs:
[1] id='SearchText' name='SearchText' placeholder='Company, job...'
Select search input (1-2): 1

[Step 4] Identifying Job List Container
[1] Selector: div.list-item (Found 11 times)
[2] Selector: div.filter-item (Found 5 times)
Select option (0-10): 1

[Step 5] Identifying Item Details (Title, Company, Link)
...

[Step 7] Generating Configuration
------------------------------------------------------------
# Add this block to your config.yaml:
  - name: "skcareers"
    url_template: "https://www.skcareers.com/Recruit"
    method: "selenium"
    search:
      selector: "#SearchText"
      action: "enter"
    selectors:
      job_list: "div.list-item"
      title: "h2.title"
      company: "div.company"
      link: "a.list-link.url"
      pagination:
        type: "infinite_scroll"
        max_pages: 3
------------------------------------------------------------
✓ Configuration generated successfully!
```

### 생성된 설정 적용

1. 출력된 YAML 블록을 복사
2. `config.yaml`의 `sites_config` 섹션에 붙여넣기
3. `sites` 목록에 사이트 이름 추가
4. `python main.py`로 테스트

## 스케줄 설정

모든 시간은 **한국시간(KST, UTC+9)** 기준입니다.

### 방법 1: 시간 범위 + 주기 (권장)

```yaml
schedule:
  start_time: "09:00"    # 오전 9시부터
  end_time: "18:00"      # 오후 6시까지
  interval_minutes: 60   # 1시간마다
```

### 방법 2: 특정 시간대

```yaml
schedule:
  times:
    - "09:00"
    - "12:00"
    - "18:00"
```

### 방법 3: 24시간 모니터링

```yaml
schedule:
  interval_minutes: 60  # 1시간마다 (24시간)
```

## 프로젝트 구조

```
JobRadar/
├── recruit/               # 메인 패키지
│   ├── __init__.py
│   ├── parser.py          # 사이트 파서 (HTTP, Selenium)
│   ├── matcher.py         # 키워드 매칭 로직
│   ├── notifier.py        # 알림 시스템
│   └── scheduler.py       # 스케줄러
├── data/                  # 데이터 저장
│   └── job_history.json   # 중복 방지용 히스토리
├── output/                # 결과 파일 저장
├── tests/                 # 테스트 코드
├── main.py                # 메인 실행 스크립트
├── selector_helper.py     # 선택자 찾기 도우미
├── config.yaml            # 설정 파일
└── requirements.txt       # 의존성
```

## 출력 예시

```
================================================================================
🚀 새로운 채용 공고 발견! (2개)
================================================================================

[1] 보안 취약점 진단 및 모의해킹 분야 전문가
    회사: SK broadband
    링크: https://www.skcareers.com/Recruit/Detail/R252XXX
    출처: skcareers
    유사도: 92.00%
    매칭 키워드: 모의해킹

[2] Python 백엔드 개발자
    회사: (주)테크스타트업
    링크: https://www.jobkorea.co.kr/...
    출처: jobkorea
    유사도: 85.00%
    매칭 키워드: Python

================================================================================
```

## 문제 해결

### Chrome/Chromium 관련

```bash
# Chrome 설치 확인
which chromium-browser || which chromium || which google-chrome

# Ubuntu/Debian에서 설치
sudo apt-get install chromium-browser
```

### 파싱이 안 될 때

1. 사이트 구조가 변경되었을 수 있습니다
2. `selector_helper.py`로 새 선택자를 찾아보세요
3. 네트워크 연결을 확인하세요

### 이메일이 안 갈 때

1. Gmail 앱 비밀번호 확인 (일반 비밀번호 아님)
2. 2단계 인증 활성화 필요
3. SMTP 포트(587) 방화벽 확인

## 주의사항

⚠️ **사이트 정책 준수**: 각 채용 사이트의 이용약관을 확인하세요. 과도한 요청은 IP 차단을 받을 수 있습니다.

⚠️ **요청 간격**: `interval_minutes`를 최소 30분 이상으로 설정하세요.

## 라이선스

MIT License
