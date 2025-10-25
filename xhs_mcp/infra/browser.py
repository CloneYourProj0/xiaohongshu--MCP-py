from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Iterator

from playwright.sync_api import Browser, BrowserContext, Playwright, sync_playwright
from .cookies import load_storage_state


def _stealth_context_args() -> dict:
    # Basic stealth: disable headless signals, tweak user agent, and reduce automation signals
    # Note: Further hardening may require patched Chromium or undetected-chromedriver-like tweaks.
    return {
        "java_script_enabled": True,
        "ignore_https_errors": True,
        "bypass_csp": True,
        "locale": "zh-CN",
        # Reduce automation fingerprints
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
    }


@contextlib.contextmanager
def launch(playwright: Playwright, chrome_bin: str | None = None) -> Iterator[Browser]:
    # Prefer Chromium; allow custom executable to reduce detection.
    chromium = playwright.chromium
    launch_args = {
        "headless": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=site-per-process",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-web-security",
            "--lang=zh-CN",
        ],
    }
    if chrome_bin:
        launch_args["executable_path"] = chrome_bin

    browser = chromium.launch(**launch_args)
    try:
        yield browser
    finally:
        browser.close()


@contextlib.contextmanager
def new_context(browser: Browser, storage_state_path: Path | None = None) -> Iterator[BrowserContext]:
    ctx_args = _stealth_context_args()
    if storage_state_path and storage_state_path.exists():
        # Only inject storage_state if the file contains valid JSON
        state = load_storage_state(storage_state_path)
        if state is not None:
            ctx_args["storage_state"] = state
    context = browser.new_context(**ctx_args)
    try:
        yield context
    finally:
        context.close()


@contextlib.contextmanager
def pw() -> Iterator[Playwright]:
    p = sync_playwright().start()
    try:
        yield p
    finally:
        p.stop()
