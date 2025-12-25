# Tests 디렉토리

이 디렉토리는 프로젝트의 **단위 테스트(Unit Tests)**와 **통합 테스트(Integration Tests)**를 저장하는 곳입니다.

## 목적

1. **코드 검증**: 각 모듈이 예상대로 작동하는지 확인
2. **회귀 방지**: 코드 변경 시 기존 기능이 깨지지 않았는지 확인
3. **문서화**: 테스트 코드가 각 함수의 사용 예시 역할
4. **리팩토링 안전성**: 코드 개선 시 안전하게 변경 가능

## 테스트 파일 구조

```
tests/
├── __init__.py          # 테스트 패키지 초기화
├── test_matcher.py      # JobMatcher 테스트
├── test_parser.py       # Parser 테스트 (추후 추가)
├── test_notifier.py     # Notifier 테스트 (추후 추가)
└── test_scheduler.py    # Scheduler 테스트 (추후 추가)
```

## 테스트 실행 방법

### pytest 사용 (권장)

```bash
# 모든 테스트 실행
pytest tests/

# 특정 테스트 파일만 실행
pytest tests/test_matcher.py

# 특정 테스트 클래스만 실행
pytest tests/test_matcher.py::TestKoreanMatching

# 특정 테스트 메서드만 실행
pytest tests/test_matcher.py::TestKoreanMatching::test_exact_korean_match

# 상세 출력
pytest tests/ -v

# 커버리지 확인
pytest tests/ --cov=recruit
```

### Python으로 직접 실행

```bash
python -m pytest tests/
```

## 테스트 작성 가이드

### 기본 구조

```python
class TestClassName:
    """Test class description"""
    
    def test_method_name(self):
        """Test method description"""
        # Arrange (준비)
        matcher = JobMatcher(keywords=["Python"], threshold=0.3)
        
        # Act (실행)
        result = matcher.match(job)
        
        # Assert (검증)
        assert result == expected
```

### 네이밍 규칙

- 테스트 파일: `test_*.py`
- 테스트 클래스: `Test*`
- 테스트 메서드: `test_*`

### Best Practices

1. **독립성**: 각 테스트는 독립적으로 실행 가능해야 함
2. **명확성**: 테스트 이름이 무엇을 테스트하는지 명확해야 함
3. **단순성**: 한 테스트는 한 가지를 테스트
4. **빠른 실행**: 테스트는 빠르게 실행되어야 함

## 현재 테스트

- ✅ `test_matcher.py`: 한국어 매칭 기능 테스트
- ✅ `test_parser_debug.py`: 파서 디버깅 도구

## 추가 예정

- ⏳ `test_parser.py`: 파서 기능 테스트 (pytest 형식)
- ⏳ `test_notifier.py`: 알림 기능 테스트
- ⏳ `test_scheduler.py`: 스케줄러 기능 테스트

## 디버깅 도구

### 파서 디버깅

파서가 제대로 작동하지 않을 때 사용:

```bash
# 특정 사이트 디버깅
python tests/test_parser_debug.py jobkorea --keyword "Python"

# 모든 사이트 테스트
python tests/test_parser_debug.py saramin --keyword "백엔드"

# 수동 검증 가이드 보기
python tests/test_parser_debug.py jobkorea --compare
```

이 스크립트는:
- URL 접근성 확인
- HTML 구조 분석
- 선택자 테스트
- 실제 파서 실행
- 디버그 HTML 파일 저장 (`debug_*.html`)

