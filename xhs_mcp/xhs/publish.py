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
        self.page.goto(PUBLISH_URL, wait_until="domcontentloaded")
        self.page.wait_for_load_state("networkidle")

    def _select_tab(self, label: str) -> None:
        page = self.page
        tab = page.locator("div.creator-tab", has_text=label)
        tab.first.wait_for(timeout=30_000)
        for _ in range(10):
            try:
                tab.first.click()
                return
            except Exception:
                page.mouse.click(420, 80)
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

