#!/usr/bin/env python3
"""
Selector Helper Script
----------------------
Analyzes job posting websites to interactively generate CSS selectors for config.yaml.

This script helps you configure new job sites by:
1. Loading the URL in a headless Chrome browser
2. Detecting the page structure (static HTML, SPA, search mechanism)
3. Analyzing repeated elements to find job list containers
4. Guiding you to select title, company, and link selectors
5. Generating a ready-to-use YAML configuration block

Features:
- Supports both HTTP and Selenium-based parsing
- Detects CSS-in-JS and prioritizes stable selectors (data-* attributes)
- Handles URL-based search, SPA search, and static job lists
- Analyzes DOM hierarchy to identify outermost containers
- Supports various pagination types (URL params, infinite scroll, none)

Usage:
    python selector_helper.py <URL> [--search KEYWORD]

Examples:
    # Standard job site
    python selector_helper.py "https://www.saramin.co.kr/zf_user/search/recruit?searchword=python"

    # SPA with search functionality
    python selector_helper.py "https://www.skcareers.com/Recruit" --search "SK"

    # Modern CSS-in-JS site
    python selector_helper.py "https://toss.im/career/jobs"
"""

import sys
import os
import time
import logging
import argparse
from collections import Counter
from urllib.parse import urlparse
from typing import List, Tuple, Optional, Dict
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from webdriver_manager.chrome import ChromeDriverManager

try:
    from webdriver_manager.core.os_manager import ChromeType
except ImportError:
    ChromeType = None

# ==================== Constants ====================
DEFAULT_SEARCH_KEYWORD = "Python"
INITIAL_LOAD_WAIT = 3
SEARCH_RESULT_WAIT = 5
SCROLL_WAIT = 2
MIN_ITEM_COUNT = 3
MAX_ITEM_COUNT = 500  # Increased to support large job lists (e.g., 200+ postings)
MAX_CANDIDATES_DISPLAY = 15

# ==================== Color Output ====================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== UI Helper Functions ====================
def print_header(text: str):
    """Print a header with formatting."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {text} ==={Colors.ENDC}")

def print_step(step: int, text: str):
    """Print a step indicator."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}[Step {step}] {text}{Colors.ENDC}")

def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")

def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.WARNING}! {text}{Colors.ENDC}")

def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def safe_int_input(prompt: str, min_val: int, max_val: int) -> Optional[int]:
    """Safely get integer input from user within a range."""
    while True:
        try:
            value = input(prompt).strip()
            if not value:
                continue
            num = int(value)
            if min_val <= num <= max_val:
                return num
            print(f"Please enter a number between {min_val} and {max_val}.")
        except ValueError:
            print("Please enter a valid number.")
        except KeyboardInterrupt:
            return None

def safe_choice_input(prompt: str, valid_choices: List[str]) -> Optional[str]:
    """Safely get a choice from user."""
    while True:
        try:
            choice = input(prompt).strip()
            if choice in valid_choices:
                return choice
            print(f"Please enter one of: {', '.join(valid_choices)}")
        except KeyboardInterrupt:
            return None

# ==================== Selenium Driver Management ====================
def init_driver() -> Optional[webdriver.Chrome]:
    """Initialize Selenium driver with robust detection."""
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        chrome_options.add_argument("--log-level=3")
        
        import shutil
        chrome_type = None
        
        # Detect Chromium/Chrome
        if not shutil.which('google-chrome') and not shutil.which('google-chrome-stable'):
            if shutil.which('chromium-browser') or shutil.which('chromium'):
                if ChromeType:
                    chrome_type = ChromeType.CHROMIUM
                
                binary_path = shutil.which('chromium-browser') or shutil.which('chromium')
                if binary_path:
                    chrome_options.binary_location = binary_path

        # Special handling for Snap Chromium
        if chrome_type == ChromeType.CHROMIUM and os.path.exists('/snap/bin/chromium'):
            if os.path.exists('/snap/bin/chromium.chromedriver'):
                service = Service('/snap/bin/chromium.chromedriver')
                return webdriver.Chrome(service=service, options=chrome_options)
            
            import glob
            snap_drivers = glob.glob('/snap/chromium/*/usr/lib/chromium-browser/chromedriver')
            if snap_drivers:
                service = Service(snap_drivers[0])
                return webdriver.Chrome(service=service, options=chrome_options)

        if chrome_type:
            driver_path = ChromeDriverManager(chrome_type=chrome_type).install()
        else:
            driver_path = ChromeDriverManager().install()
            
        # Fix for WDM returning non-binary files
        if os.path.basename(driver_path) != 'chromedriver':
            driver_dir = os.path.dirname(driver_path)
            potential_binary = os.path.join(driver_dir, 'chromedriver')
            if os.path.exists(potential_binary):
                driver_path = potential_binary
        
        try:
            os.chmod(driver_path, 0o755)
        except Exception:
            pass
            
        service = Service(driver_path)
        return webdriver.Chrome(service=service, options=chrome_options)
        
    except Exception as e:
        print_error(f"Failed to initialize driver: {e}")
        return None

# ==================== Selector Generation ====================
def is_css_in_js_class(class_name: str) -> bool:
    """Detect if a class name is generated by CSS-in-JS (e.g., .css-xxxxx, .sc-xxxxx)."""
    import re
    # Common CSS-in-JS patterns: css-xxxxx, sc-xxxxx, emotion-xxxxx, jss-xxxxx
    patterns = [r'^css-[a-z0-9]+$', r'^sc-[a-z0-9]+$', r'^emotion-[a-z0-9]+$',
                r'^jss-[0-9]+$', r'^makeStyles-[a-zA-Z]+-[0-9]+$']
    return any(re.match(pattern, class_name) for pattern in patterns)

def has_stable_data_attrs(element) -> bool:
    """Check if element has stable data-* attributes."""
    if not element:
        return False
    attrs = element.attrs
    # Look for data-* attributes (excluding empty values)
    data_attrs = [k for k in attrs.keys() if k.startswith('data-') and attrs[k]]
    return len(data_attrs) > 0

def get_css_selector(element, prefer_data_attrs: bool = True) -> str:
    """
    Generate a CSS selector for a BeautifulSoup element.

    Priority:
    1. ID (if exists)
    2. data-* attributes (if prefer_data_attrs=True and stable)
    3. Semantic/stable classes (excluding CSS-in-JS hashes)
    4. Tag name
    """
    if not element:
        return ""

    # Prefer ID
    if element.get('id'):
        return f"#{element.get('id')}"

    # Prefer data-* attributes for stability
    if prefer_data_attrs and has_stable_data_attrs(element):
        # Find most specific data attribute
        data_attrs = [(k, v) for k, v in element.attrs.items()
                      if k.startswith('data-') and v and v not in ['true', 'false', '']]
        if data_attrs:
            # Use first meaningful data attribute
            attr_name, attr_value = data_attrs[0]
            if isinstance(attr_value, list):
                attr_value = attr_value[0]
            return f"{element.name}[{attr_name}='{attr_value}']"

    # Use class (but filter CSS-in-JS hashes)
    classes = element.get('class')
    if classes:
        valid_classes = [c for c in classes
                        if not c.startswith('ng-')
                        and not c.startswith('vue-')
                        and not c.isdigit()
                        and not is_css_in_js_class(c)]

        if valid_classes:
            return f"{element.name}.{'.'.join(valid_classes)}"

        # If only CSS-in-JS classes exist, warn user but still provide selector
        css_in_js_classes = [c for c in classes if is_css_in_js_class(c)]
        if css_in_js_classes:
            print_warning(f"Element uses CSS-in-JS classes: {', '.join(css_in_js_classes[:3])}")
            print_warning("These selectors may break if styles change. Consider using data-* attributes.")
            return f"{element.name}.{'.'.join(css_in_js_classes)}"

    # Fallback to tag name
    return element.name

# ==================== Search Input Detection ====================
def find_search_inputs(driver: webdriver.Chrome) -> List[Tuple[WebElement, str]]:
    """Find all visible search input elements on the page."""
    inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='search']")
    
    valid_inputs = []
    for inp in inputs:
        try:
            if inp.is_displayed():
                placeholder = inp.get_attribute('placeholder') or "No placeholder"
                name = inp.get_attribute('name') or "No name"
                uid = inp.get_attribute('id') or "No ID"
                desc = f"id='{uid}' name='{name}' placeholder='{placeholder}'"
                valid_inputs.append((inp, desc))
        except Exception:
            continue
    
    return valid_inputs

def select_search_input(driver: webdriver.Chrome) -> Optional[Tuple[WebElement, str]]:
    """Let user select a search input from candidates."""
    print("\nScanning for search inputs...")
    valid_inputs = find_search_inputs(driver)
    
    if not valid_inputs:
        print_warning("No visible inputs found automatically.")
        return None
    
    print(f"\n{Colors.CYAN}Found Search Inputs:{Colors.ENDC}")
    for i, (_, desc) in enumerate(valid_inputs):
        print(f"[{i+1}] {desc}")
    print(f"[{len(valid_inputs)+1}] None of these (Manual Selector)")
    
    choice = safe_int_input(f"Select search input (1-{len(valid_inputs)+1}): ", 
                           1, len(valid_inputs)+1)
    if choice is None:
        return None
    
    if choice == len(valid_inputs) + 1:
        return None  # Manual entry needed
    
    return valid_inputs[choice-1]

def get_input_selector(element: WebElement) -> str:
    """Generate CSS selector for an input element."""
    if element.get_attribute('id'):
        return f"#{element.get_attribute('id')}"
    
    # Fallback: parse HTML and generate
    html = element.get_attribute('outerHTML')
    soup = BeautifulSoup(html, 'lxml')
    return get_css_selector(soup.body.next_element if soup.body else soup)

def perform_search(driver: webdriver.Chrome, input_elem: WebElement, 
                  keyword: str) -> bool:
    """Type keyword into search input and submit."""
    try:
        print(f"\nSimulating search: Typing '{keyword}'...")
        input_elem.clear()
        input_elem.send_keys(keyword)
        input_elem.send_keys(Keys.RETURN)
        print(f"Pressed Enter. Waiting {SEARCH_RESULT_WAIT}s for results...")
        time.sleep(SEARCH_RESULT_WAIT)
        return True
    except Exception as e:
        print_error(f"Search simulation failed: {e}")
        return False

# ==================== SPA Detection ====================
def detect_spa_indicators(soup: BeautifulSoup, driver: webdriver.Chrome) -> Dict[str, any]:
    """
    Detect if a page is likely an SPA by analyzing various indicators.
    
    Returns:
        Dict with keys:
        - is_spa: bool
        - confidence: float (0.0 - 1.0)
        - reasons: List[str]
    """
    indicators = []
    score = 0.0
    
    # 1. Check for common SPA frameworks in scripts
    scripts = soup.find_all('script', src=True)
    spa_frameworks = ['react', 'vue', 'angular', 'next.js', 'nuxt']
    for script in scripts:
        src = script.get('src', '').lower()
        for fw in spa_frameworks:
            if fw in src:
                indicators.append(f"Detected {fw} framework")
                score += 0.3
                break
    
    # 2. Check for minimal HTML content (skeleton loading)
    body = soup.find('body')
    if body:
        text_content = body.get_text(strip=True)
        tags_count = len(body.find_all(True))
        
        # Minimal content suggests SPA shell
        if len(text_content) < 500 and tags_count < 20:
            indicators.append("Minimal initial HTML (likely SPA shell)")
            score += 0.4
    
    # 3. Check for app root containers
    spa_root_selectors = ['#app', '#root', '[data-reactroot]', '[ng-app]', '[v-cloak]']
    for sel in spa_root_selectors:
        if soup.select_one(sel):
            indicators.append(f"Found SPA root: {sel}")
            score += 0.3
            break
    
    # 4. Check JavaScript execution impact
    # Compare static HTML vs rendered content
    try:
        static_text_length = len(soup.get_text(strip=True))
        rendered_text_length = len(driver.find_element(By.TAG_NAME, 'body').text.strip())
        
        if rendered_text_length > static_text_length * 1.5:
            indicators.append("Content significantly increased after JS execution")
            score += 0.5
    except Exception:
        pass
    
    # 5. Check for search inputs (indirect indicator)
    search_inputs = find_search_inputs(driver)
    if search_inputs:
        indicators.append(f"Found {len(search_inputs)} search input(s)")
        # Don't add score, but it's a useful signal
    
    confidence = min(score, 1.0)
    is_spa = confidence > 0.5
    
    return {
        'is_spa': is_spa,
        'confidence': confidence,
        'reasons': indicators
    }

# ==================== Job List Detection ====================
def find_job_list_candidates(soup: BeautifulSoup) -> List[Tuple[str, str, int]]:
    """
    Find potential job list container candidates by analyzing DOM.

    Improvements:
    - Prioritize elements with data-* attributes
    - Filter out CSS-in-JS-only elements
    - Require meaningful text content
    - Better scoring heuristics
    - Exclude non-job elements (navigation, articles, UI components)
    """
    # Patterns to exclude (not job postings)
    EXCLUDE_PATTERNS = [
        'nav', 'navbar', 'navigation', 'menu', 'header', 'footer',
        'sidebar', 'breadcrumb', 'pagination', 'filter', 'search',
        'button', 'input', 'select', 'dropdown', 'checkbox',
        'tab', 'accordion', 'modal', 'popup', 'tooltip',
        'banner', 'ad', 'advertisement', 'cookie', 'consent'
    ]

    # Text patterns that suggest non-job content
    EXCLUDE_TEXT_PATTERNS = [
        '전체 보기', 'view all', 'see more', 'load more',
        'terms', 'privacy', 'cookie', 'contact',
        'about', 'faq', 'help', 'support'
    ]

    def should_exclude_element(tag, text: str, classes: list) -> bool:
        """Check if element should be excluded from candidates."""
        # Check tag name
        if tag.name in ['nav', 'header', 'footer', 'aside', 'button', 'input', 'select']:
            return True

        # Check class names
        if classes:
            class_str = ' '.join(classes).lower()
            if any(pattern in class_str for pattern in EXCLUDE_PATTERNS):
                return True

        # Check text content
        text_lower = text.lower()
        if any(pattern in text_lower for pattern in EXCLUDE_TEXT_PATTERNS):
            return True

        # Check data attributes
        data_attrs = {k: v for k, v in tag.attrs.items() if k.startswith('data-')}
        if data_attrs:
            attr_str = ' '.join([f"{k}={v}" for k, v in data_attrs.items()]).lower()
            if any(pattern in attr_str for pattern in EXCLUDE_PATTERNS):
                return True

        return False

    # First pass: collect all elements with their signatures
    class_based_candidates = []
    data_based_candidates = []
    css_in_js_candidates = []  # Separate list for CSS-in-JS (lower priority)

    for tag in soup.find_all(True):
        classes = tag.get('class')
        text = tag.get_text(strip=True)

        # Skip elements with no meaningful content (increased minimum)
        if len(text) < 20:
            continue

        # Skip elements with too much content (likely containers, not items)
        if len(text) > 500:
            continue

        # Skip excluded elements
        if should_exclude_element(tag, text, classes or []):
            continue

        # Prioritize data-* attribute based elements
        data_attrs = [k for k in tag.attrs.keys() if k.startswith('data-')]
        if data_attrs:
            # Use data attribute as signature
            for attr in data_attrs[:1]:  # Use first data attr
                attr_val = tag.get(attr)
                if attr_val and attr_val not in ['true', 'false', '']:
                    sig = f"{tag.name}[{attr}='{attr_val}']"
                    data_based_candidates.append(sig)
                    break

        # Class-based candidates (secondary)
        if classes:
            # Filter out CSS-in-JS classes for stable candidates
            stable_classes = [c for c in classes if not is_css_in_js_class(c)]
            css_in_js_classes_found = [c for c in classes if is_css_in_js_class(c)]

            if stable_classes:
                sig = f"{tag.name}.{'.'.join(stable_classes)}"
                class_based_candidates.append(sig)
            elif css_in_js_classes_found:
                # Include CSS-in-JS as fallback (with first class only)
                sig = f"{tag.name}.{css_in_js_classes_found[0]}"
                css_in_js_candidates.append(sig)

    # Count occurrences
    data_counter = Counter(data_based_candidates)
    class_counter = Counter(class_based_candidates)
    css_in_js_counter = Counter(css_in_js_candidates)

    potential_lists = []

    # Prioritize data-* based candidates
    for sig, count in data_counter.most_common(30):
        if MIN_ITEM_COUNT <= count <= MAX_ITEM_COUNT:
            example = soup.select_one(sig)
            text = example.get_text(strip=True)[:100] if example else ""
            if text:  # Ensure example has content
                potential_lists.append((sig, text, count))

    # Add class-based candidates (if data-* candidates are insufficient)
    for sig, count in class_counter.most_common(50):
        if MIN_ITEM_COUNT <= count <= MAX_ITEM_COUNT:
            tag_name, class_str = sig.split('.', 1)
            selector = f"{tag_name}.{'.'.join(class_str.split('.'))}"
            example = soup.select_one(selector)
            text = example.get_text(strip=True)[:100] if example else ""
            if text:  # Ensure example has content
                potential_lists.append((sig, text, count))

    # Add CSS-in-JS candidates (last resort, with warning)
    for sig, count in css_in_js_counter.most_common(30):
        if MIN_ITEM_COUNT <= count <= MAX_ITEM_COUNT:
            example = soup.select_one(sig)
            text = example.get_text(strip=True)[:100] if example else ""
            if text:  # Ensure example has content
                # Add warning prefix to text
                potential_lists.append((sig, f"⚠ CSS-in-JS: {text}", count))

    # Heuristic scoring
    def score_candidate(item):
        sig, text, count = item
        score = 0

        # CSS-in-JS penalty (mark but don't exclude)
        is_css_in_js = '⚠ CSS-in-JS:' in text
        if is_css_in_js:
            score -= 10  # Lower priority but still available
            text = text.replace('⚠ CSS-in-JS: ', '')  # Clean for other checks

        # Tag name heuristics
        if 'li' in sig.lower(): score += 5
        if 'article' in sig.lower(): score += 10

        # Class/attribute name heuristics (job-related keywords)
        sig_lower = sig.lower()
        if 'item' in sig_lower: score += 10
        if 'list' in sig_lower: score += 5
        if 'card' in sig_lower: score += 10
        if 'recruit' in sig_lower: score += 20
        if 'job' in sig_lower: score += 20
        if 'position' in sig_lower: score += 20
        if 'posting' in sig_lower: score += 20
        if 'opening' in sig_lower: score += 15
        if 'vacancy' in sig_lower: score += 15
        if 'career' in sig_lower: score += 10

        # Data attribute bonus
        if sig.startswith('[') or 'data-' in sig: score += 20

        # Text content patterns (job postings usually have specific patterns)
        text_lower = text.lower()

        # Positive patterns in text
        if '채용' in text or 'hiring' in text_lower: score += 10
        if '포지션' in text or 'position' in text_lower: score += 10
        if '경력' in text or 'experience' in text_lower: score += 5
        if '개발' in text or 'developer' in text_lower: score += 5
        if '엔지니어' in text or 'engineer' in text_lower: score += 5

        # Text content length (job postings usually have moderate length)
        text_len = len(text)
        if 50 <= text_len <= 200: score += 10
        elif 30 <= text_len <= 300: score += 5
        elif text_len > 400: score -= 5  # Too long, likely a container

        # Count preference (job postings are usually numerous)
        if count >= 50:
            score += 30  # Very likely job postings (large lists)
        elif count >= 20:
            score += 20  # Likely job postings
        elif count >= 10:
            score += 10  # Possible job postings
        elif count >= 5:
            score += 5   # Maybe job postings
        elif count <= 3:
            score -= 5   # Too few, likely not job list

        return score

    # Remove duplicates and sort by score
    seen_sigs = set()
    unique_lists = []
    for item in potential_lists:
        if item[0] not in seen_sigs:
            seen_sigs.add(item[0])
            unique_lists.append(item)

    unique_lists.sort(key=score_candidate, reverse=True)
    return unique_lists

def has_job_items(soup: BeautifulSoup, min_text_length: int = 20) -> bool:
    """
    Check if page has any repeated items (potential job listings).

    Improvements:
    - Require meaningful text content
    - Filter CSS-in-JS only elements
    """
    candidates = []
    for tag in soup.find_all(True):
        text = tag.get_text(strip=True)

        # Require meaningful content
        if len(text) < min_text_length:
            continue

        classes = tag.get('class')
        if classes:
            # Filter out CSS-in-JS only elements
            stable_classes = [c for c in classes if not is_css_in_js_class(c)]
            if stable_classes:
                candidates.append(f"{tag.name}.{'.'.join(stable_classes)}")

    counter = Counter(candidates)
    return any(count >= MIN_ITEM_COUNT for count in counter.values())

# ==================== DOM Hierarchy Analysis ====================
def analyze_hierarchy(soup: BeautifulSoup, candidates: List[Tuple[str, str, int]]) -> Dict[str, Dict]:
    """
    Analyze DOM hierarchy of candidates to identify outermost containers.

    Returns dict mapping selector to metadata:
    - is_outermost: bool
    - contains: List[str] (which other candidates are inside this one)
    - depth: int (average depth in DOM tree)
    """
    metadata = {}

    for sig, text, count in candidates:
        # Get first example of this selector
        example = soup.select_one(sig)
        if not example:
            continue

        # Calculate depth
        depth = len(list(example.parents))

        # Check which other candidates are inside this one
        contains = []
        is_outermost = True

        for other_sig, _, _ in candidates:
            if sig == other_sig:
                continue

            other_example = soup.select_one(other_sig)
            if not other_example:
                continue

            # Check if other is inside this one
            if other_example in example.descendants:
                contains.append(other_sig)

            # Check if this one is inside other (means not outermost)
            if example in other_example.descendants:
                is_outermost = False

        metadata[sig] = {
            'is_outermost': is_outermost,
            'contains': contains,
            'depth': depth
        }

    return metadata

# ==================== Interactive Selection ====================
def interactive_select(candidates: List[Tuple[str, str, int]],
                      item_name: str, soup: BeautifulSoup = None) -> Optional[str]:
    """Let user select from candidates interactively with hierarchy analysis."""
    if not candidates:
        print_warning(f"No candidates found for {item_name}.")
        return manual_entry(item_name)

    # Analyze hierarchy if soup is provided and this is Job List Container selection
    hierarchy_info = {}
    if soup and item_name == "Job List Container":
        hierarchy_info = analyze_hierarchy(soup, candidates[:MAX_CANDIDATES_DISPLAY])

    print(f"\n{Colors.CYAN}--- Select {item_name} ---{Colors.ENDC}")
    print(f"Examine the examples and choose the one matching {item_name}.")

    # Add helpful tip for Job List Container
    if item_name == "Job List Container" and hierarchy_info:
        print(f"\n{Colors.WARNING}💡 Tip:{Colors.ENDC} Select the {Colors.BOLD}OUTERMOST{Colors.ENDC} container (marked with ⭐)")
        print("   This ensures the parser can access all child elements (title, company, link).")
        print()

    for i, (sig, example_text, count) in enumerate(candidates[:MAX_CANDIDATES_DISPLAY]):
        ex_text = example_text.strip().replace('\n', ' ')
        if len(ex_text) > 80:
            ex_text = ex_text[:77] + "..."

        # Build selector display with hierarchy info
        selector_display = f"{Colors.GREEN}{sig}{Colors.ENDC}"

        if sig in hierarchy_info:
            info = hierarchy_info[sig]
            if info['is_outermost']:
                selector_display += f" {Colors.BOLD}⭐ Outermost{Colors.ENDC}"
            else:
                selector_display += f" {Colors.WARNING}(nested){Colors.ENDC}"

        print(f"{Colors.BOLD}[{i+1}]{Colors.ENDC} Selector: {selector_display}")
        print(f"    Found {count} times. Example: '{ex_text}'")

        # Show what this container includes (optional detail)
        if sig in hierarchy_info and hierarchy_info[sig]['contains']:
            contains_count = len(hierarchy_info[sig]['contains'])
            if contains_count > 0:
                print(f"    {Colors.CYAN}↳ Contains {contains_count} other element(s){Colors.ENDC}")

    print(f"{Colors.BOLD}[0]{Colors.ENDC} None of the above (Manual selector)")

    choice = safe_int_input(f"\nSelect option (0-{min(len(candidates), MAX_CANDIDATES_DISPLAY)}): ",
                           0, min(len(candidates), MAX_CANDIDATES_DISPLAY))

    if choice is None or choice == 0:
        return manual_entry(item_name)

    print_success(f"Selected: {candidates[choice-1][0]}")
    return candidates[choice-1][0]

def manual_entry(item_name: str) -> Optional[str]:
    """Prompt user to manually enter a CSS selector."""
    print(f"\n{Colors.WARNING}Enter manual CSS selector for {item_name}{Colors.ENDC}")
    print("Tip: Use DevTools (F12) to copy selector if unsure.")
    while True:
        sel = input(f"{item_name} Selector > ").strip()
        if sel:
            return sel
        print("Selector cannot be empty.")

def get_child_candidates(parent, tags: List[str] = None) -> List[Tuple[str, str, int]]:
    """Extract child element candidates from a parent container."""
    if tags is None:
        tags = ['a', 'strong', 'b', 'h2', 'h3', 'h4', 'span', 'div', 'p']
    
    cands = []
    for tag in parent.find_all(tags):
        text = tag.get_text(strip=True)
        if not text:
            continue
        
        rel_sel = tag.name
        if tag.get('class'):
            rel_sel += f".{'.'.join(tag.get('class'))}"
        
        cands.append((rel_sel, text, 1))
    
    # Deduplicate
    seen = set()
    unique = []
    for c in cands:
        if c[0] not in seen:
            seen.add(c[0])
            unique.append(c)
    return unique

# ==================== Configuration Generation ====================
def generate_yaml_config(url: str, site_name: str, job_selector: str,
                        title_selector: str, company_selector: str,
                        link_selector: str, search_config: Dict,
                        pagination_config: Dict) -> str:
    """Generate YAML configuration block."""
    parsed_url = urlparse(url)

    # Generate url_template based on search method
    base_url = url.split('?')[0]  # Remove existing query params

    if search_config and search_config.get('type') == 'url':
        # URL-based search: add keyword parameter
        param_name = search_config.get('param', 'search')
        url_template = f"{base_url}?{param_name}={{keyword}}"
    else:
        # SPA search or no search: use base URL
        url_template = base_url

    yaml_output = f"""
{Colors.GREEN}# Add this block to your config.yaml:{Colors.ENDC}
  - name: "{site_name}"
    url_template: "{url_template}"
    method: "selenium"
    base_url: "{parsed_url.scheme}://{parsed_url.netloc}"
"""

    if search_config and 'selector' in search_config:
        yaml_output += f"""    search:
      selector: "{search_config['selector']}"
      action: "{search_config['action']}"
"""
    
    yaml_output += f"""    selectors:
      job_list: "{job_selector}"
      title: "{title_selector}"
      company: "{company_selector}"
      link: "{link_selector}"
      detail: ""
      pagination:
        type: "{pagination_config.get('type', 'url')}"
        max_pages: {pagination_config.get('max_pages', 1)}
"""
    return yaml_output

# ==================== Main Analysis Flow ====================
def analyze_page(url: str, keyword: Optional[str] = None):
    """Main analysis flow for extracting selectors from a URL."""
    print_header("Recruit Site Configuration Helper")
    
    print(f"Target URL: {url}")
    if keyword:
        print(f"Target Keyword: {keyword}")
    
    print_step(1, "Initializing Browser...")
    driver = init_driver()
    if not driver:
        return

    search_config = {}
    original_url = url
    
    try:
        print(f"Navigating to {url}...")
        driver.get(url)
        time.sleep(INITIAL_LOAD_WAIT)
        
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        # Check if URL already has search results
        has_job_list = has_job_items(soup)
        
        if has_job_list:
            print_success("Job list detected on initial page!")
            
            # Even if we found job list, we need to understand HOW to get here
            print_step(2, "Understanding Search Method")
            print("We found job listings, but need to know how users can search this site.")
            print("\n" + Colors.CYAN + "How does search work on this site?" + Colors.ENDC)
            print("1. URL changes with search keyword (e.g. ?search=python)")
            print("   → Standard sites like Saramin, JobKorea")
            print("2. Search input field without URL change (SPA)")
            print("   → Modern sites like SK Careers, Wanted")
            print("3. No search - this is a complete static list")
            print("   → All jobs are shown, no filtering needed")
            
            method_choice = safe_choice_input("\nSelect (1-3): ", ['1', '2', '3'])
            
            if method_choice == '1':
                # URL-based search
                print("\n" + Colors.GREEN + "✓ URL-based search configured." + Colors.ENDC)
                print("The system will use URL query parameters for searching.")

                # Ask for the search parameter name
                print(f"\n{Colors.CYAN}What is the search query parameter name?{Colors.ENDC}")
                print("Examples: 'search', 'q', 'keyword', 'query'")
                print(f"Look at the URL when you search on the site.")

                # Try to detect from current URL if it has query params
                from urllib.parse import parse_qs
                parsed = urlparse(url)
                existing_params = parse_qs(parsed.query)

                if existing_params:
                    print(f"Current URL parameters detected: {', '.join(existing_params.keys())}")

                param_name = input("Parameter name > ").strip()
                if not param_name:
                    param_name = "search"  # Default
                    print(f"Using default: {param_name}")

                # Store in search_config for later use in YAML generation
                search_config = {'type': 'url', 'param': param_name}
                
            elif method_choice == '2':
                # Input-based search (SPA) - need to find the input
                print("\n" + Colors.GREEN + "✓ SPA search mode activated." + Colors.ENDC)
                print("Let's find the search input field...")
                
                selected_input = select_search_input(driver)
                if selected_input:
                    input_elem, _ = selected_input
                    selector = get_input_selector(input_elem)
                    search_config = {'selector': selector, 'action': 'enter'}
                    print_success(f"Search input configured: {selector}")
                    
                    # Optional: Test the search
                    print("\n" + Colors.CYAN + "Want to verify by performing a test search? (Y/n): " + Colors.ENDC)
                    test_choice = safe_choice_input("", ['Y', 'y', 'N', 'n', ''])
                    if test_choice and test_choice.lower() != 'n':
                        test_keyword = input("Enter test keyword: ").strip() or DEFAULT_SEARCH_KEYWORD
                        if perform_search(driver, input_elem, test_keyword):
                            soup = BeautifulSoup(driver.page_source, 'lxml')
                            print_success("Search test successful!")
                else:
                    print_warning("Could not auto-detect search input.")
                    manual_sel = manual_entry("Search Input")
                    if manual_sel:
                        search_config = {'selector': manual_sel, 'action': 'enter'}
                        print_success(f"Manual search input configured: {manual_sel}")
                    else:
                        print_error("Search configuration incomplete. Proceeding without search config.")
                
            elif method_choice == '3':
                # No search needed - static list
                print("\n" + Colors.GREEN + "✓ Static list mode." + Colors.ENDC)
                print("No search configuration will be generated.")
                print("The system will monitor this exact URL for updates.")

        
        else:
            # No job list found - need to search
            print_step(2, "Analyzing Page Type...")
            
            # Detect if SPA
            spa_detection = detect_spa_indicators(soup, driver)
            
            print(f"\n{Colors.CYAN}Page Analysis:{Colors.ENDC}")
            print(f"SPA Likelihood: {spa_detection['confidence']*100:.0f}%")
            if spa_detection['reasons']:
                print("Detected indicators:")
                for reason in spa_detection['reasons']:
                    print(f"  • {reason}")
            
            if spa_detection['is_spa']:
                print(f"\n{Colors.GREEN}✓ This appears to be an SPA site.{Colors.ENDC}")
            else:
                print(f"\n{Colors.BLUE}This appears to be a standard site.{Colors.ENDC}")
            
            # Need to search
            print("\n" + "="*60)
            print("No job listings found on this page.")
            print("We need to perform a search to analyze the results.")
            print("="*60)
            
            # Prompt for keyword if not provided
            if not keyword:
                print(f"\n{Colors.CYAN}Enter a search keyword to find job listings:{Colors.ENDC}")
                print("(This will be used to generate test results for analysis)")
                keyword = input("Search keyword > ").strip()
                if not keyword:
                    keyword = DEFAULT_SEARCH_KEYWORD
                    print(f"Using default: {keyword}")
            
            print_step(3, f"Performing Search: '{keyword}'")
            
            # Try to find and use search input
            selected_input = select_search_input(driver)
            
            if selected_input:
                input_elem, _ = selected_input
                selector = get_input_selector(input_elem)
                search_config = {'selector': selector, 'action': 'enter'}
                
                if perform_search(driver, input_elem, keyword):
                    soup = BeautifulSoup(driver.page_source, 'lxml')
                    
                    # Check if URL changed (indicates URL-based search)
                    current_url = driver.current_url
                    if current_url != original_url and keyword.lower() in current_url.lower():
                        print_success("URL changed and includes keyword! → URL-based search")
                        print(f"New URL: {current_url}")
                        print(f"Original: {original_url}")
                        print(f"\n{Colors.CYAN}Analysis:{Colors.ENDC} Search input triggers URL change.")
                        print("The site uses URL parameters for search results.")
                        search_config = {}  # Use URL template instead
                        url = current_url  # Update for config generation
                    else:
                        print_success("URL unchanged → SPA search (input-based)")
                        print(f"{Colors.CYAN}Analysis:{Colors.ENDC} Search happens without URL change.")
                        print("The site uses JavaScript to load results dynamically.")
                else:
                    print_error("Search failed. Aborting.")
                    return
            else:
                # No automatic input found - manual entry
                print_warning("Could not auto-detect search input.")
                manual_sel = manual_entry("Search Input")
                if manual_sel:
                    try:
                        input_elem = driver.find_element(By.CSS_SELECTOR, manual_sel)
                        search_config = {'selector': manual_sel, 'action': 'enter'}
                        if not perform_search(driver, input_elem, keyword):
                            return
                        soup = BeautifulSoup(driver.page_source, 'lxml')
                    except Exception as e:
                        print_error(f"Could not find element: {e}")
                        return
                else:
                    print_error("Search input required. Aborting.")
                    return
        
        # At this point, we should have job listings
        # Re-check for job items after potential search
        if not has_job_items(soup):
            print_error("Still no job list found. Check the keyword or page structure.")
            return
        
        # Find Job List
        print_step(4, "Identifying Job List Container")
        print("Analyzing DOM for repeated patterns...")

        # Detect CSS-in-JS usage
        all_classes = []
        for tag in soup.find_all(True):
            classes = tag.get('class')
            if classes:
                all_classes.extend(classes)

        css_in_js_classes = [c for c in set(all_classes) if is_css_in_js_class(c)]
        if css_in_js_classes:
            print(f"\n{Colors.WARNING}⚠ CSS-in-JS Detected!{Colors.ENDC}")
            print(f"Found {len(css_in_js_classes)} dynamically generated classes (e.g., {', '.join(css_in_js_classes[:3])})")
            print("These selectors may be unstable. Looking for data-* attributes instead...\n")

        potential_lists = find_job_list_candidates(soup)

        if not potential_lists:
            print_error("Could not identify job list candidates.")
            if css_in_js_classes:
                print_warning("This site uses CSS-in-JS with no stable selectors.")
                print("Recommendation: Check if the site provides data-* attributes or use structured extraction.")
            return
        
        job_selector_sig = interactive_select(potential_lists[:10], "Job List Container", soup)

        if not job_selector_sig:
            print_error("Aborted.")
            return

        # Parse selector more flexibly to handle manual input
        if '.' in job_selector_sig and not job_selector_sig.startswith('.'):
            # Format: tag.class or tag.class1.class2
            tag_name, class_str = job_selector_sig.split('.', 1)
            job_selector = f"{tag_name}.{'.'.join(class_str.split('.'))}"
        elif job_selector_sig.startswith('.'):
            # Format: .class (assume div)
            job_selector = f"div{job_selector_sig}"
        elif '[' in job_selector_sig:
            # Format: tag[attr='value'] (already valid)
            job_selector = job_selector_sig
        else:
            # Format: just class name (e.g., "css-16ht878")
            # Assume div and add dot prefix
            job_selector = f".{job_selector_sig}"
            print(f"Interpreted as: {job_selector}")

        example_item = soup.select_one(job_selector)
        if not example_item:
            print_error("Failed to re-select item.")
            return
        
        # Find Title, Company, Link
        print_step(5, "Identifying Item Details (Title, Company, Link)")
        
        child_candidates = get_child_candidates(example_item)
        title_selector = interactive_select(child_candidates, "Job Title")
        if not title_selector:
            return
        
        company_selector = interactive_select(child_candidates, "Company Name")
        if not company_selector:
            return
        
        # Link candidates
        link_candidates = []

        # Check if the container itself is a link (e.g., <a> tag wrapping the job item)
        if example_item.name == 'a' and example_item.get('href'):
            href = example_item.get('href')
            text = example_item.get_text(strip=True)[:50]  # Truncate for readability
            rel_sel = "a"
            if example_item.get('class'):
                rel_sel += f".{'.'.join(example_item.get('class'))}"
            link_candidates.append((rel_sel, f"(Self) Href: {href}", 1))
            print_warning(f"Container itself is a link: {href}")
            print("You can use the container selector as the link, or select 'Manual' if needed.")

        # Also check for links inside the container
        for tag in example_item.find_all('a', href=True):
            href = tag.get('href')
            text = tag.get_text(strip=True)
            rel_sel = "a"
            if tag.get('class'):
                rel_sel += f".{'.'.join(tag.get('class'))}"
            link_candidates.append((rel_sel, f"Text: {text} | Href: {href}", 1))

        link_selector = interactive_select(link_candidates, "Job Link", soup)
        if not link_selector:
            return
        
        # Pagination
        print_step(6, "Pagination Configuration")
        print("How does pagination work?")
        print("1. URL Query Parameter (e.g. ?page=1)")
        print("2. 'Next' Button Click")
        print("3. Infinite Scroll (Load more on scroll)")
        print("4. No pagination (all items on first page)")

        pag_choice = safe_choice_input("Select (1-4): ", ['1', '2', '3', '4'])
        if not pag_choice:
            return

        if pag_choice == '4':
            # No pagination - just fetch first page
            pagination_config = {'max_pages': 1}
            print_success("No pagination configured. Will fetch first page only.")
        else:
            pagination_config = {'max_pages': 3}
            if pag_choice == '1':
                pagination_config['type'] = 'url'
            elif pag_choice == '2':
                pagination_config['type'] = 'button'
            elif pag_choice == '3':
                pagination_config['type'] = 'infinite_scroll'
        
        # Generate output
        print_step(7, "Generating Configuration")
        parsed_url = urlparse(url)
        site_name = parsed_url.netloc.split('.')[1] if 'www' in parsed_url.netloc else parsed_url.netloc.split('.')[0]
        
        yaml_output = generate_yaml_config(
            url, site_name, job_selector, title_selector,
            company_selector, link_selector, search_config, pagination_config
        )
        
        print("-" * 60)
        print(yaml_output)
        print("-" * 60)
        print_success("Configuration generated successfully!")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except Exception as e:
        print_error(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()

# ==================== Entry Point ====================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Interactive Selector Helper for Recruit Config"
    )
    parser.add_argument("url", help="Target URL (e.g. https://www.site.com/jobs)")
    parser.add_argument(
        "--search", 
        help="Search keyword (optional, auto-detected if needed)", 
        default=None
    )
    
    args = parser.parse_args()
    analyze_page(args.url, args.search)
