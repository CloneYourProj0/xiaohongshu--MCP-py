from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .base import ActionContext, PlaywrightAction


@dataclass(slots=True)
class FeedDetail:
    data: Dict[str, Any]
    comments: Dict[str, Any]


class FeedDetailAction(PlaywrightAction):
    def get_detail(self, feed_id: str, xsec_token: str) -> FeedDetail:
        page: Page = self.page
        url = f"https://www.xiaohongshu.com/explore/{feed_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=3_000)
        except PlaywrightTimeoutError:
            pass

        payload = page.evaluate(
            """
            () => {
              const state = window.__INITIAL_STATE__;
              if (!state || !state.note || !state.note.noteDetailMap) return "";
              return JSON.stringify(state.note.noteDetailMap);
            }
            """
        )
        if not payload:
            raise ValueError("no noteDetailMap found in __INITIAL_STATE__")

        note_detail_map = json.loads(payload)
        detail = note_detail_map.get(feed_id)
        if not detail:
            raise ValueError(f"feed {feed_id} not found in noteDetailMap")

        note = detail.get("note", {})
        comments = detail.get("comments", {})
        return FeedDetail(data=note, comments=comments)
