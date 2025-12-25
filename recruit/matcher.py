"""
Job matching module
Calculates similarity between job postings and desired positions based on keywords.
"""

import difflib
from typing import List, Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobMatcher:
    """Job matching class"""
    
    def __init__(self, keywords: List[str], exclude_keywords: List[str] = None, threshold: float = 0.3):
        """
        Args:
            keywords: List of desired job keywords
            exclude_keywords: List of keywords to exclude
            threshold: Similarity threshold (0.0 ~ 1.0)
        """
        self.keywords = [kw.lower() for kw in keywords]
        self.exclude_keywords = [kw.lower() for kw in (exclude_keywords or [])]
        self.threshold = threshold
    
    def _is_korean(self, text: str) -> bool:
        """Check if text contains Korean characters"""
        return any('\uAC00' <= char <= '\uD7A3' for char in text)
    
    def calculate_similarity(self, text: str, keyword: str) -> float:
        """Calculate similarity between text and keyword"""
        text_lower = text.lower()
        keyword_lower = keyword.lower()
        
        # Exact match
        if keyword_lower in text_lower:
            return 1.0
        
        is_korean_keyword = self._is_korean(keyword_lower)
        
        # For Korean: check if all keyword words appear in text (handles spacing issues)
        if is_korean_keyword:
            keyword_words = keyword_lower.split()
            if keyword_words:
                # Check if all keyword words appear in text (with or without spaces)
                text_no_spaces = text_lower.replace(' ', '')
                keyword_no_spaces = keyword_lower.replace(' ', '')
                
                # Check exact word matches first
                text_words = set(text_lower.split())
                keyword_words_set = set(keyword_words)
                common_words = text_words & keyword_words_set
                
                # If all words match exactly, return high similarity
                if len(common_words) == len(keyword_words_set):
                    return 1.0
                
                # Check if keyword (without spaces) appears in text (without spaces)
                # This handles cases like "백엔드개발자" matching "백엔드 개발자"
                if keyword_no_spaces in text_no_spaces:
                    return 0.9
                
                # Check if all individual words appear (handling spacing variations)
                words_found = 0
                for kw_word in keyword_words:
                    if kw_word in text_lower or kw_word.replace(' ', '') in text_no_spaces:
                        words_found += 1
                
                if words_found == len(keyword_words):
                    # All words found, calculate similarity based on word match
                    word_match_ratio = len(common_words) / len(keyword_words_set) if keyword_words_set else 0
                    return max(0.7, word_match_ratio)
        
        # Partial match score using SequenceMatcher
        similarity = difflib.SequenceMatcher(None, text_lower, keyword_lower).ratio()
        
        # Word-level matching (for both Korean and English)
        text_words = set(text_lower.split())
        keyword_words = set(keyword_lower.split())
        
        if keyword_words:
            word_match_ratio = len(text_words & keyword_words) / len(keyword_words)
            similarity = max(similarity, word_match_ratio * 0.8)
        
        # For Korean: if similarity is too low and it's a false positive, reduce it
        # This helps prevent cases like "프론트엔드" matching "백엔드 개발자"
        if is_korean_keyword and similarity < 0.6:
            # Check if any keyword words actually appear in text
            keyword_words_list = keyword_lower.split()
            words_found = sum(1 for kw in keyword_words_list if kw in text_lower)
            if words_found == 0:
                # No words found, likely false positive - reduce similarity significantly
                similarity *= 0.3
        
        return similarity
    
    def should_exclude(self, text: str) -> bool:
        """Check if text contains exclude keywords"""
        text_lower = text.lower()
        for exclude_kw in self.exclude_keywords:
            if exclude_kw in text_lower:
                return True
        return False
    
    def match(self, job: Dict) -> Tuple[bool, float, str]:
        """
        Check if job posting matches desired position
        
        Returns:
            (match status, highest similarity, matched keyword)
        """
        # Check exclude keywords
        full_text = f"{job.get('title', '')} {job.get('detail', '')}"
        if self.should_exclude(full_text):
            return False, 0.0, ""
        
        # Calculate similarity with each keyword
        max_similarity = 0.0
        matched_keyword = ""
        
        for keyword in self.keywords:
            title_sim = self.calculate_similarity(job.get('title', ''), keyword)
            detail_sim = self.calculate_similarity(job.get('detail', ''), keyword)
            
            # Give higher weight to title
            similarity = max(title_sim * 1.5, detail_sim)
            
            if similarity > max_similarity:
                max_similarity = similarity
                matched_keyword = keyword
        
        # Match if similarity is above threshold
        is_matched = max_similarity >= self.threshold
        
        return is_matched, max_similarity, matched_keyword
    
    def filter_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """Filter job list to return only matched postings"""
        matched_jobs = []
        
        for job in jobs:
            is_matched, similarity, matched_keyword = self.match(job)
            
            if is_matched:
                job['similarity'] = similarity
                job['matched_keyword'] = matched_keyword
                matched_jobs.append(job)
        
        # Sort by similarity
        matched_jobs.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        
        logger.info(f"Matched {len(matched_jobs)} out of {len(jobs)} jobs")
        
        return matched_jobs

