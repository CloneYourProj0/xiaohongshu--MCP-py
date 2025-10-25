from __future__ import annotations

from playwright.sync_api import Page

from .base import PlaywrightAction


class NavigateAction(PlaywrightAction):
    def to_explore_page(self) -> None:
        page: Page = self.page
        page.goto("https://www.xiaohongshu.com/explore", wait_until="load")
        page.wait_for_selector("div#app", timeout=30_000)

    def to_profile_page(self) -> None:
        page: Page = self.page
        self.to_explore_page()
        page.wait_for_load_state("networkidle")
        profile_link = page.locator(
            "div.main-container li.user.side-bar-component a.link-wrapper span.channel"
        )
        profile_link.first.click()
        page.wait_for_load_state("load")

