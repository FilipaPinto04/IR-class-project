import hashlib
import os
import platform
import shutil
import requests
import pdfplumber
import io
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service


def is_valid_executable(path):
    if not os.path.isfile(path):
        return False
    if platform.system() == "Windows":
        return True
    return os.access(path, os.X_OK)


def find_chrome_executable():
    system = platform.system()
    chrome_paths = []

    if system == "Windows":
        possible_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Chromium', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Chromium', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Chromium', 'Application', 'chrome.exe'),
        ]
        chrome_paths.extend(possible_paths)
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
        chrome_paths.extend(['chrome-linux64/chrome'])

    elif system == "Darwin":
        possible_paths = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
        ]
        chrome_paths.extend(possible_paths)

    for chrome_path in chrome_paths:
        if is_valid_executable(chrome_path):
            print(f"Found Chrome at: {chrome_path}")
            return chrome_path

    for executable in ['google-chrome', 'chromium', 'chromium-browser', 'chrome']:
        chrome_in_path = shutil.which(executable)
        if chrome_in_path:
            print(f"Found Chrome in PATH: {chrome_in_path}")
            return chrome_in_path

    print("Chrome not found in default locations.")
    return None


class UMinhoDSpace8Scraper:
    def __init__(self, base_url, max_items=20, research_area=None, full_scrape_limit=20):
        if research_area:
            separator = "&" if "?" in base_url else "?"
            base_url = f"{base_url}{separator}query={research_area.replace(' ', '+')}"
            print(f"[REQ-B08] Filtering by research area: '{research_area}'")

        self.base_url = base_url
        chrome_options = Options()
        chrome_path = find_chrome_executable()

        if chrome_path is None:
            raise FileNotFoundError("Chrome executable not found.")

        chrome_options.binary_location = chrome_path
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.ANGULAR_SETTLE_TIME = 0.5
        self.MAX_ITEMS = max_items
        self.FULL_SCRAPE_LIMIT = full_scrape_limit

    def get_listing_info(self, item_element) -> dict:
        data = {
            "title": "N/A",
            "year": "N/A",
            "doi": "N/A",
            "abstract": "N/A",
            "authors": [],
            "affiliations": [],
            "pdf_link": None,
            "pdf_text_path": None,
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

        for selector in ["span.item-list-authors", ".item-list-author", ".authors"]:
            try:
                author_elems = item_element.find_elements(By.CSS_SELECTOR, selector)
                if author_elems:
                    data["authors"] = [a.text.strip() for a in author_elems if a.text.strip()]
                    break
            except NoSuchElementException:
                continue

        for selector in ["span.item-list-date", ".item-list-date", ".date"]:
            try:
                date_elem = item_element.find_element(By.CSS_SELECTOR, selector)
                data["year"] = date_elem.text.strip() or "N/A"
                break
            except NoSuchElementException:
                continue

        return data

    def get_paper_info(self, url, extract_pdf=True):
        """
        Visita a página /full de um documento, extrai metadados da tabela
        Dublin Core e tenta descarregar e ler o texto completo do PDF.
        """
        self.driver.get(url)

        # For new /entities/publication/ URLs, wait longer for Angular to render
        is_new_format = "/entities/publication/" in url

        try:
            self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "table.table-striped, ds-full-item-page table, .item-page table, table")
            ))
        except Exception:
            pass

        # Extra wait for new Angular format
        if is_new_format:
            time.sleep(self.ANGULAR_SETTLE_TIME + 1.5)
        else:
            time.sleep(self.ANGULAR_SETTLE_TIME)

        targets = {
            "dc.title":                   "title",
            "dc.date.issued":             "year",
            "dc.identifier.doi":          "doi",
            "dc.contributor.author":      "authors",
            "dc.description.abstract":    "abstract",
            "dc.identifier.uri":          "url",
            "dc.contributor.affiliation": "affiliations",
        }

        data = {
            "title":        "N/A",
            "year":         "N/A",
            "doi":          "N/A",
            "abstract":     "N/A",
            "authors":      [],
            "affiliations": [],
            "pdf_link":     None,
            "pdf_text_path": None,
            "url":          url.replace('/full', ''),
        }

        try:
            # Try multiple selectors to find metadata rows
            rows = self.driver.find_elements(
                By.CSS_SELECTOR, "table.table-striped tbody tr, table tbody tr"
            )

            # If no rows found and new format, try scrolling and waiting more
            if not rows and is_new_format:
                self.driver.execute_script("window.scrollTo(0, 300);")
                time.sleep(1.5)
                rows = self.driver.find_elements(
                    By.CSS_SELECTOR, "table tbody tr, tr"
                )

            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2:
                    field_label = cols[0].text.strip()
                    field_value = cols[1].text.strip()
                    if field_label in targets:
                        key = targets[field_label]
                        if key in ("authors", "affiliations"):
                            if field_value not in data[key]:
                                data[key].append(field_value)
                        else:
                            data[key] = field_value
        except Exception as e:
            print(f"Error parsing metadata for {url}: {e}")

        pdf_selectors = [
            "a.download-link", 
            "a[href*='/bitstreams/']", 
            "ds-file-download-link a", 
            "a[href*='download']",
            "a[href$='.pdf']"
        ]
        
        for selector in pdf_selectors:
            try:
                pdf_elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in pdf_elems:
                    href = elem.get_attribute("href")
                    if href and ("bitstream" in href or "download" in href or href.endswith(".pdf")):
                        data["pdf_link"] = href
                        break
                if data["pdf_link"]:
                    break
            except Exception:
                continue

        # Descarregar e ler o texto completo do PDF
        if data["pdf_link"] and extract_pdf:
            try:
                print(f"      A tentar descarregar PDF de: {data['pdf_link']}")
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                response = requests.get(
                    data["pdf_link"], headers=headers, timeout=30, stream=True
                )
                
                if response.status_code == 200:
                    pdf_bytes = io.BytesIO(response.content)
                    text_parts = []
                    with pdfplumber.open(pdf_bytes) as pdf:
                        total_pages = len(pdf.pages)
                        print(f"      -> A processar {total_pages} páginas do PDF...")
                        for page_num, page in enumerate(pdf.pages, 1):
                            page_text = page.extract_text()
                            if page_text:
                                text_parts.append(page_text.strip())
                            if page_num % 10 == 0 or page_num == total_pages:
                                print(f"         [Progresso: {page_num}/{total_pages} páginas lidas]")
                    if text_parts:
                        full_text = "\n\n".join(text_parts)
                        url_hash = hashlib.md5(data["url"].encode()).hexdigest() if data.get("url") else hashlib.md5(data["pdf_link"].encode()).hexdigest()
                        pdf_dir = os.path.join("docs", "pdf_texts")
                        os.makedirs(pdf_dir, exist_ok=True)
                        txt_path = os.path.join(pdf_dir, f"{url_hash}.txt")
                        with open(txt_path, "w", encoding="utf-8") as tf:
                            tf.write(full_text)
                        data["pdf_text_path"] = txt_path
                        print(f"      -> PDF guardado em: {txt_path} ({len(full_text)} caracteres)")
                    else:
                        print(f"      -> O PDF não contém texto extraível estruturado.")
                else:
                    print(f"      -> Falha no download (HTTP Status {response.status_code}).")
            except Exception as e:
                print(f"      -> Erro ao ler corpo do PDF: {e}")

        return data

    def go_to_next_page(self):
        next_button_xpath = (
            "//li[contains(@class, 'page-item') and not(contains(@class, 'disabled'))]/a[@aria-label='Next']"
            " | //a[@aria-label='Next' and not(ancestor::li[contains(@class,'disabled')])]"
            " | //button[@aria-label='Next' and not(@disabled)]"
        )
        try:
            next_button = self.driver.find_element(By.XPATH, next_button_xpath)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            next_button.click()
            time.sleep(self.ANGULAR_SETTLE_TIME + 2.5)
            return True
        except NoSuchElementException:
            raise NoSuchElementException("Reached the last page: 'Next' button is missing or disabled.")

    def collect_all_links(self):
        paper_items = []
        seen_urls: set = set()

        self.driver.get(self.base_url)
        print("Waiting for Angular to populate the item list...")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "ds-listable-object-component-loader")))
        time.sleep(self.ANGULAR_SETTLE_TIME)

        while True:
            items = self.driver.find_elements(By.TAG_NAME, "ds-listable-object-component-loader")

            if not items:
                if not paper_items:
                    print("Error: Could not find any item links in the list.")
                    return []
                print("No items found on this page. Stopping pagination.")
                break

            for item in items:
                try:
                    listing_data = self.get_listing_info(item)
                    if not listing_data["url"]:
                        continue
                    if listing_data["url"] not in seen_urls:
                        seen_urls.add(listing_data["url"])
                        paper_items.append(listing_data)
                        print(f"  [{len(paper_items)}] Found: {listing_data['url']}")
                    if len(paper_items) >= self.MAX_ITEMS:
                        print(f"Reached limit of {self.MAX_ITEMS} items.")
                        return paper_items
                except NoSuchElementException:
                    continue

            try:
                self.go_to_next_page()
            except NoSuchElementException:
                print("No more pages to scrape.")
                break

        return paper_items

    def scrape(self):
        results = []
        paper_items = []

        print(f"Loading collection list: {self.base_url}")
        print(f"  Collecting metadata for up to {self.MAX_ITEMS} documents.")
        print(f"  Full page scrape (abstract/PDF/pdf_text) for first {self.FULL_SCRAPE_LIMIT}.")

        try:
            paper_items = self.collect_all_links()
            print(f"Found {len(paper_items)} documents in listing.")

            for idx, item in enumerate(paper_items):
                full_url = item["url"] + "/full"
                extract_pdf = idx < self.FULL_SCRAPE_LIMIT

                if extract_pdf:
                    print(f"  [full+PDF {idx+1}/{self.FULL_SCRAPE_LIMIT}] {item['url']}")
                else:
                    print(f"  [full {idx+1}/{len(paper_items)}] {item['url']}")

                full_data = self.get_paper_info(full_url, extract_pdf=extract_pdf)
                item.update(full_data)
                print(f"      Title: {item['title']}")
                results.append(item)

        finally:
            self.driver.quit()

        return results

if __name__ == "__main__":
    import json
    import os

    BASE_URL = "https://repositorium.uminho.pt/collections/7eae6651-4038-4838-a1f1-6d827f4d9d06/search"
    RESEARCH_AREA = ""

    MAX_ITEMS = 100

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
    pdf_count  = sum(1 for r in results if r.get("pdf_text_path"))
    print(f"\nGuardados {len(results)} documentos.")
    print(f"  → {full_count} com abstract completo.")
    print(f"  → {pdf_count} com texto do PDF extraído.")