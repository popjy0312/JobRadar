#!/usr/bin/env python3
"""
Parser debugging script
Tests and debugs site parsers to identify issues

Usage:
    python -m pytest tests/test_parser_debug.py::test_parser_debug -v
    python tests/test_parser_debug.py jobkorea --keyword "Python"
"""

import sys
import os
import yaml
from urllib.parse import urlparse, quote

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import parser classes directly without importing selenium-dependent code
import requests
from bs4 import BeautifulSoup
import yaml as yaml_lib

# Simple HTTP parser for debugging (without selenium dependency)
# This mimics the actual parser logic
class DebugHttpParser:
    def __init__(self, config):
        self.name = config.get('name', 'unknown')
        self.url_template = config.get('url_template', '')
        self.selectors = config.get('selectors', {})
        self.base_url = config.get('base_url', '')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def _extract_structured(self, job_elem, extraction_config):
        """Mimic structured extraction from parser.py"""
        link_filter = extraction_config.get('link_filter', '')
        link_filter_condition = extraction_config.get('link_filter_condition', '')
        
        if link_filter:
            all_links = job_elem.select(link_filter)
        else:
            all_links = job_elem.select('a')
        
        text_links = []
        for link in all_links:
            if link_filter_condition == 'has_typography':
                typo_spans = link.select('span[data-sentry-element="Typography"]')
                if typo_spans:
                    text_links.append(link)
            elif link_filter_condition == 'not_logo':
                if link.get('data-sentry-component') != 'CompanyLogo':
                    text_links.append(link)
            else:
                text_links.append(link)
        
        # Extract title
        title_config = extraction_config.get('title', {})
        title_elem = None
        link_elem = None
        
        title_link_index = title_config.get('link_index', 0)
        if len(text_links) > title_link_index:
            title_link = text_links[title_link_index]
            link_elem = title_link
            
            span_selector = title_config.get('span_selector', '')
            class_pattern = title_config.get('class_pattern', '')
            
            if span_selector:
                title_spans = title_link.select(span_selector)
                if title_spans:
                    if class_pattern:
                        for span in title_spans:
                            classes = ' '.join(span.get('class', []))
                            if class_pattern in classes:
                                title_elem = span
                                break
                        if not title_elem:
                            title_elem = title_spans[0]
                    else:
                        title_elem = title_spans[0]
                else:
                    title_elem = title_link
            else:
                title_elem = title_link
        
        # Extract company
        company_config = extraction_config.get('company', {})
        company_elem = None
        
        company_link_index = company_config.get('link_index', 1)
        if len(text_links) > company_link_index:
            company_link = text_links[company_link_index]
            
            span_selector = company_config.get('span_selector', '')
            class_pattern = company_config.get('class_pattern', '')
            max_length = company_config.get('max_length', 50)
            
            if span_selector:
                company_spans = company_link.select(span_selector)
                if company_spans:
                    if class_pattern:
                        for span in company_spans:
                            classes = ' '.join(span.get('class', []))
                            text = span.get_text(strip=True)
                            if class_pattern in classes and text and len(text) < max_length:
                                company_elem = span
                                break
                        if not company_elem:
                            for span in company_spans:
                                text = span.get_text(strip=True)
                                if text and len(text) < max_length:
                                    company_elem = span
                                    break
                        if not company_elem:
                            company_elem = company_spans[0]
                    else:
                        for span in company_spans:
                            text = span.get_text(strip=True)
                            if text and len(text) < max_length:
                                company_elem = span
                                break
                        if not company_elem:
                            company_elem = company_spans[0] if company_spans else None
                else:
                    company_elem = company_link
            else:
                company_elem = company_link
        
        if not title_elem:
            return None
        
        title = title_elem.get_text(strip=True)
        company = company_elem.get_text(strip=True) if company_elem else "Unknown"
        link = link_elem.get('href', '') if link_elem else ''
        
        if link and not link.startswith('http'):
            if self.base_url:
                link = f"{self.base_url.rstrip('/')}/{link.lstrip('/')}"
        
        return {
            'title': title,
            'company': company,
            'link': link,
            'detail': '',
            'source': self.name
        }
    
    def parse(self, keyword):
        jobs = []
        if not self.url_template:
            return jobs
        
        search_url = self.url_template.replace('{keyword}', keyword)
        try:
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            job_list_selector = self.selectors.get('job_list', '')
            if job_list_selector:
                job_list = soup.select(job_list_selector)
                
                # Check for structured extraction
                extraction_config = self.selectors.get('extraction', {})
                strategy = extraction_config.get('strategy', 'simple')
                
                for job in job_list[:10]:
                    try:
                        if strategy == 'structured':
                            job_data = self._extract_structured(job, extraction_config)
                        else:
                            # Simple extraction
                            title_selector = self.selectors.get('title', '')
                            company_selector = self.selectors.get('company', '')
                            link_selector = self.selectors.get('link', title_selector)
                            detail_selector = self.selectors.get('detail', '')
                            
                            title_elem = job.select_one(title_selector) if title_selector else None
                            company_elem = job.select_one(company_selector) if company_selector else None
                            link_elem = job.select_one(link_selector) if link_selector else None
                            
                            if title_elem:
                                title = title_elem.get_text(strip=True)
                                company = company_elem.get_text(strip=True) if company_elem else "Unknown"
                                link = link_elem.get('href', '') if link_elem else ''
                                
                                if link and not link.startswith('http'):
                                    if self.base_url:
                                        link = f"{self.base_url.rstrip('/')}/{link.lstrip('/')}"
                                
                                detail = ""
                                if detail_selector:
                                    detail_elem = job.select_one(detail_selector)
                                    if detail_elem:
                                        detail = detail_elem.get_text(strip=True)
                                
                                job_data = {
                                    'title': title,
                                    'company': company,
                                    'link': link,
                                    'detail': detail,
                                    'source': self.name
                                }
                            else:
                                job_data = None
                        
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        print(f"   Error parsing job item: {e}")
                        continue
            
            return jobs
        except Exception as e:
            print(f"Error: {e}")
            return jobs


def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(project_root, 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def test_url_accessibility(url: str):
    """Test if URL is accessible"""
    print(f"\n{'='*80}")
    print(f"Testing URL Accessibility")
    print(f"{'='*80}")
    print(f"URL: {url}")
    
    import requests
    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.content)} bytes")
        print(f"Content Type: {response.headers.get('Content-Type', 'Unknown')}")
        
        if response.status_code == 200:
            print("✓ URL is accessible")
            return True, response
        else:
            print(f"✗ URL returned status {response.status_code}")
            return False, response
    except Exception as e:
        print(f"✗ Error accessing URL: {e}")
        return False, None


def analyze_html_structure(html_content: str, site_name: str, selectors: dict):
    """Analyze HTML structure and test selectors"""
    print(f"\n{'='*80}")
    print(f"Analyzing HTML Structure for: {site_name}")
    print(f"{'='*80}")
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Save HTML to file for inspection
    # Always save debug HTML in the same directory as this test file
    debug_file = os.path.join(os.path.dirname(__file__), f"debug_{site_name}_html.html")
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    print(f"✓ HTML saved to: {debug_file}")
    
    # Test each selector
    print(f"\nTesting Selectors:")
    print("-" * 80)
    
    job_list_selector = selectors.get('job_list', '')
    if job_list_selector:
        print(f"\n1. Job List Selector: '{job_list_selector}'")
        job_list = soup.select(job_list_selector)
        print(f"   Found {len(job_list)} elements")
        
        if len(job_list) == 0:
            print(f"   ✗ No elements found! Trying alternative selectors...")
            
            # Try common alternatives
            alternatives = [
                'div.list-post',
                'div[class*="list"]',
                'div[class*="job"]',
                'div[class*="post"]',
                'li.job-item',
                'div.job-item',
                'article',
                'div.card',
                'div[class*="recruit"]',
                'div[class*="search"]',
                'ul.list',
                'ol.list'
            ]
            
            found_alternatives = []
            for alt in alternatives:
                test = soup.select(alt)
                if len(test) > 0:
                    found_alternatives.append((alt, len(test)))
                    print(f"   → Alternative '{alt}' found {len(test)} elements")
            
            # If alternatives found, analyze the first one
            if found_alternatives:
                best_alt, count = found_alternatives[0]
                print(f"\n   Analyzing best alternative: '{best_alt}' ({count} elements)")
                test_elements = soup.select(best_alt)
                if test_elements:
                    first_elem = test_elements[0]
                    print(f"   First element structure:")
                    print(f"     Tag: <{first_elem.name}>")
                    print(f"     Classes: {first_elem.get('class', [])}")
                    print(f"     ID: {first_elem.get('id', 'None')}")
                    print(f"     HTML preview: {str(first_elem)[:200]}...")
                    
                    # Try to find title and company in this element
                    print(f"\n   Looking for title/company in this element:")
                    title_candidates = first_elem.select('a, h1, h2, h3, h4, span, div')
                    for i, candidate in enumerate(title_candidates[:5]):
                        text = candidate.get_text(strip=True)
                        if text and len(text) > 5:
                            classes = '.'.join(candidate.get('class', []))
                            print(f"     [{i+1}] <{candidate.name}.{classes}>: {text[:50]}...")
        
        if len(job_list) > 0:
            print(f"   ✓ Found job list container")
            print(f"   First element classes: {job_list[0].get('class', [])}")
            print(f"   First element tag: {job_list[0].name}")
            
            # Test child selectors on first job item
            first_job = job_list[0]
            print(f"\n   Testing selectors on first job item:")
            
            title_selector = selectors.get('title', '')
            if title_selector:
                title_elem = first_job.select_one(title_selector)
                if title_elem:
                    print(f"   ✓ Title selector '{title_selector}': '{title_elem.get_text(strip=True)[:50]}...'")
                else:
                    print(f"   ✗ Title selector '{title_selector}': Not found")
                    # Try to find title-like elements
                    title_like = first_job.select('a, h1, h2, h3, h4, span[class*="title"]')
                    if title_like:
                        print(f"   → Found {len(title_like)} title-like elements")
                        for i, elem in enumerate(title_like[:3]):
                            print(f"     [{i+1}] {elem.name}.{'.'.join(elem.get('class', []))}: {elem.get_text(strip=True)[:30]}...")
            
            company_selector = selectors.get('company', '')
            if company_selector:
                company_elem = first_job.select_one(company_selector)
                if company_elem:
                    print(f"   ✓ Company selector '{company_selector}': '{company_elem.get_text(strip=True)[:50]}...'")
                else:
                    print(f"   ✗ Company selector '{company_selector}': Not found")
            
            link_selector = selectors.get('link', title_selector)
            if link_selector:
                link_elem = first_job.select_one(link_selector)
                if link_elem:
                    href = link_elem.get('href', '')
                    print(f"   ✓ Link selector '{link_selector}': '{href[:50]}...'")
                else:
                    print(f"   ✗ Link selector '{link_selector}': Not found")
    else:
        print("✗ Job list selector not configured")
    
    # Show page structure
    print(f"\nPage Structure Analysis:")
    print("-" * 80)
    
    # Count common elements
    divs = soup.find_all('div')
    print(f"Total <div> elements: {len(divs)}")
    
    # Find elements with common job-related classes
    job_keywords = ['job', 'post', 'list', 'item', 'card', 'recruit']
    for keyword in job_keywords:
        elements = soup.find_all(class_=lambda x: x and keyword.lower() in ' '.join(x).lower())
        if elements:
            print(f"Elements with '{keyword}' in class: {len(elements)}")
            if len(elements) > 0:
                sample = elements[0]
                print(f"  Sample: <{sample.name} class=\"{' '.join(sample.get('class', []))}\">")
    
    return soup


def test_parser(site_name: str, keyword: str = "Python"):
    """Test parser for a specific site"""
    print(f"\n{'='*80}")
    print(f"Testing Parser: {site_name}")
    print(f"{'='*80}")
    
    # Load config
    config = load_config()
    sites_config = config.get('sites_config', [])
    
    # Find site config
    site_config = None
    for s in sites_config:
        if s.get('name', '').lower() == site_name.lower():
            site_config = s
            break
    
    if not site_config:
        print(f"✗ Site '{site_name}' not found in sites_config")
        return
    
    print(f"Site Config:")
    print(f"  Name: {site_config.get('name')}")
    print(f"  Method: {site_config.get('method')}")
    print(f"  URL Template: {site_config.get('url_template')}")
    print(f"  Selectors: {site_config.get('selectors')}")
    
    # Build search URL
    url_template = site_config.get('url_template', '')
    search_url = url_template.replace('{keyword}', keyword)
    
    print(f"\nSearch URL: {search_url}")
    
    # Test URL accessibility
    accessible, response = test_url_accessibility(search_url)
    
    if not accessible:
        print(f"\n✗ Cannot proceed - URL not accessible")
        return
    
    # Analyze HTML if HTTP method
    if site_config.get('method') == 'http':
        print(f"\nAnalyzing HTML structure...")
        soup = analyze_html_structure(response.text, site_name, site_config.get('selectors', {}))
    
    # Test actual parser (simplified version for debugging)
    print(f"\n{'='*80}")
    print(f"Testing Parser (Simplified)")
    print(f"{'='*80}")
    
    if site_config.get('method') == 'selenium':
        print(f"⚠ Selenium parser - skipping (requires Chrome)")
        print(f"  To test Selenium parser, install Chrome and run main.py")
    else:
        try:
            parser = DebugHttpParser(site_config)
            jobs = parser.parse(keyword)
            print(f"\nResults:")
            print(f"  Found {len(jobs)} jobs")
            
            if len(jobs) > 0:
                print(f"\nFirst {min(3, len(jobs))} jobs:")
                for i, job in enumerate(jobs[:3], 1):
                    print(f"\n  [{i}]")
                    for key, value in job.items():
                        print(f"    {key}: {str(value)[:80]}")
            else:
                print(f"\n✗ No jobs found!")
                print(f"\nPossible issues:")
                print(f"  1. Selectors might be incorrect (check HTML structure above)")
                print(f"  2. Site structure might have changed")
                print(f"  3. Site might require JavaScript (use method: 'selenium')")
                print(f"  4. Site might be blocking requests")
                print(f"  5. Check the saved HTML file: tests/debug_{site_name}_html.html")
            
        except Exception as e:
            print(f"\n✗ Error during parsing: {e}")
            import traceback
            traceback.print_exc()


def compare_with_browser(site_name: str, keyword: str = "Python"):
    """Compare parser results with manual browser check"""
    print(f"\n{'='*80}")
    print(f"Manual Verification Guide")
    print(f"{'='*80}")
    
    config = load_config()
    sites_config = config.get('sites_config', [])
    
    site_config = None
    for s in sites_config:
        if s.get('name', '').lower() == site_name.lower():
            site_config = s
            break
    
    if not site_config:
        return
    
    url_template = site_config.get('url_template', '')
    search_url = url_template.replace('{keyword}', keyword)
    
    print(f"\n1. Open this URL in your browser:")
    print(f"   {search_url}")
    print(f"\n2. Open Developer Tools (F12)")
    print(f"\n3. Check the following selectors:")
    
    selectors = site_config.get('selectors', {})
    for key, selector in selectors.items():
        print(f"   {key}: {selector}")
        print(f"      → In Console, run: document.querySelectorAll('{selector}').length")
    
    print(f"\n4. Compare the structure with saved HTML file:")
    print(f"   debug_{site_name}_html.html")


def test_parser_debug():
    """Pytest-compatible test function"""
    print("="*80)
    print("Parser Debugging Tool")
    print("="*80)
    test_parser('jobkorea', 'Python')


def main():
    """Main debugging function (for command-line usage)"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Debug site parsers')
    parser.add_argument('site', nargs='?', default='jobkorea', 
                       help='Site name to debug (default: jobkorea)')
    parser.add_argument('--keyword', '-k', default='Python',
                       help='Search keyword (default: Python)')
    parser.add_argument('--compare', '-c', action='store_true',
                       help='Show manual verification guide')
    
    args = parser.parse_args()
    
    print("="*80)
    print("Parser Debugging Tool")
    print("="*80)
    
    if args.compare:
        compare_with_browser(args.site, args.keyword)
    else:
        test_parser(args.site, args.keyword)
        print(f"\n{'='*80}")
        print(f"Tip: Run with --compare to see manual verification guide")
        print(f"Example: python tests/test_parser_debug.py {args.site} --compare")
        print(f"{'='*80}")


if __name__ == '__main__':
    main()

