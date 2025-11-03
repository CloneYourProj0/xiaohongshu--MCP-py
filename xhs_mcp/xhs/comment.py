from __future__ import annotations

from playwright.sync_api import Page

from .base import PlaywrightAction


class CommentAction(PlaywrightAction):
    def post_comment(self, feed_id: str, xsec_token: str, content: str) -> None:
        page: Page = self.page
        url = f"https://www.xiaohongshu.com/explore/{feed_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
        page.goto(url,wait_until="domcontentloaded")

        print("进入目标页面")
        page.wait_for_timeout(3_000)  # 停留 3 秒

        # page.wait_for_load_state("networkidle")

        page.locator("div.input-box div.content-edit span").first.click()
        editor = page.locator("div.input-box div.content-edit p.content-input").first
        editor.fill(content)

        submit = page.locator("div.bottom button.submit").first
        submit.click()
        page.wait_for_timeout(1_000)

