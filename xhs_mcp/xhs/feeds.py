from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode

from playwright.sync_api import Page

from .base import ActionContext, PlaywrightAction


@dataclass(slots=True)
class Feed:
    raw: Dict[str, Any]


class FeedsListAction(PlaywrightAction):
    def __init__(self, ctx: ActionContext) -> None:
        super().__init__(ctx)
        self.page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded")
        # TODO(debug): remove after验证首页数据。记录 DOMContentLoaded 后的页面截图。
        debug_dir = Path("debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(debug_dir / "feeds_after_domcontentloaded.png"), full_page=True)
        # self.page.wait_for_load_state("networkidle")

    def get_feeds(self) -> List[Feed]:
        page = self.page
        page.wait_for_timeout(3_000)
        # TODO(debug): remove after验证首页数据。记录额外等待后的页面截图。
        debug_dir = Path("debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(debug_dir / "feeds_after_wait.png"), full_page=True)
        payload = page.evaluate(
            """
            () => {
              const state = window.__INITIAL_STATE__;
              if (!state || !state.feed || !state.feed.feeds) return "";
              const feeds = state.feed.feeds;
              const value = feeds.value !== undefined ? feeds.value : feeds._value;
              return value ? JSON.stringify(value) : "";
            }
            """
        )
        if not payload:
            raise ValueError("no feeds found in __INITIAL_STATE__")
        data = json.loads(payload)
        return [Feed(raw=item) for item in data]


class SearchAction(PlaywrightAction):
    def search(self, keyword: str) -> List[Feed]:
        page: Page = self.page
        query = urlencode({"keyword": keyword, "source": "web_explore_feed"})
        page.goto(f"https://www.xiaohongshu.com/search_result?{query}", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        payload = page.evaluate(
            """
            () => {
              const state = window.__INITIAL_STATE__;
              if (!state || !state.search || !state.search.feeds) return "";
              const feeds = state.search.feeds;
              const value = feeds.value !== undefined ? feeds.value : feeds._value;
              return value ? JSON.stringify(value) : "";
            }
            """
        )
        if not payload:
            raise ValueError("no search feeds found in __INITIAL_STATE__")
        data = json.loads(payload)
        return [Feed(raw=item) for item in data]
