from __future__ import annotations

import time
from typing import Tuple

from playwright.sync_api import Page


EXPLORE_URL = "https://www.xiaohongshu.com/explore"
LOGIN_QR_SELECTOR = ".login-container .qrcode-img"
LOGGED_IN_SELECTOR = ".main-container .user .link-wrapper .channel"


def check_login_status(page: Page, *, wait_load: bool = True) -> bool:
    # Navigate to explore page and wait for basic DOM ready for faster checks
    page.goto(EXPLORE_URL, wait_until="domcontentloaded")
    if wait_load:
        # Small grace period for dynamic elements
        time.sleep(0.5)
    try:
        el = page.query_selector(LOGGED_IN_SELECTOR)
        return el is not None
    except Exception:
        # Treat any transient error as not logged in
        return False


def fetch_qrcode_image(
    page: Page,
    *,
    timeout_seconds: int = 240,
    poll_interval: float = 0.5,
    reload_interval: float = 10.0,
    verbose: bool = False,
) -> Tuple[str | None, bool]:
    """Robustly fetch QR image src or detect logged-in state.

    Returns a tuple (src, logged_in):
    - If already logged in: (None, True)
    - If QR found: (src, False)
    - If timed out: (None, False)
    """

    # Navigate and use DOMContentLoaded for faster readiness
    page.goto(EXPLORE_URL, wait_until="domcontentloaded")
    deadline = time.time() + max(0, timeout_seconds)
    last_reload = time.time()

    while time.time() < deadline:
        # 1) Check login state first
        try:
            if page.query_selector(LOGGED_IN_SELECTOR):
                if verbose:
                    print("[fetch_qrcode_image] Detected logged-in status.")
                return None, True
        except Exception:
            # ignore intermittent failures
            pass

        # 2) Try to locate QR image element
        try:
            el = page.query_selector(LOGIN_QR_SELECTOR)
            if el:
                src = el.get_attribute("src")
                if src:
                    if verbose:
                        print("[fetch_qrcode_image] QR src fetched.")
                    return src, False
        except Exception:
            # swallow and retry
            pass

        # 3) Prefer waiting for network idle briefly; fallback to sleep
        try:
            page.wait_for_load_state("networkidle", timeout=int(max(1, poll_interval * 1000)))
        except Exception:
            time.sleep(poll_interval)

        # 4) Periodically reload to recover from dynamic modal/DOM issues
        now = time.time()
        if now - last_reload >= max(1.0, reload_interval):
            last_reload = now
            try:
                if verbose:
                    print("[fetch_qrcode_image] Reloading page to recover...")
                page.reload(wait_until="domcontentloaded")
            except Exception:
                # ignore reload failures
                pass

    # Timed out without login or QR src
    if verbose:
        print("[fetch_qrcode_image] Timeout without QR.")
    return None, False


def wait_for_login(
    page: Page,
    *,
    timeout_seconds: int | None = 240,
    deadline: float | None = None,
    poll_interval: float = 0.5,
    verbose: bool = False,
) -> bool:
    """Wait until logged-in selector appears.

    Accepts either timeout_seconds or an absolute deadline (epoch seconds).
    """
    if deadline is None:
        deadline = time.time() + (timeout_seconds or 0)
    while time.time() < deadline:
        try:
            if page.query_selector(LOGGED_IN_SELECTOR):
                if verbose:
                    print("[wait_for_login] Logged in detected.")
                return True
        except Exception:
            pass
        # brief attempt to reach network idle to speed up DOM settling
        try:
            page.wait_for_load_state("networkidle", timeout=int(max(1, poll_interval * 1000)))
        except Exception:
            time.sleep(poll_interval)
    if verbose:
        print("[wait_for_login] Timeout waiting for login.")
    return False
