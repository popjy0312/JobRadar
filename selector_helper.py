#!/usr/bin/env python3
"""
Selector Helper Script (Refactored)
------------------------------------
Analyzes a given URL to interactively deduce CSS selectors for config.yaml.

Usage:
    python selector_helper.py <URL> [options]

Examples:
    # 1. Standard search (URL query params) - Auto-detected
    python selector_helper.py "https://www.saramin.co.kr/zf_user/search/recruit?searchword=python"

    # 2. SPA search (Input field + Enter key) - Auto-detected or Manual
    python selector_helper.py "https://www.skcareers.com/Recruit" 
    # -> If no job list is found, the script will propose to find a search bar and type a keyword.

    # 3. Explicit Keyword (Force specific keyword search)
    python selector_helper.py "https://www.skcareers.com/Recruit" --search "SK"

This script will:
1. Open the URL in a headless Chrome browser.
2. Analyze the page content.
3. If it looks like an empty SPA page, it will suggest finding a search bar.
4. If it looks like a result page, it will identify Job List candidates.
5. Guide you to select Title, Company, and Link selectors.
6. Generate a ready-to-use YAML configuration block.
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
MAX_ITEM_COUNT = 100
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
def get_css_selector(element) -> str:
    """Generate a CSS selector for a BeautifulSoup element."""
    if not element:
        return ""
    
    # Prefer ID
    if element.get('id'):
        return f"#{element.get('id')}"

    # Use class
    classes = element.get('class')
    if classes:
        valid_classes = [c for c in classes if not c.startswith('ng-') 
                        and not c.startswith('vue-') and not c.isdigit()]
        if valid_classes:
            return f"{element.name}.{'.'.join(valid_classes)}"
    
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
    """Find potential job list container candidates by analyzing DOM."""
    candidates = []
    for tag in soup.find_all(True):
        classes = tag.get('class')
        if not classes:
            continue
        sig = f"{tag.name}.{'.'.join(classes)}"
        candidates.append(sig)
    
    counter = Counter(candidates)
    
    # Filter for reasonable counts
    potential_lists = []
    for sig, count in counter.most_common(50):
        if MIN_ITEM_COUNT <= count <= MAX_ITEM_COUNT:
            tag_name, class_str = sig.split('.', 1)
            selector = f"{tag_name}.{'.'.join(class_str.split('.'))}"
            example = soup.select_one(selector)
            text = example.get_text(strip=True)[:100] if example else ""
            potential_lists.append((sig, text, count))
    
    # Heuristic scoring
    def score_candidate(item):
        sig = item[0]
        score = 0
        if 'li' in sig: score += 5
        if 'item' in sig: score += 10
        if 'list' in sig: score += 5
        if 'card' in sig: score += 10
        if 'recruit' in sig: score += 15
        if 'job' in sig: score += 15
        return score
    
    potential_lists.sort(key=score_candidate, reverse=True)
    return potential_lists

def has_job_items(soup: BeautifulSoup) -> bool:
    """Check if page has any repeated items (potential job listings)."""
    candidates = []
    for tag in soup.find_all(True):
        classes = tag.get('class')
        if classes:
            candidates.append(f"{tag.name}.{'.'.join(classes)}")
    
    counter = Counter(candidates)
    return any(count >= MIN_ITEM_COUNT for count in counter.values())

# ==================== Interactive Selection ====================
def interactive_select(candidates: List[Tuple[str, str, int]], 
                      item_name: str) -> Optional[str]:
    """Let user select from candidates interactively."""
    if not candidates:
        print_warning(f"No candidates found for {item_name}.")
        return manual_entry(item_name)
    
    print(f"\n{Colors.CYAN}--- Select {item_name} ---{Colors.ENDC}")
    print(f"Examine the examples and choose the one matching {item_name}.")
    
    for i, (sig, example_text, count) in enumerate(candidates[:MAX_CANDIDATES_DISPLAY]):
        ex_text = example_text.strip().replace('\n', ' ')
        if len(ex_text) > 80:
            ex_text = ex_text[:77] + "..."
        
        print(f"{Colors.BOLD}[{i+1}]{Colors.ENDC} Selector: {Colors.GREEN}{sig}{Colors.ENDC}")
        print(f"    Found {count} times. Example: '{ex_text}'")
    
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
    
    yaml_output = f"""
{Colors.GREEN}# Add this block to your config.yaml:{Colors.ENDC}
  - name: "{site_name}"
    url_template: "{url.split('?')[0]}" 
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
        max_pages: 3
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
                # search_config remains empty (URL template will have {keyword})
                
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
        
        potential_lists = find_job_list_candidates(soup)
        
        if not potential_lists:
            print_error("Could not identify job list candidates.")
            return
        
        job_selector_sig = interactive_select(potential_lists[:10], "Job List Container")
        
        if not job_selector_sig:
            print_error("Aborted.")
            return
        
        tag_name, class_str = job_selector_sig.split('.', 1)
        job_selector = f"{tag_name}.{'.'.join(class_str.split('.'))}"
        
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
        for tag in example_item.find_all('a', href=True):
            href = tag.get('href')
            text = tag.get_text(strip=True)
            rel_sel = "a"
            if tag.get('class'):
                rel_sel += f".{'.'.join(tag.get('class'))}"
            link_candidates.append((rel_sel, f"Text: {text} | Href: {href}", 1))
        
        link_selector = interactive_select(link_candidates, "Job Link")
        if not link_selector:
            return
        
        # Pagination
        print_step(6, "Pagination Configuration")
        print("How does pagination work?")
        print("1. URL Query Parameter (e.g. ?page=1)")
        print("2. 'Next' Button Click")
        print("3. Infinite Scroll (Load more on scroll)")
        
        pag_choice = safe_choice_input("Select (1-3): ", ['1', '2', '3'])
        if not pag_choice:
            return
        
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
