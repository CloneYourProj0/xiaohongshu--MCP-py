import os
import tempfile
from pathlib import Path


DEFAULT_COOKIES_FILE = "cookies.json"
DEFAULT_PROFILES_DIR = Path("profiles")


def legacy_cookies_path_exists() -> bool:
    # Historically used /tmp/cookies.json
    legacy_dir = os.getenv("TMPDIR", tempfile.gettempdir())
    legacy = Path(os.path.join(legacy_dir, "cookies.json"))
    return legacy.exists()


def get_cookies_path(cookies_path: str | None = None, profile: str | None = None) -> Path:
    # Legacy: /tmp/cookies.json
    legacy = Path(os.path.join(os.getenv("TMPDIR", "/tmp"), "cookies.json"))
    if legacy.exists():
        return legacy

    # Env override
    env_path = os.getenv("COOKIES_PATH")
    if env_path:
        return Path(env_path)

    # profile-based
    if profile:
        pdir = DEFAULT_PROFILES_DIR / profile
        pdir.mkdir(parents=True, exist_ok=True)
        return pdir / DEFAULT_COOKIES_FILE

    # explicit path
    if cookies_path:
        return Path(cookies_path)

    # fallback
    return Path(DEFAULT_COOKIES_FILE)


def get_chrome_executable(bin_path: str | None) -> str | None:
    return bin_path or os.getenv("CHROME_BIN") or None
