from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .base import ActionContext, PlaywrightAction


@dataclass(slots=True)
class UserProfile:
    basic_info: Dict[str, Any] = field(default_factory=dict)
    interactions: List[Dict[str, Any]] = field(default_factory=list)
    feeds: List[Dict[str, Any]] = field(default_factory=list)


class UserProfileAction(PlaywrightAction):
    def user_profile(self, user_id: str, xsec_token: str) -> UserProfile:
        page: Page = self.page
        url = f"https://www.xiaohongshu.com/user/profile/{user_id}?xsec_token={xsec_token}&xsec_source=pc_note"
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=3_000)
        except PlaywrightTimeoutError:
            pass
        return self._extract_profile(page)

    def get_my_profile_via_sidebar(self) -> UserProfile:
        page: Page = self.page
        from .navigate import NavigateAction  # delayed import

        navigate = NavigateAction(ActionContext(page))
        navigate.to_profile_page()
        try:
            page.wait_for_load_state("networkidle", timeout=3_000)
        except PlaywrightTimeoutError:
            pass
        return self._extract_profile(page)

    def _extract_profile(self, page: Page) -> UserProfile:
        payload_user = page.evaluate(
            """
            () => {
              const state = window.__INITIAL_STATE__;
              if (!state || !state.user || !state.user.userPageData) return "";
              const target = state.user.userPageData;
              const value = target.value !== undefined ? target.value : target._value;
              return value ? JSON.stringify(value) : "";
            }
            """
        )
        if not payload_user:
            raise ValueError("userPageData not found in __INITIAL_STATE__")

        payload_notes = page.evaluate(
            """
            () => {
              const state = window.__INITIAL_STATE__;
              if (!state || !state.user || !state.user.notes) return "";
              const target = state.user.notes;
              const value = target.value !== undefined ? target.value : target._value;
              return value ? JSON.stringify(value) : "";
            }
            """
        )
        if not payload_notes:
            raise ValueError("user.notes not found in __INITIAL_STATE__")

        user_data = json.loads(payload_user)
        notes_data = json.loads(payload_notes)

        profile = UserProfile(
            basic_info=user_data.get("basicInfo", {}),
            interactions=user_data.get("interactions", []),
        )

        if isinstance(notes_data, list):
            for feeds in notes_data:
                if isinstance(feeds, list):
                    profile.feeds.extend(feeds)

        return profile
