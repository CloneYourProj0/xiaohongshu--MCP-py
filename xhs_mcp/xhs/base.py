from __future__ import annotations

from dataclasses import dataclass
from playwright.sync_api import Page


@dataclass
class ActionContext:
    """Lightweight wrapper carrying shared Playwright page and options."""

    page: Page


class PlaywrightAction:
    """Base class for actions that operate on a Playwright page."""

    def __init__(self, ctx: ActionContext) -> None:
        self.ctx = ctx

    @property
    def page(self) -> Page:
        return self.ctx.page

