from __future__ import annotations

import json

from playwright.sync_api import Page

from .base import PlaywrightAction


def _load_interact_state(page: Page, feed_id: str) -> tuple[bool, bool]:
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
        raise ValueError("no noteDetailMap in __INITIAL_STATE__")
    note_detail = json.loads(payload)
    detail = note_detail.get(feed_id) or {}
    interact = detail.get("note", {}).get("interactInfo", {})
    return bool(interact.get("liked")), bool(interact.get("collected"))


class LikeAction(PlaywrightAction):
    def like(self, feed_id: str, xsec_token: str) -> None:
        self._toggle(feed_id, xsec_token, target=True)

    def unlike(self, feed_id: str, xsec_token: str) -> None:
        self._toggle(feed_id, xsec_token, target=False)

    def _toggle(self, feed_id: str, xsec_token: str, target: bool) -> None:
        page: Page = self.page
        url = f"https://www.xiaohongshu.com/explore/{feed_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        try:
            liked, _ = _load_interact_state(page, feed_id)
        except Exception:
            liked = None

        if liked is not None:
            if target and liked:
                return
            if not target and not liked:
                return

        button = page.locator(".interact-container .left .like-lottie").first
        button.click()
        page.wait_for_timeout(2_000)

        try:
            liked_after, _ = _load_interact_state(page, feed_id)
            if liked_after == target:
                return
        except Exception:
            pass

        button.click()
        page.wait_for_timeout(1_000)


class FavoriteAction(PlaywrightAction):
    def favorite(self, feed_id: str, xsec_token: str) -> None:
        self._toggle(feed_id, xsec_token, target=True)

    def unfavorite(self, feed_id: str, xsec_token: str) -> None:
        self._toggle(feed_id, xsec_token, target=False)

    def _toggle(self, feed_id: str, xsec_token: str, target: bool) -> None:
        page: Page = self.page
        url = f"https://www.xiaohongshu.com/explore/{feed_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        try:
            _, collected = _load_interact_state(page, feed_id)
        except Exception:
            collected = None

        if collected is not None:
            if target and collected:
                return
            if not target and not collected:
                return

        button = page.locator(".interact-container .left .reds-icon.collect-icon").first
        button.click()
        page.wait_for_timeout(2_000)

        try:
            _, collected_after = _load_interact_state(page, feed_id)
            if collected_after == target:
                return
        except Exception:
            pass

        button.click()
        page.wait_for_timeout(1_000)

