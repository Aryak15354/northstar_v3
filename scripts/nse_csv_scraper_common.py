#!/usr/bin/env python3
"""Shared Selenium helpers for NSE CSV download scrapers."""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

NSE_BASE_URL = "https://www.nseindia.com"
DEFAULT_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9",
}


def _compact_text(value: object) -> str:
    return "".join(str(value or "").strip().upper().split())


def create_driver(download_dir: Path) -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    chrome_options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir.resolve()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)


def create_nse_session(*, referer: str | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_NSE_HEADERS)
    session.headers.setdefault("Accept", "application/json,text/plain,*/*")
    if referer:
        session.headers["Referer"] = str(referer)
    return session


def bootstrap_nse_session(
    session: requests.Session,
    *,
    referer: str | None = None,
    timeout: int = 30,
) -> None:
    bootstrap_urls: list[str] = [
        NSE_BASE_URL,
        f"{NSE_BASE_URL}/market-data/live-equity-market",
    ]
    if referer:
        bootstrap_urls.insert(1, str(referer))

    seen: set[str] = set()
    for url in bootstrap_urls:
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            session.get(url, timeout=timeout)
        except Exception:
            continue


def nse_request(
    session: requests.Session,
    url: str,
    *,
    params: dict | None = None,
    referer: str | None = None,
    timeout: int | tuple[int, int] = (30, 180),
    max_attempts: int = 4,
    backoff_seconds: float = 1.5,
) -> requests.Response:
    last_error: Exception | None = None
    retriable_status = {401, 403, 429, 500, 502, 503, 504}

    for attempt in range(1, max_attempts + 1):
        if referer:
            session.headers["Referer"] = str(referer)
        bootstrap_nse_session(session, referer=referer, timeout=30)
        try:
            response = session.get(url, params=params, timeout=timeout)
            if int(response.status_code) in retriable_status:
                last_error = RuntimeError(f"NSE returned HTTP {response.status_code} for {url}")
            else:
                response.raise_for_status()
                return response
        except Exception as exc:  # noqa: BLE001
            last_error = exc

        if attempt < max_attempts:
            time.sleep(backoff_seconds * attempt)

    if last_error is None:
        raise RuntimeError(f"NSE request failed for {url}")
    raise last_error


def cleanup_download_dir(download_dir: Path, file_pattern: str) -> None:
    for path in download_dir.glob(file_pattern):
        try:
            path.unlink()
        except Exception:
            continue
    for pattern in ("*.crdownload", "*.part"):
        for path in download_dir.glob(pattern):
            try:
                path.unlink()
            except Exception:
                continue


def click_matching_element(driver: webdriver.Chrome, text_options: list[str], *, occurrence: int = 1) -> bool:
    normalized_targets = [_compact_text(text) for text in text_options]
    exact_matches: list[tuple[object, str]] = []
    partial_matches: list[tuple[object, str]] = []

    for tag_name in ("button", "a"):
        for element in driver.find_elements(By.TAG_NAME, tag_name):
            try:
                element_text = element.text.strip()
                compact_text = _compact_text(element_text)
                if not compact_text:
                    continue
                if compact_text in normalized_targets:
                    exact_matches.append((element, element_text))
                elif any(target in compact_text for target in normalized_targets):
                    partial_matches.append((element, element_text))
            except Exception:
                continue

    matches = exact_matches + partial_matches
    if occurrence < 1 or len(matches) < occurrence:
        return False

    element, element_text = matches[occurrence - 1]
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", element)
        print(f"   ✓ Clicked: {element_text.strip().upper()}")
        return True
    except Exception:
        return False


def wait_for_csv_download(download_dir: Path, file_pattern: str, timeout: int = 30) -> Path | None:
    print("   Waiting for CSV download...")
    initial_csvs = set(download_dir.glob(file_pattern))
    start = time.time()

    while time.time() - start < timeout:
        current_csvs = set(download_dir.glob(file_pattern))
        new_csvs = current_csvs - initial_csvs
        if new_csvs:
            time.sleep(2)
            return sorted(new_csvs, key=lambda path: path.stat().st_mtime, reverse=True)[0]

        if current_csvs:
            latest = max(current_csvs, key=lambda path: path.stat().st_mtime)
            if time.time() - latest.stat().st_mtime < 30:
                return latest

        time.sleep(1)

    all_csvs = list(download_dir.glob(file_pattern))
    if all_csvs:
        return max(all_csvs, key=lambda path: path.stat().st_mtime)
    return None


def enable_window_open_capture(driver: webdriver.Chrome) -> None:
    driver.execute_script(
        """
        window.__nseCapturedOpenUrl = null;
        window.__nseOriginalOpen = window.__nseOriginalOpen || window.open;
        window.open = function(url) {
            window.__nseCapturedOpenUrl = url;
            return window.__nseOriginalOpen.apply(this, arguments);
        };
        """
    )


def get_captured_window_open_url(driver: webdriver.Chrome) -> str | None:
    value = driver.execute_script("return window.__nseCapturedOpenUrl || null;")
    return str(value).strip() if value else None


def download_csv_via_browser_session(
    driver: webdriver.Chrome,
    csv_url: str,
    download_dir: Path,
    *,
    default_filename: str,
    timeout=30,
) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    full_url = urljoin("https://www.nseindia.com", csv_url)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/csv,application/octet-stream,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": driver.current_url,
        }
    )
    for cookie in driver.get_cookies():
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain") or "www.nseindia.com",
            path=cookie.get("path") or "/",
        )

    response = session.get(full_url, timeout=timeout, allow_redirects=True)
    response.raise_for_status()

    content_type = str(response.headers.get("Content-Type", "")).lower()
    if "text/html" in content_type:
        raise RuntimeError(f"Expected CSV response, got HTML from {full_url}")

    disposition = response.headers.get("Content-Disposition", "")
    filename_match = re.search(r'filename="?([^";]+)"?', disposition)
    filename = filename_match.group(1).strip() if filename_match else default_filename
    output_path = download_dir / filename
    output_path.write_bytes(response.content)
    return output_path


def download_csv_via_nse_api(
    *,
    api_url: str,
    referer: str,
    download_dir: Path,
    default_filename: str,
    params: dict | None = None,
    timeout: int | tuple[int, int] = (30, 180),
    max_attempts: int = 4,
) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    session = create_nse_session(referer=referer)
    response = nse_request(
        session,
        api_url,
        params=params,
        referer=referer,
        timeout=timeout,
        max_attempts=max_attempts,
    )

    content_type = str(response.headers.get("Content-Type", "")).lower()
    body_prefix = response.text[:256].lower() if response.text else ""
    if "text/html" in content_type or "<html" in body_prefix:
        raise RuntimeError(f"Expected CSV/JSON payload, got HTML from {api_url}")

    disposition = response.headers.get("Content-Disposition", "")
    filename_match = re.search(r'filename="?([^";]+)"?', disposition)
    filename = filename_match.group(1).strip() if filename_match else default_filename
    output_path = download_dir / filename
    output_path.write_bytes(response.content)
    return output_path


def store_raw_download(downloaded_path: Path, raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / downloaded_path.name
    if downloaded_path.resolve() != destination.resolve():
        shutil.copy2(downloaded_path, destination)
    return destination
