from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlencode

from playwright.sync_api import Page

from .base import ActionContext, PlaywrightAction


@dataclass(slots=True)
class Feed:
    raw: Dict[str, Any]


@dataclass(slots=True)
class FilterOption:
    filters_index: int
    tags_index: int
    text: str


FILTER_OPTIONS_MAP: Dict[int, Tuple[FilterOption, ...]] = {
    1: (
        FilterOption(1, 1, "综合"),
        FilterOption(1, 2, "最新"),
        FilterOption(1, 3, "最多点赞"),
        FilterOption(1, 4, "最多评论"),
        FilterOption(1, 5, "最多收藏"),
    ),
    2: (
        FilterOption(2, 1, "不限"),
        FilterOption(2, 2, "视频"),
        FilterOption(2, 3, "图文"),
    ),
    3: (
        FilterOption(3, 1, "不限"),
        FilterOption(3, 2, "一天内"),
        FilterOption(3, 3, "一周内"),
        FilterOption(3, 4, "半年内"),
    ),
    4: (
        FilterOption(4, 1, "不限"),
        FilterOption(4, 2, "已看过"),
        FilterOption(4, 3, "未看过"),
        FilterOption(4, 4, "已关注"),
    ),
    5: (
        FilterOption(5, 1, "不限"),
        FilterOption(5, 2, "同城"),
        FilterOption(5, 3, "附近"),
    ),
}


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
    def search(self, keyword: str, filters: List[FilterOption] | None = None) -> List[Feed]:
        page: Page = self.page
        query = urlencode({"keyword": keyword, "source": "web_explore_feed"})
        page.goto(f"https://www.xiaohongshu.com/search_result?{query}", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        if filters:
            self._apply_filters(page, filters)

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

    def _apply_filters(self, page: Page, filters: List[FilterOption]) -> None:
        for opt in filters:
            if opt.filters_index not in FILTER_OPTIONS_MAP:
                raise ValueError(f"invalid filters_index {opt.filters_index}")
            options = FILTER_OPTIONS_MAP[opt.filters_index]
            if opt.tags_index < 1 or opt.tags_index > len(options):
                raise ValueError(
                    f"filter {opt.filters_index} tags_index {opt.tags_index} out of range"
                )

        filter_button = page.locator("div.filter")
        filter_button.first.hover()
        panel = page.locator("div.filter-panel")
        panel.wait_for(timeout=10_000)

        for opt in filters:
            selector = (
                f"div.filter-panel div.filters:nth-child({opt.filters_index}) "
                f"div.tags:nth-child({opt.tags_index})"
            )
            panel.locator(selector).first.click()
            time.sleep(0.3)

        page.wait_for_load_state("networkidle")


def get_filter_option(filters_index: int, text: str) -> FilterOption:
    options = FILTER_OPTIONS_MAP.get(filters_index)
    if not options:
        raise ValueError(f"filters_index {filters_index} not supported")
    for option in options:
        if option.text == text:
            return option
    raise ValueError(f"text '{text}' not found for filters_index {filters_index}")
