"""lab-dobby: Slack notifications for lab folks who run long jobs."""

from __future__ import annotations

import atexit
import contextlib
import datetime
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

_COLOR_SUCCESS = "#36a64f"
_COLOR_FAILURE = "#a30200"

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


def _post_json(payload: dict) -> None:
    """Send an arbitrary JSON payload to the webhook. Never raises."""
    global _warned_missing
    url = _get_webhook()
    if not url:
        if not _warned_missing:
            print(_MISSING_HELP, file=sys.stderr)
            _warned_missing = True
        return
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=_TIMEOUT)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[lab-dobby] 알림 전송 실패: {e}", file=sys.stderr)


def _fmt_dur(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}m{s}s"
    h, m = divmod(m, 60)
    return f"{h}h{m}m"


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _build_card(
    *,
    status: str,
    title: str,
    duration: str | None = None,
    tag: str | None = None,
    error_line: str | None = None,
) -> dict:
    """Build a Slack attachment+blocks payload for a status event."""
    icon = "✅" if status == "success" else "❌"
    color = _COLOR_SUCCESS if status == "success" else _COLOR_FAILURE

    fields = [{"type": "mrkdwn", "text": f"*Host:*\n{_HOST}"}]
    if duration is not None:
        fields.append({"type": "mrkdwn", "text": f"*Duration:*\n{duration}"})
    if tag:
        fields.append({"type": "mrkdwn", "text": f"*Tag:*\n{tag}"})

    blocks: list = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{icon} {title}", "emoji": True},
        },
        {"type": "section", "fields": fields},
    ]
    if error_line:
        line = error_line if len(error_line) < 1500 else error_line[:1500] + "..."
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": f"```\n{line}\n```"}}
        )
    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"lab-dobby · {_now_str()}"}],
        }
    )

    fallback = f"{icon} {title}"
    if duration:
        fallback += f" in {duration}"

    return {"text": fallback, "attachments": [{"color": color, "blocks": blocks}]}


def _post_status(
    status: str,
    title: str,
    duration: str | None,
    tag: str | None,
    error_line: str | None,
) -> None:
    _post_json(
        _build_card(
            status=status,
            title=title,
            duration=duration,
            tag=tag,
            error_line=error_line,
        )
    )


def notify(message: str, *, tag: str | None = None) -> None:
    """단발 메시지 (plain text). 카드 X."""
    prefix = f"[{_HOST}]"
    if tag:
        prefix += f"[{tag}]"
    text = f"{prefix} {message}"
    if len(text) > _MAX_LEN:
        text = text[:_MAX_LEN] + "...(truncated)"
    _post_json({"text": text})


def on_finish(_func=None, *, name: str | None = None, tag: str | None = None):
    """함수 데코레이터. 종료 시 ✅ 카드, 예외 시 ❌ 카드."""
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
                _post_status("failure", f"{label} failed", dur, tag, last)
                raise
            dur = _fmt_dur(time.monotonic() - t0)
            _post_status("success", f"{label} done", dur, tag, None)
            return result

        return wrapper

    if callable(_func):
        return deco(_func)
    return deco


@contextlib.contextmanager
def block(name: str = "block", *, tag: str | None = None):
    """with-블록. 종료 시 ✅ 카드, 예외 시 ❌ 카드."""
    t0 = time.monotonic()
    try:
        yield
    except Exception:
        dur = _fmt_dur(time.monotonic() - t0)
        last = traceback.format_exc().strip().splitlines()[-1]
        _post_status("failure", f"{name} failed", dur, tag, last)
        raise
    dur = _fmt_dur(time.monotonic() - t0)
    _post_status("success", f"{name} done", dur, tag, None)


_watching = False


def watch(name: str | None = None, *, tag: str | None = None) -> None:
    """스크립트 전체 감시. 종료(성공/예외) 시 카드. .py 스크립트 전용."""
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
            _post_status(
                "failure", f"{label} failed", dur, tag,
                f"{exc_type.__name__}: {exc}",
            )
        else:
            _post_status("success", f"{label} done", dur, tag, None)

    atexit.register(at_exit)


def _cli_main() -> None:
    msg = " ".join(sys.argv[1:]) or "lab-dobby test"
    notify(msg)


if __name__ == "__main__":
    _cli_main()
