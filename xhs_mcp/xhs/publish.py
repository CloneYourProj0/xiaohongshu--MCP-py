from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from .base import ActionContext, PlaywrightAction


PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official"


@dataclass(slots=True)
class PublishImageContent:
    title: str
    content: str
    image_paths: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass(slots=True)
class PublishVideoContent:
    title: str
    content: str
    video_path: str
    tags: List[str] = field(default_factory=list)


class _PublishBase(PlaywrightAction):
    def _goto_publish(self) -> None:
        page = self.page
        page.goto(PUBLISH_URL, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=30_000)

    def _remove_popover(self) -> None:
        page = self.page
        popover = page.locator("div.d-popover")
        if popover.count() == 0:
            return
        try:
            popover.first.evaluate("(el) => el.remove()")
        except Exception:
            pass
        page.mouse.click(420, 80)

    def _is_tab_blocked(self, element: Locator) -> bool:
        try:
            return element.evaluate(
                """
                (el) => {
                  const rect = el.getBoundingClientRect();
                  if (rect.width === 0 || rect.height === 0) return true;
                  const x = rect.left + rect.width / 2;
                  const y = rect.top + rect.height / 2;
                  const target = document.elementFromPoint(x, y);
                  return !(target === el || el.contains(target));
                }
                """
            )
        except Exception:
            return False

    def _select_tab(self, label: str) -> None:
        page = self.page
        page.locator("div.upload-content").first.wait_for(timeout=30_000)

        tab_candidates = [
            page.locator("div.creator-tab", has_text=label),
            page.locator("div.publish-tabs .tab-item", has_text=label),
            page.locator("button", has_text=label),
            page.locator("a", has_text=label),
            page.get_by_text(label, exact=True),
            page.get_by_text(label, exact=False),
        ]

        deadline = time.time() + 15
        while time.time() < deadline:
            for candidate in tab_candidates:
                count = candidate.count()
                if count == 0:
                    continue

                for index in range(count):
                    locator = candidate.nth(index)
                    try:
                        locator.wait_for(state="attached", timeout=2_000)
                    except PlaywrightTimeoutError:
                        continue

                    if not locator.is_visible():
                        continue

                    if self._is_tab_blocked(locator):
                        self._remove_popover()
                        time.sleep(0.2)
                        continue

                    try:
                        locator.click()
                        return
                    except Exception:
                        page.mouse.click(420, 80)
                        time.sleep(0.2)
                        continue

            time.sleep(0.2)

        raise RuntimeError(f"unable to select publish tab {label}")

    def _find_content_editor(self, page: Page) -> Locator:
        editor = page.locator("div.ql-editor").first
        try:
            editor.wait_for(timeout=5_000)
            return editor
        except PlaywrightTimeoutError:
            pass

        fallback = page.locator("[data-placeholder*='输入正文描述']").first
        fallback.wait_for(timeout=5_000)
        return fallback

    def _fill_text_and_tags(self, page: Page, title: str, content: str, tags: Iterable[str]) -> None:
        page.locator("div.d-input input").first.fill(title)

        editor = self._find_content_editor(page)
        editor.click()
        editor.fill("")
        if content:
            editor.type(content)

        normalized = [tag.lstrip("#") for tag in tags][:10]
        for tag in normalized:
            if not tag:
                continue
            editor.type("#" + tag + " ")
            time.sleep(0.2)


class PublishImageAction(_PublishBase):
    def __init__(self, ctx: ActionContext) -> None:
        super().__init__(ctx)
        self._goto_publish()
        self._select_tab("上传图文")

    def publish(self, payload: PublishImageContent) -> None:
        page = self.page
        files = [str(Path(p).expanduser()) for p in payload.image_paths if Path(p).expanduser().is_file()]
        if not files:
            raise ValueError("no valid image paths provided")

        file_input = page.locator(".upload-input input[type='file']")
        if file_input.count() == 0:
            file_input = page.locator("input[type='file']")
        file_input.first.set_input_files(files)

        preview = page.locator(".img-preview-area .pr")
        preview.nth(len(files) - 1).wait_for(timeout=120_000)

        self._fill_text_and_tags(page, payload.title, payload.content, payload.tags)
        page.locator("div.submit div.d-button-content").first.click()
        page.wait_for_timeout(3_000)


class PublishVideoAction(_PublishBase):
    def __init__(self, ctx: ActionContext) -> None:
        super().__init__(ctx)
        self._goto_publish()
        self._select_tab("上传视频")

    def publish(self, payload: PublishVideoContent) -> None:
        page = self.page
        video_path = Path(payload.video_path).expanduser()
        if not video_path.is_file():
            raise ValueError(f"video file not found: {video_path}")

        file_input = page.locator(".upload-input input[type='file']")
        if file_input.count() == 0:
            file_input = page.locator("input[type='file']")
        file_input.first.set_input_files(str(video_path))

        publish_btn = page.locator("button.publishBtn:not([disabled])")
        publish_btn.first.wait_for(state="visible", timeout=600_000)

        self._fill_text_and_tags(page, payload.title, payload.content, payload.tags)
        publish_btn.first.click()
        page.wait_for_timeout(3_000)
