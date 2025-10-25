from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterable, Optional

import typer

from xhs_mcp.configs import get_chrome_executable, get_cookies_path
from xhs_mcp.infra.browser import launch, new_context, pw
from xhs_mcp.xhs.base import ActionContext
from xhs_mcp.xhs.comment import CommentAction
from xhs_mcp.xhs.feed_detail import FeedDetailAction
from xhs_mcp.xhs.feeds import Feed, FeedsListAction, FilterOption, SearchAction, get_filter_option
from xhs_mcp.xhs.like_favorite import FavoriteAction, LikeAction
from xhs_mcp.xhs.publish import (
    PublishImageAction,
    PublishImageContent,
    PublishVideoAction,
    PublishVideoContent,
)
from xhs_mcp.xhs.user_profile import UserProfileAction


app = typer.Typer(help="Manual testing CLI for action layer")


def _run_with_page(
    profile: Optional[str],
    cookies_path: Optional[str],
    bin_path: Optional[str],
    handler: Callable[[ActionContext], None],
    debug_dir: Optional[Path] = None,
    trace: bool = False,
) -> None:
    cpath = get_cookies_path(cookies_path, profile)
    chrome_bin = get_chrome_executable(bin_path)

    typer.echo(f"Using cookies: {cpath}")
    if chrome_bin:
        typer.echo(f"Using browser binary: {chrome_bin}")

    debug_dir_path = debug_dir.resolve() if debug_dir else None
    console_logs: list[str] = []

    with pw() as playwright:
        with launch(playwright, chrome_bin=chrome_bin) as browser:
            with new_context(browser, cpath) as ctx:
                if trace and debug_dir_path:
                    ctx.tracing.start(screenshots=True, snapshots=True, sources=True)

                page = ctx.new_page()

                if debug_dir_path is not None:
                    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

                try:
                    handler(ActionContext(page))
                finally:
                    if debug_dir_path is not None:
                        debug_dir_path.mkdir(parents=True, exist_ok=True)
                        dom_path = debug_dir_path / "dom.html"
                        dom_path.write_text(page.content(), encoding="utf-8")

                        screenshot_path = debug_dir_path / "page.png"
                        try:
                            page.screenshot(path=str(screenshot_path), full_page=True)
                        except Exception as exc:
                            typer.echo(f"Screenshot failed: {exc}")

                        log_path = debug_dir_path / "console.log"
                        log_path.write_text("\n".join(console_logs), encoding="utf-8")

                    if trace and debug_dir_path:
                        trace_path = debug_dir_path / "trace.zip"
                        ctx.tracing.stop(path=str(trace_path))


def _print_json(data) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))


def _parse_filters(raw_filters: Iterable[str]) -> list[FilterOption]:
    filters: list[FilterOption] = []
    for item in raw_filters:
        if ":" in item:
            group_str, text = item.split(":", 1)
            try:
                group = int(group_str)
            except ValueError as exc:
                raise typer.BadParameter(f"Invalid filters_index '{group_str}'") from exc
            filters.append(get_filter_option(group, text))
        else:
            raise typer.BadParameter("Filter format must be '<group>:<text>'")
    return filters


@app.command()
def feeds_list(
    profile: Optional[str] = typer.Option(None, help="Profile name"),
    cookies_path: Optional[str] = typer.Option(None, help="Explicit cookies path"),
    bin: Optional[str] = typer.Option(None, help="Chromium/Chrome binary path"),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Fetch homepage feeds and print JSON."""

    def handler(ctx: ActionContext) -> None:
        action = FeedsListAction(ctx)
        feeds: list[Feed] = action.get_feeds()
        _print_json([feed.raw for feed in feeds])

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


@app.command()
def search(
    keyword: str = typer.Argument(..., help="Search keyword"),
    filter_option: list[str] = typer.Option(
        [], "--filter", help="Filter in '<group>:<text>' format (e.g. '1:最新')"
    ),
    profile: Optional[str] = typer.Option(None),
    cookies_path: Optional[str] = typer.Option(None),
    bin: Optional[str] = typer.Option(None),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Search feeds with optional filters."""

    filters = _parse_filters(filter_option) if filter_option else None

    def handler(ctx: ActionContext) -> None:
        action = SearchAction(ctx)
        feeds = action.search(keyword, filters)
        _print_json([feed.raw for feed in feeds])

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


@app.command()
def feed_detail(
    feed_id: str = typer.Argument(...),
    xsec_token: str = typer.Argument(...),
    profile: Optional[str] = typer.Option(None),
    cookies_path: Optional[str] = typer.Option(None),
    bin: Optional[str] = typer.Option(None),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Fetch feed detail and comments."""

    def handler(ctx: ActionContext) -> None:
        action = FeedDetailAction(ctx)
        detail = action.get_detail(feed_id, xsec_token)
        _print_json({"note": detail.data, "comments": detail.comments})

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


@app.command()
def publish_image(
    title: str = typer.Argument(...),
    content: str = typer.Argument(...),
    image: list[Path] = typer.Option(..., exists=True, file_okay=True, dir_okay=False),
    tag: list[str] = typer.Option([], help="Tags, can repeat"),
    profile: Optional[str] = typer.Option(None),
    cookies_path: Optional[str] = typer.Option(None),
    bin: Optional[str] = typer.Option(None),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Publish an image note."""

    def handler(ctx: ActionContext) -> None:
        action = PublishImageAction(ctx)
        payload = PublishImageContent(
            title=title,
            content=content,
            image_paths=[str(p.resolve()) for p in image],
            tags=tag,
        )
        action.publish(payload)
        typer.echo("Publish image note triggered.")

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


@app.command()
def publish_video(
    title: str = typer.Argument(...),
    content: str = typer.Argument(...),
    video: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False),
    tag: list[str] = typer.Option([], help="Tags, can repeat"),
    profile: Optional[str] = typer.Option(None),
    cookies_path: Optional[str] = typer.Option(None),
    bin: Optional[str] = typer.Option(None),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Publish a video note."""

    def handler(ctx: ActionContext) -> None:
        action = PublishVideoAction(ctx)
        payload = PublishVideoContent(
            title=title,
            content=content,
            video_path=str(video.resolve()),
            tags=tag,
        )
        action.publish(payload)
        typer.echo("Publish video note triggered.")

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


@app.command()
def comment(
    feed_id: str = typer.Argument(...),
    xsec_token: str = typer.Argument(...),
    content: str = typer.Argument(...),
    profile: Optional[str] = typer.Option(None),
    cookies_path: Optional[str] = typer.Option(None),
    bin: Optional[str] = typer.Option(None),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Post a comment to a feed."""

    def handler(ctx: ActionContext) -> None:
        action = CommentAction(ctx)
        action.post_comment(feed_id, xsec_token, content)
        typer.echo("Comment submitted.")

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


@app.command()
def like(
    feed_id: str = typer.Argument(...),
    xsec_token: str = typer.Argument(...),
    profile: Optional[str] = typer.Option(None),
    cookies_path: Optional[str] = typer.Option(None),
    bin: Optional[str] = typer.Option(None),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Like a feed."""

    def handler(ctx: ActionContext) -> None:
        action = LikeAction(ctx)
        action.like(feed_id, xsec_token)
        typer.echo("Like attempted.")

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


@app.command()
def unlike(
    feed_id: str = typer.Argument(...),
    xsec_token: str = typer.Argument(...),
    profile: Optional[str] = typer.Option(None),
    cookies_path: Optional[str] = typer.Option(None),
    bin: Optional[str] = typer.Option(None),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Unlike a feed."""

    def handler(ctx: ActionContext) -> None:
        action = LikeAction(ctx)
        action.unlike(feed_id, xsec_token)
        typer.echo("Unlike attempted.")

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


@app.command()
def favorite(
    feed_id: str = typer.Argument(...),
    xsec_token: str = typer.Argument(...),
    profile: Optional[str] = typer.Option(None),
    cookies_path: Optional[str] = typer.Option(None),
    bin: Optional[str] = typer.Option(None),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Favorite a feed."""

    def handler(ctx: ActionContext) -> None:
        action = FavoriteAction(ctx)
        action.favorite(feed_id, xsec_token)
        typer.echo("Favorite attempted.")

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


@app.command()
def unfavorite(
    feed_id: str = typer.Argument(...),
    xsec_token: str = typer.Argument(...),
    profile: Optional[str] = typer.Option(None),
    cookies_path: Optional[str] = typer.Option(None),
    bin: Optional[str] = typer.Option(None),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Unfavorite a feed."""

    def handler(ctx: ActionContext) -> None:
        action = FavoriteAction(ctx)
        action.unfavorite(feed_id, xsec_token)
        typer.echo("Unfavorite attempted.")

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


@app.command()
def user_profile(
    user_id: str = typer.Argument(...),
    xsec_token: str = typer.Argument(...),
    profile: Optional[str] = typer.Option(None),
    cookies_path: Optional[str] = typer.Option(None),
    bin: Optional[str] = typer.Option(None),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Fetch user profile information."""

    def handler(ctx: ActionContext) -> None:
        action = UserProfileAction(ctx)
        profile_data = action.user_profile(user_id, xsec_token)
        _print_json(
            {
                "basic_info": profile_data.basic_info,
                "interactions": profile_data.interactions,
                "feeds": profile_data.feeds,
            }
        )

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


@app.command()
def my_profile(
    profile: Optional[str] = typer.Option(None),
    cookies_path: Optional[str] = typer.Option(None),
    bin: Optional[str] = typer.Option(None),
    debug_dir: Optional[Path] = typer.Option(None, help="Dump DOM/screenshot to this directory"),
    trace: bool = typer.Option(False, help="Capture Playwright trace inside debug directory"),
):
    """Fetch current logged-in user's profile via sidebar navigation."""

    def handler(ctx: ActionContext) -> None:
        action = UserProfileAction(ctx)
        profile_data = action.get_my_profile_via_sidebar()
        _print_json(
            {
                "basic_info": profile_data.basic_info,
                "interactions": profile_data.interactions,
                "feeds": profile_data.feeds,
            }
        )

    _run_with_page(profile, cookies_path, bin, handler, debug_dir, trace)


if __name__ == "__main__":
    app()
