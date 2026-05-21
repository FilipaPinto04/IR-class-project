import time
import os
import platform
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service



def is_valid_executable(path):
    """
    Check if a path points to a valid executable file.

    Args:
        path (str): Path to check.

    Returns:
        bool: True if the path is a valid executable file, False otherwise.
    """
    if not os.path.isfile(path):
        return False

    # On Windows, os.access with os.X_OK may not work reliably
    # so we just check if the file exists
    if platform.system() == "Windows":
        return True

    # On Unix-like systems, check if the file is executable
    return os.access(path, os.X_OK)


def find_chrome_executable():
    """
    Attempts to find Chrome executable in common installation locations.

    Checks for Chrome in default installation paths on both Windows and Linux.
    Returns the path to the Chrome executable if found, otherwise returns None.

    Returns:
        str or None: Path to Chrome executable if found, None otherwise.
    """
    system = platform.system()

    # List of common Chrome executable paths
    chrome_paths = []

    if system == "Windows":
        # Windows default installation paths
        possible_paths = [
            # Chrome stable
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            # Chromium
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Chromium', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Chromium', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Chromium', 'Application', 'chrome.exe'),
        ]
        chrome_paths.extend(possible_paths)

        # Also add hardcoded paths for Chrome
        chrome_paths.extend([
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
            'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
            'C:\\Users\\%USERNAME%\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe',
            'C:\\Program Files\\Chromium\\Application\\chrome.exe',
            'C:\\Program Files (x86)\\Chromium\\Application\\chrome.exe',
            'C:\\Users\\%USERNAME%\\AppData\\Local\\Chromium\\Application\\chrome.exe',
            'D:\\Portable\\chrome\\chrome.exe'
        ])

    elif system == "Linux":
        # Linux default installation paths
        possible_paths = [
            '/usr/bin/google-chrome',
            '/usr/local/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/local/bin/google-chrome-stable',
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
            '/usr/local/bin/chromium',
            '/usr/local/bin/chromium-browser',
            '/snap/bin/chromium',
            '/opt/google/chrome/chrome',
            '/opt/google/chrome/google-chrome',
        ]
        chrome_paths.extend(possible_paths)

        # Also add hardcoded paths for Chrome inside the project directory (for portable Chrome)
        chrome_paths.extend([
            'chrome-linux64/chrome'
        ])

    elif system == "Darwin":  # macOS
        possible_paths = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
        ]
        chrome_paths.extend(possible_paths)

    # Check each path
    for chrome_path in chrome_paths:
        if is_valid_executable(chrome_path):
            print(f"Found Chrome at: {chrome_path}")
            return chrome_path

    # If not found in common locations, check if 'google-chrome' or 'chromium' is in PATH
    for executable in ['google-chrome', 'chromium', 'chromium-browser', 'chrome']:
        chrome_in_path = shutil.which(executable)
        if chrome_in_path:
            print(f"Found Chrome in PATH: {chrome_in_path}")
            return chrome_in_path

    print("Chrome not found in default locations.")
    return None


class UMinhoDSpace8Scraper:
    def __init__(self, base_url, max_items=20, research_area=None, full_scrape_limit=20):
        """
        Initialize the web scraper with Selenium WebDriver configuration.
        Args:
            base_url (str): The base URL of the website to scrape.
            max_items (int, optional): Total number of items whose URLs/basic metadata
                are collected. Defaults to 20.
            full_scrape_limit (int, optional): Of those items, how many get a full page
                visit (abstract, PDF link, affiliations). Defaults to 20.
                Set higher than max_items to do a full scrape of everything (original
                behaviour). Set lower to keep bandwidth/time down while still having
                basic metadata for a larger collection.
            research_area (str, optional): Filter by research area/subject (REQ-B08).
                Appended as a query parameter, e.g. 'machine learning'.
        Note:
            Automatically detects Chrome in default installation locations on Windows and Linux.
            If you don't have Chrome, you can download a portable version from:
            https://googlechromelabs.github.io/chrome-for-testing/#stable
        """
        # REQ-B08: Append research area filter to the base URL if provided
        if research_area:
            separator = "&" if "?" in base_url else "?"
            base_url = f"{base_url}{separator}query={research_area.replace(' ', '+')}"
            print(f"[REQ-B08] Filtering by research area: '{research_area}'")

        self.base_url = base_url
        chrome_options = Options()

        # Try to find Chrome in default installation locations
        chrome_path = find_chrome_executable()

        if chrome_path is None:
            raise FileNotFoundError("Chrome executable not found. Please install Chrome or provide a portable version.")

        chrome_options.binary_location = chrome_path
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

        # Time to wait for Angular to settle after page loads
        self.ANGULAR_SETTLE_TIME = 0.5  # seconds
        # Total items to collect URLs/basic metadata for
        self.MAX_ITEMS = max_items
        # Of those, how many get a full page visit (abstract, PDF, affiliations)
        self.FULL_SCRAPE_LIMIT = full_scrape_limit

    def get_listing_info(self, item_element) -> dict:
        """
        Extracts basic metadata directly from the listing page element —
        no extra page visit required.

        Returns a dict with: url, title, authors, year.
        abstract, doi, pdf_link, and affiliations are left empty/None;
        they are filled in by get_paper_info() only for the first
        ``FULL_SCRAPE_LIMIT`` documents.
        """
        data = {
            "title": "N/A",
            "year": "N/A",
            "doi": "N/A",
            "abstract": "N/A",
            "authors": [],
            "affiliations": [],
            "pdf_link": None,
            "url": None,
        }
        try:
            title_elem = item_element.find_element(By.CSS_SELECTOR, "a.item-list-title")
            data["title"] = title_elem.text.strip() or "N/A"
            href = title_elem.get_attribute("href")
            if href:
                data["url"] = href.split("?")[0]
        except NoSuchElementException:
            pass

        # Authors shown in the listing card (class varies across DSpace themes)
        for selector in ["span.item-list-authors", ".item-list-author", ".authors"]:
            try:
                author_elems = item_element.find_elements(By.CSS_SELECTOR, selector)
                if author_elems:
                    data["authors"] = [a.text.strip() for a in author_elems if a.text.strip()]
                    break
            except NoSuchElementException:
                continue

        # Publication date shown in the listing card
        for selector in ["span.item-list-date", ".item-list-date", ".date"]:
            try:
                date_elem = item_element.find_element(By.CSS_SELECTOR, selector)
                data["year"] = date_elem.text.strip() or "N/A"
                break
            except NoSuchElementException:
                continue

        return data

    def get_paper_info(self, url):
        """
        Given a paper URL, navigates to it and extracts metadata from the table.
        Supports both old (/handle/) and new (/entities/publication/) DSpace 8 URL formats.
        
        Args:
            url (str): The URL of the specific paper's full metadata view.
            
        Returns:
            dict: A dictionary containing the mapped Dublin Core metadata fields.
        """
        self.driver.get(url)

        # Wait for metadata table — supports both old (table.table-striped) and
        # new (/entities/publication/) DSpace 8 URL formats where the table has no class
        try:
            self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "table.table-striped, ds-full-item-page table, .item-page table, table")
            ))
        except Exception:
            pass  # Continue anyway — maybe partial content loaded

        time.sleep(self.ANGULAR_SETTLE_TIME)

        # Dictionary to store the mapping we want
        # This is our "Shopping List" - Key: what the HTML says, Value: what we want in our JSON
        targets = {
            "dc.title": "title",
            "dc.date.issued": "year",
            "dc.identifier.doi": "doi",
            "dc.contributor.author": "authors",
            "dc.description.abstract": "abstract",
            "dc.identifier.uri": "url",          # Crucial for the indexer to link words back to the source
            "dc.contributor.affiliation": "affiliations",  # REQ-B05: author affiliations
        }

        # Initialize the data structure with default values
        data = { 
            "title": "N/A", 
            "year": "N/A", 
            "doi": "N/A", 
            "abstract": "N/A", 
            "authors": [], 
            "affiliations": [],   # REQ-B05
            "pdf_link": None,     # REQ-B04
            "url": url.replace('/full', ''), # Fallback URL in case dc.identifier.uri is missing
        }

        try:
            # Locate all rows in the metadata table
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table.table-striped tbody tr, table tbody tr")
            
            for row in rows:
                # In DSpace 8, metadata is usually structured in two columns: Label and Value
                cols = row.find_elements(By.TAG_NAME, "td")
                
                if len(cols) >= 2:
                    field_label = cols[0].text.strip()
                    field_value = cols[1].text.strip()

                    # Check if the current field label is one of our required targets
                    if field_label in targets:
                        key = targets[field_label]
                        
                        # Handle multiple authors/affiliations (append to list) vs singular fields (overwrite)
                        if key in ("authors", "affiliations"):
                            data[key].append(field_value)
                        else:
                            data[key] = field_value

        except Exception as e:
            # Catch and log any parsing errors without crashing the entire scraping process
            print(f"Error parsing metadata for {url}: {e}")

        # REQ-B04: Extract PDF download link from the page
        try:
            pdf_elem = self.driver.find_element(By.CSS_SELECTOR, "a[href*='.pdf'], a[href*='/bitstream/']")
            data["pdf_link"] = pdf_elem.get_attribute("href")
        except NoSuchElementException:
            pass  # No PDF link found, keep None

        return data

    def go_to_next_page(self):
        """
        Attempts to click the next page button.
        Raises NoSuchElementException if the button is missing or disabled.
        """
        # XPath looking for an active (not disabled) 'Next' button
        next_button_xpath = "//li[contains(@class, 'page-item') and not(contains(@class, 'disabled'))]/a[@aria-label='Next']"

        try:
            next_button = self.driver.find_element(By.XPATH, next_button_xpath)

            # Scroll and Click
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            next_button.click()

            # Wait for Angular to swap the content, Slightly longer wait after clicking
            time.sleep(self.ANGULAR_SETTLE_TIME + 1)
            return True

        except NoSuchElementException:
            # Re-raising the exception so the caller knows to stop the loop
            raise NoSuchElementException("Reached the last page: 'Next' button is missing or disabled.")

    def collect_all_links(self):
        """
        Iterates through pagination to collect paper URLs up to self.MAX_ITEMS.
        1. Loads the initial collection page.
        2. Extracts paper links from each item on the page.
        3. Navigates to the next page until no more pages or limit reached.
        4. Returns a list of unique paper URLs.
        """
        paper_items = []
        seen_urls: set = set()

        # Load the initial collection page
        self.driver.get(self.base_url)

        # Wait for the Angular component that holds the item list
        print("Waiting for Angular to populate the item list...")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "ds-listable-object-component-loader")))

        # Give it a moment to render the links inside those components
        time.sleep(self.ANGULAR_SETTLE_TIME)

        while True:

            # 1. Locate all paper containers on the current page
            items = self.driver.find_elements(By.TAG_NAME, "ds-listable-object-component-loader")

            # Handle cases where the page didn't load any items
            if not items:
                if not paper_items:
                    print("Error: Could not find any item links in the list.")
                    return []
                print("No items found on this page. Stopping pagination.")
                break

            # 2. Extract links and basic listing metadata from each item
            for item in items:
                try:
                    listing_data = self.get_listing_info(item)
                    if not listing_data["url"]:
                        continue

                    if listing_data["url"] not in seen_urls:
                        seen_urls.add(listing_data["url"])
                        paper_items.append(listing_data)
                        print(f"  [{len(paper_items)}] Found: {listing_data['url']}")

                    # Stop immediately if we hit the limit
                    if len(paper_items) >= self.MAX_ITEMS:
                        print(f"Reached limit of {self.MAX_ITEMS} items.")
                        return paper_items

                except NoSuchElementException:
                    continue  # Skip items that don't have a title link

            # 3. Attempt to move to the next page
            try:
                self.go_to_next_page()
            except NoSuchElementException:
                print("No more pages to scrape.")
                break

        return paper_items

    def scrape(self):
        """
        Two-tier scraping strategy:

        Tier 1 — Listing metadata (up to ``MAX_ITEMS`` documents):
            Collected directly from the search results page without visiting
            each document. Provides: url, title, authors, year.

        Tier 2 — Full metadata (first ``FULL_SCRAPE_LIMIT`` documents only):
            Visits each document's /full page to extract the complete set:
            abstract, DOI, PDF link, affiliations.
            Documents beyond the limit keep the listing-level metadata.

        This lets you index a large collection for search purposes while
        limiting the time/bandwidth cost of full page visits.
        """
        results = []
        paper_items = []

        print(f"Loading collection list: {self.base_url}")
        print(f"  Collecting metadata for up to {self.MAX_ITEMS} documents.")
        print(f"  Full page scrape (abstract/PDF) for first {self.FULL_SCRAPE_LIMIT}.")

        try:
            # ── Tier 1: collect basic metadata from the listing pages ────────
            paper_items = self.collect_all_links()
            print(f"Found {len(paper_items)} documents in listing.")

            # ── Tier 2: enrich first FULL_SCRAPE_LIMIT docs with full metadata ─
            for idx, item in enumerate(paper_items):
                if idx < self.FULL_SCRAPE_LIMIT:
                    full_url = item["url"] + "/full"
                    print(f"  [full {idx+1}/{self.FULL_SCRAPE_LIMIT}] {item['url']}")
                    full_data = self.get_paper_info(full_url)
                    # Merge: full_data wins for every field it has
                    item.update(full_data)
                else:
                    print(f"  [listing only] {item['url']}")

                print(f"      Title: {item['title']}")
                results.append(item)

        finally:
            self.driver.quit()

        return results

if __name__ == "__main__":
    import json
    import os

    BASE_URL = "https://repositorium.uminho.pt/search?f.entityType=Publication,equals"

    # REQ-B08: Optionally filter by research area (set to None to disable)
    RESEARCH_AREA = ""  # e.g. "machine learning" or "health"

    # Total documents to collect basic metadata for (url, title, authors, year)
    MAX_ITEMS = 50

    # Of those, how many get a full page visit (abstract, DOI, PDF, affiliations).
    # Set equal to MAX_ITEMS to do a full scrape of everything (original behaviour).
    FULL_SCRAPE_LIMIT = 20

    scraper = UMinhoDSpace8Scraper(
        base_url=BASE_URL,
        max_items=MAX_ITEMS,
        research_area=RESEARCH_AREA,
        full_scrape_limit=FULL_SCRAPE_LIMIT,
    )
    results = scraper.scrape()

    os.makedirs("data", exist_ok=True)
    with open("data/scraper_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    full_count = sum(1 for r in results if r.get("abstract") not in ("N/A", None, ""))
    print(f"\nGuardados {len(results)} documentos.")
    print(f"  → {full_count} com abstract completo (full scrape).")
    print(f"  → {len(results) - full_count} só com metadados de listagem.")