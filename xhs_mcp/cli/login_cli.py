from __future__ import annotations

import base64
from pathlib import Path

import typer
from playwright.sync_api import Error as PWError

from xhs_mcp.configs import get_cookies_path, get_chrome_executable
from xhs_mcp.infra.browser import pw, launch, new_context
from xhs_mcp.infra.cookies import save_storage_state
from xhs_mcp.xhs.login import check_login_status, fetch_qrcode_image, wait_for_login
import os
import sys
from typing import Optional

try:
    import requests  # type: ignore
except Exception:
    requests = None  # lazy optional: only needed if QR src is http(s)


app = typer.Typer(help="Headless login CLI for xiaohongshu-mcp-py")


@app.command()
def check(
    profile: str | None = typer.Option(None, help="Profile name to select cookies file"),
    cookies_path: str | None = typer.Option(None, help="Explicit cookies storage_state file path"),
    bin: str | None = typer.Option(None, help="Chromium/Chrome executable path"),
):
    """Check if current cookies indicate a logged-in session."""
    cpath = get_cookies_path(cookies_path, profile)
    chrome_bin = get_chrome_executable(bin)
    with pw() as p:
        with launch(p, chrome_bin=chrome_bin) as browser:
            with new_context(browser, cpath) as ctx:
                page = ctx.new_page()
                logged = check_login_status(page)
                typer.echo(f"logged_in={logged}")


@app.command()
def get_qrcode(
    out: str = typer.Option("login.png", help="Output PNG path for QR image"),
    timeout: int = typer.Option(240, help="Total timeout seconds for this command"),
    poll_interval: float = typer.Option(0.5, help="Polling interval seconds"),
    reload_interval: float = typer.Option(10.0, help="Reload page interval seconds to recover"),
    verbose: bool = typer.Option(False, help="Verbose progress output"),
    profile: str | None = typer.Option(None, help="Profile name to select cookies file"),
    cookies_path: str | None = typer.Option(None, help="Explicit cookies storage_state file path"),
    bin: str | None = typer.Option(None, help="Chromium/Chrome executable path"),
):
    """Fetch QR code as PNG for headless login."""
    cpath = get_cookies_path(cookies_path, profile)
    chrome_bin = get_chrome_executable(bin)
    with pw() as p:
        with launch(p, chrome_bin=chrome_bin) as browser:
            with new_context(browser, cpath) as ctx:
                page = ctx.new_page()
                src, logged = fetch_qrcode_image(
                    page,
                    timeout_seconds=timeout,
                    poll_interval=poll_interval,
                    reload_interval=reload_interval,
                    verbose=verbose,
                )
                if logged:
                    typer.echo("Already logged in.")
                    return
                if not src:
                    raise typer.Exit(code=1)
                # src may be data:image/png;base64,...
                if src.startswith("data:image/"):
                    b64 = src.split(",", 1)[1]
                    data = base64.b64decode(b64)
                    Path(out).write_bytes(data)
                elif src.startswith("http://") or src.startswith("https://"):
                    if requests is None:
                        typer.echo("QR is URL but 'requests' not available. Install requests.")
                        raise typer.Exit(code=2)
                    resp = requests.get(src, timeout=15)
                    resp.raise_for_status()
                    Path(out).write_bytes(resp.content)
                else:
                    typer.echo("Unsupported QR src format.")
                    raise typer.Exit(code=2)
                typer.echo(f"QR saved to {out}")


@app.command()
def wait(
    timeout: int = typer.Option(240, help="Wait timeout seconds for login"),
    poll_interval: float = typer.Option(0.5, help="Polling interval seconds"),
    verbose: bool = typer.Option(False, help="Verbose progress output"),
    profile: str | None = typer.Option(None, help="Profile name to select cookies file"),
    cookies_path: str | None = typer.Option(None, help="Explicit cookies storage_state file path"),
    bin: str | None = typer.Option(None, help="Chromium/Chrome executable path"),
):
    """Wait for QR login completion and save cookies."""
    cpath = get_cookies_path(cookies_path, profile)
    chrome_bin = get_chrome_executable(bin)
    with pw() as p:
        with launch(p, chrome_bin=chrome_bin) as browser:
            with new_context(browser, cpath) as ctx:
                page = ctx.new_page()
                success = wait_for_login(page, timeout_seconds=timeout, poll_interval=poll_interval, verbose=verbose)
                if not success:
                    typer.echo("Login timed out")
                    raise typer.Exit(code=3)
                # Save storage_state to file
                try:
                    state = ctx.storage_state()
                except PWError:
                    typer.echo("Failed to get storage_state")
                    raise typer.Exit(code=4)
                save_storage_state(cpath, state)
                typer.echo(f"Login success. Cookies saved to {cpath}")


@app.command()
def login(
    out: str = typer.Option("login.png", help="Output PNG path for QR image"),
    timeout: int = typer.Option(240, help="Total timeout seconds (QR fetch + wait)"),
    poll_interval: float = typer.Option(0.5, help="Polling interval seconds"),
    reload_interval: float = typer.Option(10.0, help="Reload page interval seconds to recover"),
    verbose: bool = typer.Option(False, help="Verbose progress output"),
    profile: str | None = typer.Option(None, help="Profile name to select cookies file"),
    cookies_path: str | None = typer.Option(None, help="Explicit cookies storage_state file path"),
    bin: str | None = typer.Option(None, help="Chromium/Chrome executable path"),
):
    """Fetch QR code, wait for login, and save cookies in one shot."""
    # 获取 cookies 文件路径（优先旧路径 /tmp/cookies.json；然后 COOKIES_PATH；然后 profile；然后显式路径；最后默认 cookies.json）
    cpath = get_cookies_path(cookies_path, profile)
    # 获取浏览器可执行文件路径（优先命令行 --bin；然后 CHROME_BIN 环境变量；否则使用 Playwright 内置 Chromium）
    chrome_bin = get_chrome_executable(bin)

    typer.echo("准备启动浏览器.")

    # 启动 Playwright（上下文管理器，确保异常时也能退出）
    with pw() as p:

        typer.echo("初始化浏览器内核.")

        # 启动浏览器（无头、禁用常见自动化特征，可选指定执行文件以提升规避能力）
        with launch(p, chrome_bin=chrome_bin) as browser:

            typer.echo("启动浏览器.")

            # 新建上下文（若存在 cookies 文件，则以 storage_state 自动注入登录态）
            with new_context(browser, cpath) as ctx:

                typer.echo("浏览器打开页面.")

                # 新建页面对象
                page = ctx.new_page()
                # 统一总超时：从现在起直到 deadline 期间完成“取码 + 等待登录”
                import time as _time
                deadline = _time.time() + max(0, timeout)
                # 剩余时间用于取码
                remaining = max(0.0, deadline - _time.time())
                # 抓取二维码（若已登录则直接返回）
                src, logged = fetch_qrcode_image(
                    page,
                    timeout_seconds=int(remaining),
                    poll_interval=poll_interval,
                    reload_interval=reload_interval,
                    verbose=verbose,
                )
                # 已处于登录态，直接提示并返回
                if logged:
                    typer.echo("Already logged in.")
                    return
                # 没拿到二维码地址，打印错误并退出
                if not src:
                    typer.echo("Failed to fetch QR image src.")
                    raise typer.Exit(code=1)
                # 若是 data URL，则解码写入 PNG 文件
                if src.startswith("data:image/"):
                    b64 = src.split(",", 1)[1]
                    Path(out).write_bytes(base64.b64decode(b64))
                # 若是 http(s) URL，则下载图片写入文件
                elif src.startswith("http://") or src.startswith("https://"):
                    if requests is None:
                        typer.echo("QR is URL but 'requests' is not installed. Please install requests.")
                        raise typer.Exit(code=2)
                    resp = requests.get(src, timeout=15)
                    resp.raise_for_status()
                    Path(out).write_bytes(resp.content)
                # 其他格式不支持，提示错误
                else:
                    typer.echo("Unsupported QR src format.")
                    raise typer.Exit(code=2)
                # 输出二维码保存位置
                typer.echo(f"QR saved to {out}")

                # 用剩余时间等待登录完成，超时则退出
                remaining = max(0.0, deadline - _time.time())
                success = wait_for_login(page, deadline=_time.time() + remaining, poll_interval=poll_interval, verbose=verbose)
                if not success:
                    typer.echo("Login timed out")
                    raise typer.Exit(code=3)
                # 读取当前上下文的 storage_state（包含 cookies/localStorage 等）
                state = ctx.storage_state()
                # 保存到 cookies 文件，供下次启动自动载入
                save_storage_state(cpath, state)
                # 完成提示并输出 cookies 文件路径
                typer.echo(f"Login success. Cookies saved to {cpath}")


def main():
    try:
        app()
    except Exception as e:
        typer.echo(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
