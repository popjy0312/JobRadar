# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Korean job posting monitoring system** that automatically scrapes job listings from major Korean recruitment sites (JobKorea, Saramin, Wanted) and sends notifications when matching positions are found. The system uses keyword-based similarity matching and supports multiple notification methods.

**Language Context**: The project primarily targets Korean job sites and uses Korean keywords. Comments and documentation are in English, but configuration and job content will be in Korean (한국어).

## Development Commands

### Environment Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Run with scheduling (continuous monitoring)
python main.py

# Run one-time check (from Python REPL)
python -c "from recruit import JobScheduler; import yaml; \
config = yaml.safe_load(open('config.yaml', 'r', encoding='utf-8')); \
JobScheduler(config).check_jobs()"
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_matcher.py

# Run with verbose output
pytest -v

# Run with output (don't capture)
pytest -s
```

## Architecture Overview

The project follows a **modular pipeline architecture** with clear separation of concerns:

```
User Config (config.yaml)
        ↓
    Scheduler (scheduler.py) ← main orchestrator
        ↓
    ┌───────────────────────┐
    ↓                       ↓
Parser (parser.py)    Matcher (matcher.py)
    ↓                       ↓
[Raw jobs]  →  [Filtered/scored jobs]
                            ↓
                    Notifier (notifier.py)
                            ↓
                [Terminal/Email/File output]
```

### Core Modules

**1. `parser.py` - Job Scraping**
- **BaseParser**: Abstract base class defining the parsing interface
- **HttpSiteParser**: Parses static HTML sites using requests + BeautifulSoup
- **SeleniumSiteParser**: Parses JavaScript-rendered sites using Selenium WebDriver
- **Configuration-driven**: All sites (built-in and custom) are configured via `config.yaml` with CSS selectors
- **Special handling**: JobKorea uses data-* attributes instead of hash-based CSS classes for stability

**2. `matcher.py` - Job Matching**
- **JobMatcher**: Calculates similarity between job postings and desired keywords
- **Hybrid matching**: Uses both exact matching and fuzzy matching (difflib.SequenceMatcher)
- **Korean text handling**: Special logic for Korean spacing variations (e.g., "백엔드개발자" vs "백엔드 개발자")
- **Weighted scoring**: Title matches weighted 1.5x higher than detail matches
- **Exclude keywords**: Filters out unwanted postings (e.g., "인턴", "신입만")

**3. `scheduler.py` - Job Orchestration**
- **JobScheduler**: Main orchestrator that coordinates parsing, matching, and notification
- **Three scheduling modes**:
  1. Specific times: `times: ["09:00", "12:00", "15:00"]`
  2. Time range + interval: `start_time: "09:00", end_time: "18:00", interval_minutes: 60`
  3. Continuous interval: `interval_minutes: 60` (24/7)
- **Timezone**: All times use KST (Asia/Seoul, UTC+9) via pytz
- **Deduplication**: Tracks seen jobs in `job_history.json` to prevent duplicate notifications
- **Multi-keyword search**: Iterates through all keywords × all sites

**4. `notifier.py` - Notification Delivery**
- **Notifier**: Sends notifications through multiple channels
- **Channels**: Terminal (stdout), Email (SMTP), File (JSON/TXT)
- **Email support**: Gmail SMTP with app password authentication
- **File output**: Timestamped files in `output/` directory

## Configuration System

All configuration is in `config.yaml`:

**Simple Sites** (static HTML with stable CSS classes):
```yaml
sites_config:
  - name: "mysite"
    url_template: "https://example.com/search?q={keyword}"
    method: "http"
    base_url: "https://example.com"
    selectors:
      job_list: "div.job-card"      # CSS selector for job containers
      title: "h3.job-title"          # CSS selector for job title
      company: "span.company"        # CSS selector for company name
      link: "a.job-link"             # CSS selector for job link
      detail: "p.description"        # Optional: additional job details
```

**Complex Sites** (dynamic CSS classes, CSS-in-JS):
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
        link_filter:
          selector: "a[href*='/jobs/']"              # Base selector
          has_child: "span[data-element='Title']"    # Filter: has child
          not_has_attribute:
            name: "data-component"
            value: "Logo"                            # Filter: exclude logos
        title:
          link_index: 0                              # Use 1st filtered link
          span_selector: "span[data-element='Title']"
          class_pattern: "size18"                    # Match semantic pattern
        company:
          link_index: 1                              # Use 2nd filtered link
          span_selector: "span[data-element='Title']"
          class_pattern: "size16"
```

**Filter Conditions Available**:
- `has_child`: Element must have child matching selector
- `not_has_child`: Element must NOT have child matching selector
- `has_attribute`: Element must have attribute (string or {name, value})
- `not_has_attribute`: Element must NOT have attribute
- `has_text`: Element text must contain string
- `not_has_text`: Element text must NOT contain string

**Finding CSS Selectors**: Use browser DevTools (F12) → Right-click element → Copy → Copy selector

## Key Technical Details

### Parser Method Selection
- **HTTP method**: For static HTML sites (faster, lighter)
  - Uses `requests` + `BeautifulSoup` + `lxml`
  - No browser required
- **Selenium method**: For JavaScript-rendered sites (e.g., Wanted)
  - Requires Chrome/Chromium browser
  - Uses headless Chrome with webdriver-manager
  - Automatically skips if Chrome not installed
  - 3-second wait for JavaScript rendering

### JobKorea Structured Extraction
JobKorea's HTML structure uses dynamically generated CSS class names (hashes like `__i0l0hl2`, `__344nw25`), making standard CSS selectors fragile. The parser uses a **configuration-driven structured extraction approach**:
- **Filter links** by `href*="Recruit/GI_Read"` attribute (stable)
- **Apply conditions**: Only links with `Typography` child elements (excludes logo links)
- **Use link order**: 1st link = title, 2nd link = company
- **Match semantic patterns**: `size18` for titles, `size16` for company names (not full hash)
- All filter conditions are defined in `config.yaml`, not hardcoded in parser
- See `parser.py:105-175` for `_matches_filter_conditions()` implementation

### Korean Text Matching
The matcher handles Korean text spacing variations:
- Removes spaces for comparison: "백엔드 개발자" matches "백엔드개발자"
- Word-level matching with partial matches
- False positive reduction for low-similarity matches
- See `matcher.py:28-97` for Korean-specific logic

### Deduplication Strategy
Jobs are deduplicated by composite ID: `{source}_{link}_{title}`
- Prevents same job from being notified multiple times
- History persisted in `job_history.json`
- Duplicate URLs within same scrape also filtered (see `scheduler.py:124-131`)

## Environment Variables

Email credentials can be set via `.env` file:
```bash
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password  # Gmail app password, not regular password
EMAIL_TO=recipient@gmail.com
```

**Gmail App Password Setup**:
1. Enable 2FA on Google Account
2. Go to Security → App passwords
3. Generate new app password
4. Use that password (not your regular Gmail password)

## Important Notes

### Site Scraping Ethics
- **Respect robots.txt** and site terms of service
- **Rate limiting**: 1-second delay between keyword searches (`scheduler.py:118`)
- **Recommended interval**: Minimum 30 minutes between checks
- **IP blocking risk**: Excessive requests may result in temporary IP bans

### Chrome/Chromium Requirement
- **Only required for Selenium-based sites** (Wanted)
- Other sites work fine without Chrome
- System auto-detects Chrome availability and skips Selenium sites if not found
- Install on Ubuntu/Debian: `sudo apt-get install chromium-browser`

### Timezone Handling
- All schedule times are **KST (Korea Standard Time, UTC+9)**
- Uses `pytz.timezone('Asia/Seoul')` for timezone-aware operations
- Current KST time logged on startup for verification

### Error Handling Philosophy
- **Fail gracefully**: If one site fails, continue with others
- **Skip unavailable resources**: Missing Chrome skips Selenium sites with warning
- **Preserve partial results**: Errors logged but don't crash entire check
- See `scheduler.py:119-122` for per-site error handling

## File Structure Context

```
recruit/
├── recruit/              # Main package (all core logic)
│   ├── parser.py        # 435 lines: Scraping logic + site-specific handling
│   ├── matcher.py       # 158 lines: Similarity calculation + Korean text
│   ├── scheduler.py     # 262 lines: Orchestration + scheduling + dedup
│   └── notifier.py      # 184 lines: Multi-channel notifications
├── tests/               # Test files (pytest)
│   ├── test_matcher.py
│   └── test_parser_debug.py
├── main.py              # Entry point (59 lines)
├── config.yaml          # User configuration
├── requirements.txt     # Python dependencies
├── job_history.json     # Auto-generated: seen job IDs
└── output/              # Auto-generated: saved job files
```

## Common Modification Patterns

### Adding a New Simple Site
1. Add site name to `sites` list in `config.yaml`
2. Add configuration to `sites_config` section
3. Choose `method: "http"` or `"selenium"` based on site rendering
4. Find CSS selectors using browser DevTools (F12 → right-click → Copy selector)
5. Test with one keyword first

Example:
```yaml
sites:
  - mysite

sites_config:
  - name: "mysite"
    url_template: "https://example.com/jobs?q={keyword}"
    method: "http"
    base_url: "https://example.com"
    selectors:
      job_list: "div.job-item"
      title: "h3.title"
      company: "span.company"
      link: "a.job-link"
```

### Adding a Complex Site (CSS-in-JS, Dynamic Classes)
When CSS class names contain hashes (e.g., `Typography_size18__abc123`), use structured extraction:

1. Identify stable attributes (e.g., `data-*`, `href` patterns)
2. Use `extraction.strategy: "structured"`
3. Define `link_filter` with conditions to filter out unwanted elements
4. Use `link_index` to select by position
5. Match semantic patterns (e.g., `size18`) instead of full class names

Example:
```yaml
sites_config:
  - name: "complexsite"
    method: "http"
    selectors:
      job_list: "div[data-card='job']"
      extraction:
        strategy: "structured"
        link_filter:
          selector: "a[href*='/job/']"
          has_child: "h3"                    # Only links with h3 children
          not_has_text: "광고"               # Exclude ads
        title:
          link_index: 0
          span_selector: "h3"
          class_pattern: "title"             # Match class containing "title"
        company:
          link_index: 1
          span_selector: "span"
          class_pattern: "company"
```

### Adding a New Notification Channel
1. Add new method to `Notifier` class (e.g., `notify_slack()`)
2. Add configuration section to `config.yaml` notifications
3. Call from `notify()` method in `notifier.py:175`

### Customizing Matching Logic
- Modify `JobMatcher.calculate_similarity()` for scoring algorithm
- Adjust `similarity_threshold` in `config.yaml` (0.0-1.0, default 0.3)
- Change title weight multiplier at `matcher.py:128` (currently 1.5x)

## Debugging Tips

### Parser Not Finding Jobs
1. Check if site structure changed (CSS selectors may be outdated)
2. Use browser DevTools to verify selectors still match
3. Enable debug logging: `logging.basicConfig(level=logging.DEBUG)`
4. Check `test_parser_debug.py` for parser testing utilities

### Jobs Not Matching
1. Verify keywords in `config.yaml` match actual job titles
2. Lower `similarity_threshold` for more results (may include false positives)
3. Check `exclude_keywords` aren't too broad
4. Test matching logic with `test_matcher.py`

### Email Not Sending
1. Verify Gmail app password (not regular password)
2. Check 2FA is enabled on Google account
3. Verify SMTP port 587 not blocked by firewall
4. Check `from_email`, `to_email`, `password` are set correctly
