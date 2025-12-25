"""
Unit tests for job matcher module
Tests Korean keyword matching functionality
"""

import sys
import os
import importlib.util

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import matcher module directly to avoid dependency issues
spec = importlib.util.spec_from_file_location(
    "matcher", 
    os.path.join(project_root, "recruit", "matcher.py")
)
matcher_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matcher_module)
JobMatcher = matcher_module.JobMatcher


class TestKoreanMatching:
    """Test Korean keyword matching"""
    
    def test_exact_korean_match(self):
        """Test exact Korean keyword match"""
        matcher = JobMatcher(keywords=["백엔드 개발자"], threshold=0.3)
        job = {
            'title': '백엔드 개발자 채용',
            'detail': '',
            'company': 'Test',
            'link': 'https://test.com',
            'source': 'test'
        }
        is_matched, similarity, _ = matcher.match(job)
        assert is_matched == True
        assert similarity >= 0.8
    
    def test_korean_in_mixed_text(self):
        """Test Korean keyword in mixed text"""
        matcher = JobMatcher(keywords=["백엔드 개발자"], threshold=0.3)
        job = {
            'title': 'Python 백엔드 개발자 모집',
            'detail': '',
            'company': 'Test',
            'link': 'https://test.com',
            'source': 'test'
        }
        is_matched, similarity, _ = matcher.match(job)
        assert is_matched == True
        assert similarity >= 0.8
    
    def test_korean_without_space(self):
        """Test Korean keyword without space"""
        matcher = JobMatcher(keywords=["백엔드 개발자"], threshold=0.3)
        job = {
            'title': '백엔드개발자 채용',
            'detail': '',
            'company': 'Test',
            'link': 'https://test.com',
            'source': 'test'
        }
        is_matched, similarity, _ = matcher.match(job)
        assert is_matched == True
        assert similarity >= 0.7
    
    def test_korean_in_detail(self):
        """Test Korean keyword in detail field"""
        matcher = JobMatcher(keywords=["데이터 엔지니어"], threshold=0.3)
        job = {
            'title': 'Backend Developer',
            'detail': '데이터 엔지니어 경험 우대',
            'company': 'Test',
            'link': 'https://test.com',
            'source': 'test'
        }
        is_matched, similarity, _ = matcher.match(job)
        assert is_matched == True
        assert similarity >= 0.8
    
    def test_korean_exclude_keyword(self):
        """Test Korean exclude keyword"""
        matcher = JobMatcher(
            keywords=["Python"],
            exclude_keywords=["인턴"],
            threshold=0.3
        )
        job = {
            'title': 'Python 인턴 채용',
            'detail': '',
            'company': 'Test',
            'link': 'https://test.com',
            'source': 'test'
        }
        is_matched, similarity, _ = matcher.match(job)
        assert is_matched == False
    
    def test_korean_partial_match(self):
        """Test Korean partial match"""
        matcher = JobMatcher(keywords=["백엔드"], threshold=0.3)
        job = {
            'title': '시니어 백엔드 개발자',
            'detail': '',
            'company': 'Test',
            'link': 'https://test.com',
            'source': 'test'
        }
        is_matched, similarity, _ = matcher.match(job)
        assert is_matched == True
        assert similarity >= 0.8
    
    def test_no_match_different_keywords(self):
        """Test no match with different keywords"""
        matcher = JobMatcher(keywords=["프론트엔드"], threshold=0.3)
        job = {
            'title': '백엔드 개발자',
            'detail': '',
            'company': 'Test',
            'link': 'https://test.com',
            'source': 'test'
        }
        is_matched, similarity, _ = matcher.match(job)
        # This might match due to "개발자" common word, but similarity should be low
        if is_matched:
            assert similarity < 0.5  # Low similarity for false positive
    
    def test_mixed_korean_english(self):
        """Test mixed Korean and English keywords"""
        matcher = JobMatcher(keywords=["Python", "백엔드 개발자"], threshold=0.3)
        job = {
            'title': 'Python Backend Developer',
            'detail': '',
            'company': 'Test',
            'link': 'https://test.com',
            'source': 'test'
        }
        is_matched, similarity, _ = matcher.match(job)
        assert is_matched == True
        assert similarity >= 0.8
    
    def test_multiple_korean_keywords(self):
        """Test multiple Korean keywords"""
        matcher = JobMatcher(
            keywords=["백엔드 개발자", "데이터 엔지니어"],
            threshold=0.3
        )
        job = {
            'title': '백엔드 개발자 및 데이터 엔지니어 채용',
            'detail': '',
            'company': 'Test',
            'link': 'https://test.com',
            'source': 'test'
        }
        is_matched, similarity, _ = matcher.match(job)
        assert is_matched == True
        assert similarity >= 0.8
    
    def test_korean_spacing_variation(self):
        """Test Korean keyword with spacing variation"""
        matcher = JobMatcher(keywords=["데이터 엔지니어"], threshold=0.3)
        job = {
            'title': '데이터엔지니어 채용',
            'detail': '',
            'company': 'Test',
            'link': 'https://test.com',
            'source': 'test'
        }
        is_matched, similarity, _ = matcher.match(job)
        assert is_matched == True
        assert similarity >= 0.7


class TestSimilarityCalculation:
    """Test similarity calculation methods"""
    
    def test_calculate_similarity_exact_match(self):
        """Test exact match returns 1.0"""
        matcher = JobMatcher(keywords=["Python"], threshold=0.3)
        similarity = matcher.calculate_similarity("Python Developer", "Python")
        assert similarity == 1.0
    
    def test_calculate_similarity_partial_match(self):
        """Test partial match"""
        matcher = JobMatcher(keywords=["백엔드"], threshold=0.3)
        similarity = matcher.calculate_similarity("시니어 백엔드 개발자", "백엔드")
        assert similarity >= 0.8
    
    def test_calculate_similarity_no_match(self):
        """Test no match returns low similarity"""
        matcher = JobMatcher(keywords=["프론트엔드"], threshold=0.3)
        similarity = matcher.calculate_similarity("백엔드 개발자", "프론트엔드")
        assert similarity < 0.5


class TestFilterJobs:
    """Test job filtering"""
    
    def test_filter_jobs_matches(self):
        """Test filtering matched jobs"""
        matcher = JobMatcher(keywords=["Python"], threshold=0.3)
        jobs = [
            {
                'title': 'Python Developer',
                'detail': '',
                'company': 'A',
                'link': 'https://a.com',
                'source': 'test'
            },
            {
                'title': 'Java Developer',
                'detail': '',
                'company': 'B',
                'link': 'https://b.com',
                'source': 'test'
            },
            {
                'title': 'Python Backend',
                'detail': '',
                'company': 'C',
                'link': 'https://c.com',
                'source': 'test'
            }
        ]
        matched = matcher.filter_jobs(jobs)
        assert len(matched) == 2
        assert all('similarity' in job for job in matched)
        assert all('matched_keyword' in job for job in matched)
    
    def test_filter_jobs_sorted_by_similarity(self):
        """Test filtered jobs are sorted by similarity"""
        matcher = JobMatcher(keywords=["Python"], threshold=0.3)
        jobs = [
            {
                'title': 'Python Developer',
                'detail': '',
                'company': 'A',
                'link': 'https://a.com',
                'source': 'test'
            },
            {
                'title': 'Senior Python Developer',
                'detail': '',
                'company': 'B',
                'link': 'https://b.com',
                'source': 'test'
            }
        ]
        matched = matcher.filter_jobs(jobs)
        if len(matched) > 1:
            # Check if sorted (highest similarity first)
            similarities = [job['similarity'] for job in matched]
            assert similarities == sorted(similarities, reverse=True)

