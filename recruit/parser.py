"""
Recruitment site parser module
Parses job postings from various recruitment sites using HTTP or Selenium.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time
import logging
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
try:
    from webdriver_manager.core.os_manager import ChromeType
except ImportError:
    # Older webdriver-manager might put it elsewhere or not export it
    ChromeType = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseParser:
    """Base parser class"""

    def __init__(self, config: Dict):
        """
        Args:
            config: Site configuration dictionary
        """
        self.config = config  # Store full config
        self.name = config.get('name', 'unknown')
        self.url_template = config.get('url_template', '')
        self.selectors = config.get('selectors', {})
        self.base_url = config.get('base_url', '')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def parse(self, keyword: str) -> List[Dict]:
        """Parse job postings (to be implemented by subclasses)"""
        raise NotImplementedError

    def get_soup(self, url: str) -> BeautifulSoup:
        """Create BeautifulSoup object from URL"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'lxml')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _extract_job_data_html(self, job_elem) -> Optional[Dict]:
        """Extract job data from HTML element (BeautifulSoup)"""
        title_selector = self.selectors.get('title', '')
        company_selector = self.selectors.get('company', '')
        link_selector = self.selectors.get('link', title_selector)
        detail_selector = self.selectors.get('detail', '')

        # Check if structured extraction is configured
        extraction_config = self.selectors.get('extraction', {})
        strategy = extraction_config.get('strategy', 'simple')

        if strategy == 'structured':
            # Structured extraction: use link indices and patterns
            return self._extract_structured(job_elem, extraction_config)
        else:
            # Standard extraction
            title_elem = job_elem.select_one(
                title_selector) if title_selector else None
            company_elem = job_elem.select_one(
                company_selector) if company_selector else None
            link_elem = job_elem.select_one(
                link_selector) if link_selector else None

        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        company = company_elem.get_text(
            strip=True) if company_elem else "Unknown"
        link = link_elem.get('href', '') if link_elem else ''

        # Convert relative link to absolute
        if link and not link.startswith('http'):
            if self.base_url:
                link = f"{self.base_url.rstrip('/')}/{link.lstrip('/')}"
            elif self.url_template:
                # Extract base URL from url_template
                from urllib.parse import urlparse
                parsed = urlparse(self.url_template)
                base = f"{parsed.scheme}://{parsed.netloc}"
                link = f"{base}/{link.lstrip('/')}"

        detail = ""
        if detail_selector:
            detail_elem = job_elem.select_one(detail_selector)
            if detail_elem:
                detail = detail_elem.get_text(strip=True)

        return {
            'title': title,
            'company': company,
            'link': link,
            'detail': detail,
            'source': self.name
        }

    def _matches_filter_conditions(self, element, conditions: Dict) -> bool:
        """
        Check if element matches all filter conditions

        Args:
            element: BeautifulSoup element to check
            conditions: Dictionary of filter conditions

        Returns:
            True if all conditions match, False otherwise
        """
        # If no conditions, match everything
        if not conditions:
            return True

        # Check has_child condition
        if 'has_child' in conditions:
            child_selector = conditions['has_child']
            if not element.select(child_selector):
                return False

        # Check not_has_child condition
        if 'not_has_child' in conditions:
            child_selector = conditions['not_has_child']
            if element.select(child_selector):
                return False

        # Check has_attribute condition
        if 'has_attribute' in conditions:
            attr_config = conditions['has_attribute']
            if isinstance(attr_config, str):
                # Simple: just check if attribute exists
                if not element.has_attr(attr_config):
                    return False
            else:
                # Complex: check attribute value
                attr_name = attr_config.get('name', '')
                attr_value = attr_config.get('value', '')
                if element.get(attr_name) != attr_value:
                    return False

        # Check not_has_attribute condition
        if 'not_has_attribute' in conditions:
            attr_config = conditions['not_has_attribute']
            if isinstance(attr_config, str):
                # Simple: check if attribute doesn't exist
                if element.has_attr(attr_config):
                    return False
            else:
                # Complex: check attribute value doesn't match
                attr_name = attr_config.get('name', '')
                attr_value = attr_config.get('value', '')
                if element.get(attr_name) == attr_value:
                    return False

        # Check has_text condition
        if 'has_text' in conditions:
            text_pattern = conditions['has_text']
            element_text = element.get_text(strip=True)
            if text_pattern not in element_text:
                return False

        # Check not_has_text condition
        if 'not_has_text' in conditions:
            text_pattern = conditions['not_has_text']
            element_text = element.get_text(strip=True)
            if text_pattern in element_text:
                return False

        return True

    def _extract_structured(
            self,
            job_elem,
            extraction_config: Dict) -> Optional[Dict]:
        """
        Extract job data using structured approach (link indices, patterns, etc.)

        Args:
            job_elem: Job element to extract from
            extraction_config: Extraction configuration from selectors.extraction

        Returns:
            Job data dictionary or None
        """
        # Get link filter configuration
        link_filter_config = extraction_config.get('link_filter', '')

        # Support both old and new configuration formats
        if isinstance(link_filter_config, str):
            # Legacy format: simple string selector
            link_selector = link_filter_config
            filter_conditions = {}
            # Backward compatibility for link_filter_condition
            legacy_condition = extraction_config.get(
                'link_filter_condition', '')
            if legacy_condition:
                logger.warning(
                    f"Deprecated: 'link_filter_condition' is deprecated. Use 'link_filter' dict format instead.")
                # Convert legacy condition to new format
                if legacy_condition == 'has_typography':
                    filter_conditions['has_child'] = 'span[data-sentry-element="Typography"]'
                elif legacy_condition == 'not_logo':
                    filter_conditions['not_has_attribute'] = {
                        'name': 'data-sentry-component',
                        'value': 'CompanyLogo'
                    }
        else:
            # New format: dictionary with selector and conditions
            link_selector = link_filter_config.get('selector', '')
            filter_conditions = link_filter_config

        # Find all links matching base selector
        if link_selector:
            all_links = job_elem.select(link_selector)
        else:
            all_links = job_elem.select('a')

        # Apply filter conditions
        text_links = []
        for link in all_links:
            if self._matches_filter_conditions(link, filter_conditions):
                text_links.append(link)

        # Extract title
        title_config = extraction_config.get('title', {})
        title_elem = None
        link_elem = None

        title_link_index = title_config.get('link_index', 0)
        if len(text_links) > title_link_index:
            title_link = text_links[title_link_index]
            link_elem = title_link

            # Find span within link
            span_selector = title_config.get('span_selector', '')
            class_pattern = title_config.get('class_pattern', '')

            if span_selector:
                title_spans = title_link.select(span_selector)
                if title_spans:
                    if class_pattern:
                        # Find span matching class pattern
                        for span in title_spans:
                            classes = ' '.join(span.get('class', []))
                            if class_pattern in classes:
                                title_elem = span
                                break
                        # Fallback: first span
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
                        # Find span matching class pattern and length
                        for span in company_spans:
                            classes = ' '.join(span.get('class', []))
                            text = span.get_text(strip=True)
                            if class_pattern in classes and text and len(
                                    text) < max_length:
                                company_elem = span
                                break
                        # Fallback: first matching length
                        if not company_elem:
                            for span in company_spans:
                                text = span.get_text(strip=True)
                                if text and len(text) < max_length:
                                    company_elem = span
                                    break
                        # Last fallback: first span
                        if not company_elem:
                            company_elem = company_spans[0]
                    else:
                        # Use first non-empty span
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

        # Fallback: try to find company in entire card
        if not company_elem:
            company_config = extraction_config.get('company', {})
            span_selector = company_config.get('span_selector', '')
            class_pattern = company_config.get('class_pattern', '')
            max_length = company_config.get('max_length', 50)

            if span_selector and class_pattern:
                all_spans = job_elem.select(span_selector)
                for span in all_spans:
                    classes = ' '.join(span.get('class', []))
                    text = span.get_text(strip=True)
                    if class_pattern in classes and text and len(
                            text) < max_length:
                        # Check if in a link
                        parent_link = span.find_parent(
                            'a', href=lambda x: x and link_filter in x if link_filter and x else True)
                        if parent_link:
                            company_elem = span
                            break

        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        company = company_elem.get_text(
            strip=True) if company_elem else "Unknown"
        link = link_elem.get('href', '') if link_elem else ''

        # Convert relative link to absolute
        if link and not link.startswith('http'):
            if self.base_url:
                link = f"{self.base_url.rstrip('/')}/{link.lstrip('/')}"
            elif self.url_template:
                from urllib.parse import urlparse
                parsed = urlparse(self.url_template)
                base = f"{parsed.scheme}://{parsed.netloc}"
                link = f"{base}/{link.lstrip('/')}"

        # Extract detail if configured
        detail = ""
        detail_selector = self.selectors.get('detail', '')
        if detail_selector:
            detail_elem = job_elem.select_one(detail_selector)
            if detail_elem:
                detail = detail_elem.get_text(strip=True)

        return {
            'title': title,
            'company': company,
            'link': link,
            'detail': detail,
            'source': self.name
        }


class HttpSiteParser(BaseParser):
    """HTTP-based parser for sites that return static HTML"""

    def parse(self, keyword: str) -> List[Dict]:
        """Parse job postings from HTTP-based site"""
        jobs = []

        if not self.url_template:
            logger.error(f"Site '{self.name}': url_template not configured")
            return jobs

        # Build base search URL
        base_search_url = self.url_template.replace('{keyword}', keyword)

        # Pagination configuration
        pagination = self.selectors.get('pagination', {})
        param = pagination.get('param')
        max_pages = pagination.get('max_pages', 1) if param else 1

        for page in range(1, max_pages + 1):
            # Construct URL for current page
            search_url = base_search_url
            if param:
                separator = '&' if '?' in search_url else '?'
                search_url = f"{search_url}{separator}{param}={page}"
                if page > 1:
                    logger.info(f"Parsing page {page} for {self.name}...")

            try:
                soup = self.get_soup(search_url)
                if not soup:
                    break

                # Find job list
                job_list_selector = self.selectors.get('job_list', '')
                if not job_list_selector:
                    logger.error(
                        f"Site '{
                            self.name}': job_list selector not configured")
                    return jobs

                job_list = soup.select(job_list_selector)

                if not job_list:
                    # Stop if no jobs found on this page
                    break

                page_jobs_count = 0
                for job in job_list:
                    try:
                        job_data = self._extract_job_data_html(job)
                        if job_data:
                            jobs.append(job_data)
                            page_jobs_count += 1
                    except Exception as e:
                        logger.error(
                            f"Error parsing job item from {
                                self.name}: {e}")
                        continue

                logger.debug(
                    f"{self.name}: Found {page_jobs_count} jobs on page {page}")

                # Delay between pages to be polite
                if page < max_pages:
                    time.sleep(1)

            except Exception as e:
                logger.error(
                    f"Error parsing site '{
                        self.name}' page {page}: {e}")

        logger.info(
            f"{self.name}: Found total {len(jobs)} jobs for keyword '{keyword}'")

        return jobs


class SeleniumSiteParser(BaseParser):
    """Selenium-based parser for JavaScript-rendered sites"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.driver = None
        self.chrome_available = None

    def _check_chrome_available(self) -> bool:
        """Check if Chrome browser is available"""
        if self.chrome_available is not None:
            return self.chrome_available

        try:
            # Check for various Chrome/Chromium binaries
            chrome_binaries = [
                'google-chrome', 'google-chrome-stable',
                'chromium', 'chromium-browser'
            ]

            # Use shutil.which for more reliable path checking
            import shutil
            found = any(shutil.which(binary)
                        is not None for binary in chrome_binaries)

            # Check specific paths if not found in PATH
            if not found:
                chrome_paths = [
                    '/usr/bin/google-chrome',
                    '/usr/bin/google-chrome-stable',
                    '/usr/bin/chromium',
                    '/usr/bin/chromium-browser',
                    '/snap/bin/chromium'
                ]
                found = any(os.path.exists(path) for path in chrome_paths)

            self.chrome_available = found
        except Exception:
            self.chrome_available = False

        return self.chrome_available

    def _init_driver(self):
        """Initialize Selenium driver"""
        if self.driver is not None:
            return

        if not self._check_chrome_available():
            raise RuntimeError(
                f"Chrome browser not found for site '{self.name}'. "
                "Install Chrome/Chromium to use Selenium method. "
                "On Ubuntu/Debian: sudo apt-get install chromium-browser"
            )

        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(
                'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

            # Explicitly check for chromium binary if google-chrome is missing
            import shutil

            # Use ChromeType for webdriver_manager if detected (cleaner
            # detection by library)
            chrome_type = None
            if not shutil.which(
                    'google-chrome') and not shutil.which('google-chrome-stable'):
                if shutil.which(
                        'chromium-browser') or shutil.which('chromium'):
                    if ChromeType:
                        chrome_type = ChromeType.CHROMIUM

                    # Also set binary location explicitly for safety
                    binary_path = shutil.which(
                        'chromium-browser') or shutil.which('chromium')
                    if binary_path:
                        chrome_options.binary_location = binary_path

            # Special handling for Snap Chromium (common in Ubuntu)
            # If using chromium-browser wrapper, we might need the snap
            # chromedriver
            if chrome_type == ChromeType.CHROMIUM and os.path.exists(
                    '/snap/bin/chromium'):
                # First check for the standard snap alias for chromedriver
                if os.path.exists('/snap/bin/chromium.chromedriver'):
                    logger.info(
                        "Using Snap Chromedriver alias: /snap/bin/chromium.chromedriver")
                    service = Service('/snap/bin/chromium.chromedriver')
                    self.driver = webdriver.Chrome(
                        service=service, options=chrome_options)
                    return

                # Try to find snap chromedriver directly if alias missing
                import glob
                snap_drivers = glob.glob(
                    '/snap/chromium/*/usr/lib/chromium-browser/chromedriver')
                if snap_drivers:
                    # Use the first found snap chromedriver
                    driver_path = snap_drivers[0]
                    logger.info(f"Using Snap Chromedriver: {driver_path}")
                    service = Service(driver_path)
                    self.driver = webdriver.Chrome(
                        service=service, options=chrome_options)
                    return

            if chrome_type:
                driver_path = ChromeDriverManager(
                    chrome_type=chrome_type).install()
            else:
                driver_path = ChromeDriverManager().install()

            # Fix for WDM returning non-binary files (e.g. THIRD_PARTY_NOTICES)
            if os.path.basename(driver_path) != 'chromedriver':
                driver_dir = os.path.dirname(driver_path)
                potential_binary = os.path.join(driver_dir, 'chromedriver')
                if os.path.exists(potential_binary):
                    driver_path = potential_binary

            # Ensure the driver is executable
            try:
                os.chmod(driver_path, 0o755)
            except Exception:
                pass

            service = Service(driver_path)
            self.driver = webdriver.Chrome(
                service=service, options=chrome_options)
        except Exception as e:
            logger.error(
                f"Failed to initialize Chrome driver for {
                    self.name}: {e}")
            raise

    def _extract_job_data_selenium(self, card) -> Optional[Dict]:
        """Extract job data from Selenium WebElement"""
        # Check if structured extraction is configured
        extraction_config = self.selectors.get('extraction', {})
        strategy = extraction_config.get('strategy', 'simple')

        if strategy == 'structured':
            # For Selenium, we need to convert to HTML and use BeautifulSoup
            # or implement similar logic with Selenium methods
            html = card.get_attribute('outerHTML')
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            job_elem = soup.find('div') or soup  # Get root element
            return self._extract_structured(job_elem, extraction_config)

        # Simple extraction (original logic)
        title_selector = self.selectors.get('title', '')
        company_selector = self.selectors.get('company', '')
        link_selector = self.selectors.get('link', title_selector)
        detail_selector = self.selectors.get('detail', '')

        try:
            title_elem = card.find_element(
                By.CSS_SELECTOR, title_selector) if title_selector else None
            company_elem = card.find_element(
                By.CSS_SELECTOR, company_selector) if company_selector else None
            link_elem = card.find_element(
                By.CSS_SELECTOR, link_selector) if link_selector else None

            if not title_elem:
                return None

            title = title_elem.text.strip()
            company = company_elem.text.strip() if company_elem else "Unknown"
            link = link_elem.get_attribute('href') if link_elem else ''

            # Convert relative link to absolute
            if link and not link.startswith('http'):
                if self.base_url:
                    link = f"{self.base_url.rstrip('/')}/{link.lstrip('/')}"
                elif self.url_template:
                    from urllib.parse import urlparse
                    parsed = urlparse(self.url_template)
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    link = f"{base}/{link.lstrip('/')}"

            detail = ""
            if detail_selector:
                try:
                    detail_elem = card.find_element(
                        By.CSS_SELECTOR, detail_selector)
                    detail = detail_elem.text.strip()
                except Exception:
                    pass

            return {
                'title': title,
                'company': company,
                'link': link,
                'detail': detail,
                'source': self.name
            }
        except Exception as e:
            logger.error(f"Error extracting job data from {self.name}: {e}")
            return None

    def parse(self, keyword: str) -> List[Dict]:
        """Parse job postings from Selenium-based site"""
        jobs = []

        if not self.url_template:
            logger.error(f"Site '{self.name}': url_template not configured")
            return jobs

        # Check Chrome availability first
        if not self._check_chrome_available():
            logger.warning(
                f"Site '{self.name}' skipped: Chrome browser not found. "
                "Install Chrome/Chromium to use Selenium method."
            )
            return jobs

        # Build base search URL
        base_search_url = self.url_template.replace('{keyword}', keyword)

        # Pagination configuration
        pagination = self.selectors.get('pagination', {})
        pag_type = pagination.get('type', 'url')

        try:
            self._init_driver()

            # Handle Search (URL vs Input)
            # Note: 'search' is at config root level, not inside 'selectors'
            search_config = self.config.get('search', {})
            if search_config and 'selector' in search_config:
                # 1. Navigate to base URL
                self.driver.get(self.url_template)

                # 2. Wait for input
                try:
                    search_input = WebDriverWait(
                        self.driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, search_config['selector'])))

                    # 3. Type keyword and Enter
                    search_input.clear()
                    search_input.send_keys(keyword)
                    if search_config.get('action') == 'enter':
                        search_input.send_keys(Keys.RETURN)

                    time.sleep(3)  # Wait for search results
                except Exception as e:
                    logger.error(f"Search interaction failed: {e}")
                    return jobs
            else:
                # Standard URL based search
                # Build base search URL only if we are not doing input search
                search_url = self.url_template.replace('{keyword}', keyword)
                self.driver.get(search_url)
                # Wait for JavaScript to load
                time.sleep(3)

            # Find job list
            job_list_selector = self.selectors.get('job_list', '')
            if not job_list_selector:
                logger.error(
                    f"Site '{
                        self.name}': job_list selector not configured")
                return jobs

            # Pagination Logic
            max_pages = pagination.get('max_pages', 1)

            if pag_type == 'infinite_scroll':
                for page in range(max_pages):
                    # Scroll down
                    self.driver.execute_script(
                        "window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)  # Wait for load

                    # Check if new items loaded (optional optimization)

            elif pag_type == 'url':
                # Existing URL pagination logic (simplified for Selenium
                # context)
                pass

            # Extract Jobs (after all scrolling/loading)
            # Re-find elements after scrolling
            job_cards = self.driver.find_elements(
                By.CSS_SELECTOR, job_list_selector)

            if not job_cards:
                logger.warning(
                    f"{self.name}: No job cards found with selector '{job_list_selector}'"
                )

            for card in job_cards:
                try:
                    # Convert WebElement to HTML and parse with BeautifulSoup
                    # This avoids StaleElementReferenceException after scrolling
                    html = card.get_attribute('outerHTML')
                    soup = BeautifulSoup(html, 'lxml')
                    job_elem = soup.find() or soup  # Get root element
                    
                    # Use HTML-based extraction
                    job_data = self._extract_job_data_html(job_elem)
                    if job_data:
                        jobs.append(job_data)
                except Exception as e:
                    logger.error(
                        f"Error parsing job item from {
                            self.name}: {e}")
                    continue

            logger.info(
                f"{self.name}: Found {len(jobs)} jobs for keyword '{keyword}'")

        except RuntimeError as e:
            logger.warning(f"Site '{self.name}' skipped: {e}")
        except Exception as e:
            logger.error(f"Error parsing site '{self.name}': {e}")
            logger.debug(
                f"Error details: {
                    type(e).__name__}: {
                    str(e)}",
                exc_info=True)

        logger.info(
            f"{self.name}: Found total {len(jobs)} jobs for keyword '{keyword}'")
        return jobs

    def __del__(self):
        """Quit driver"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass


def get_parser(
        site_name: str,
        sites_config: List[Dict] = None) -> Optional[BaseParser]:
    """
    Return appropriate parser based on site name and configuration

    Args:
        site_name: Name of the site
        sites_config: List of site configurations from config.yaml (includes built-in and custom sites)

    Returns:
        Parser instance or None if site not found
    """
    if not sites_config:
        return None

    site_name_lower = site_name.lower()

    # Find site configuration
    site_config = None
    for config in sites_config:
        if config.get('name', '').lower() == site_name_lower:
            site_config = config
            break

    if not site_config:
        return None

    # Determine parser type based on method
    method = site_config.get('method', 'http')

    if method == 'selenium':
        return SeleniumSiteParser(site_config)
    else:
        return HttpSiteParser(site_config)
