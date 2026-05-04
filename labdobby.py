"""lab-dobby: Slack notifications for lab folks who run long jobs."""

from __future__ import annotations

import atexit
import contextlib
import functools
import json
import os
import socket
import sys
import time
import traceback
import urllib.error
import urllib.request

_WEBHOOK_ENV = "SLACK_WEBHOOK_URL"
_ENV_FILE = "~/.labdobby.env"
_MAX_LEN = 3500
_TIMEOUT = 5

_MISSING_HELP = (
    "[lab-dobby] ⚠️  Webhook URL이 없어요.\n"
    "  - Colab: 좌측 🔑 Secrets에 SLACK_WEBHOOK_URL 추가 (노트북 액세스 ON)\n"
    "  - 서버: ~/.labdobby.env 파일에 SLACK_WEBHOOK_URL=... 추가 후 chmod 600\n"
    "  - 자세히: https://github.com/etamong/lab-dobby#설정\n"
    "  알림은 일단 꺼두고 코드는 계속 돌아갈게요."
)


def _is_colab() -> bool:
    try:
        import google.colab  # noqa: F401
        return True
    except ImportError:
        return False


def _hostname() -> str:
    if _is_colab():
        return "colab"
    try:
        return socket.gethostname()
    except OSError:
        return "?"


_HOST = _hostname()


def _read_env_file(path: str) -> str | None:
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                k, _, v = line.partition("=")
                if k.strip() == _WEBHOOK_ENV:
                    return v.strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def _get_webhook() -> str | None:
    url = os.environ.get(_WEBHOOK_ENV)
    if url:
        return url
    if _is_colab():
        try:
            from google.colab import userdata
            url = userdata.get(_WEBHOOK_ENV)
            if url:
                return url
        except Exception:
            pass
    path = os.path.expanduser(_ENV_FILE)
    if os.path.isfile(path):
        return _read_env_file(path)
    return None


_warned_missing = False


def _post(text: str) -> None:
    global _warned_missing
    url = _get_webhook()
    if not url:
        if not _warned_missing:
            print(_MISSING_HELP, file=sys.stderr)
            _warned_missing = True
        return
    if len(text) > _MAX_LEN:
        text = text[:_MAX_LEN] + "...(truncated)"
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=_TIMEOUT)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[lab-dobby] 알림 전송 실패: {e}", file=sys.stderr)


def _fmt_dur(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{int(m)}m{int(s)}s"
    h, m = divmod(m, 60)
    return f"{int(h)}h{int(m)}m"


def notify(message: str, *, tag: str | None = None) -> None:
    """단발 메시지 보내기."""
    prefix = f"[{_HOST}]"
    if tag:
        prefix += f"[{tag}]"
    _post(f"{prefix} {message}")


def on_finish(_func=None, *, name: str | None = None, tag: str | None = None):
    """함수 데코레이터. 종료 시 ✅, 예외 시 ❌ 자동 알림."""
    def deco(func):
        label = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            t0 = time.monotonic()
            try:
                result = func(*args, **kwargs)
            except Exception:
                dur = _fmt_dur(time.monotonic() - t0)
                last = traceback.format_exc().strip().splitlines()[-1]
                notify(f"❌ {label} failed in {dur}\n{last}", tag=tag)
                raise
            dur = _fmt_dur(time.monotonic() - t0)
            notify(f"✅ {label} done in {dur}", tag=tag)
            return result

        return wrapper

    if callable(_func):
        return deco(_func)
    return deco


@contextlib.contextmanager
def block(name: str = "block", *, tag: str | None = None):
    """with-블록 데코레이터. 종료 시 ✅, 예외 시 ❌ 자동 알림."""
    t0 = time.monotonic()
    try:
        yield
    except Exception:
        dur = _fmt_dur(time.monotonic() - t0)
        last = traceback.format_exc().strip().splitlines()[-1]
        notify(f"❌ {name} failed in {dur}\n{last}", tag=tag)
        raise
    dur = _fmt_dur(time.monotonic() - t0)
    notify(f"✅ {name} done in {dur}", tag=tag)


_watching = False


def watch(name: str | None = None, *, tag: str | None = None) -> None:
    """스크립트 전체 감시. 종료(성공/예외) 시 자동 알림. .py 스크립트 전용."""
    global _watching
    if _watching:
        return
    _watching = True
    label = name or os.path.basename(sys.argv[0]) or "script"
    t0 = time.monotonic()
    state: dict = {"err": None}

    prev_hook = sys.excepthook

    def excepthook(exc_type, exc, tb):
        state["err"] = (exc_type, exc)
        prev_hook(exc_type, exc, tb)

    sys.excepthook = excepthook

    def at_exit():
        dur = _fmt_dur(time.monotonic() - t0)
        if state["err"] is not None:
            exc_type, exc = state["err"]
            notify(f"❌ {label} failed in {dur}\n{exc_type.__name__}: {exc}", tag=tag)
        else:
            notify(f"✅ {label} done in {dur}", tag=tag)

    atexit.register(at_exit)


def _cli_main() -> None:
    msg = " ".join(sys.argv[1:]) or "lab-dobby test"
    notify(msg)


if __name__ == "__main__":
    _cli_main()
