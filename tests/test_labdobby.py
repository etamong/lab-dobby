"""Unit tests for labdobby. stdlib unittest only — no pytest dep."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

# Make labdobby importable when running tests from the repo root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import labdobby  # noqa: E402


class TestFmtDur(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(labdobby._fmt_dur(0.5), "0.5s")
        self.assertEqual(labdobby._fmt_dur(12.3), "12.3s")

    def test_minutes(self):
        self.assertEqual(labdobby._fmt_dur(60), "1m0s")
        self.assertEqual(labdobby._fmt_dur(75), "1m15s")
        self.assertEqual(labdobby._fmt_dur(3599), "59m59s")

    def test_hours(self):
        self.assertEqual(labdobby._fmt_dur(3600), "1h0m")
        self.assertEqual(labdobby._fmt_dur(3725), "1h2m")


class TestReadEnvFile(unittest.TestCase):
    def _write(self, content: str) -> str:
        f = tempfile.NamedTemporaryFile("w", delete=False, suffix=".env")
        f.write(content)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_simple(self):
        path = self._write("SLACK_WEBHOOK_URL=https://example.com/h\n")
        self.assertEqual(labdobby._read_env_file(path), "https://example.com/h")

    def test_with_quotes(self):
        path = self._write('SLACK_WEBHOOK_URL="https://example.com/h"\n')
        self.assertEqual(labdobby._read_env_file(path), "https://example.com/h")

    def test_with_comments_and_blank_lines(self):
        path = self._write("# comment\n\nSLACK_WEBHOOK_URL=https://x.io/h\n")
        self.assertEqual(labdobby._read_env_file(path), "https://x.io/h")

    def test_other_keys_only(self):
        path = self._write("OTHER_KEY=value\n")
        self.assertIsNone(labdobby._read_env_file(path))

    def test_missing_file(self):
        self.assertIsNone(labdobby._read_env_file("/nonexistent/path/.env"))


class TestGetWebhook(unittest.TestCase):
    def test_env_var_wins(self):
        with mock.patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://from/env"}):
            self.assertEqual(labdobby._get_webhook(), "https://from/env")

    def test_no_source(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(labdobby, "_ENV_FILE", "/nonexistent/.env"):
            self.assertIsNone(labdobby._get_webhook())


class TestBuildCard(unittest.TestCase):
    def test_success_card(self):
        card = labdobby._build_card(
            status="success", title="train done", duration="12m34s"
        )
        self.assertEqual(card["attachments"][0]["color"], labdobby._COLOR_SUCCESS)
        self.assertIn("✅", card["text"])
        self.assertIn("train done", card["text"])
        self.assertIn("12m34s", card["text"])

        blocks = card["attachments"][0]["blocks"]
        self.assertEqual(blocks[0]["type"], "header")
        self.assertIn("✅", blocks[0]["text"]["text"])

        fields = blocks[1]["fields"]
        self.assertEqual(len(fields), 2)  # Host + Duration

        self.assertEqual(blocks[-1]["type"], "context")
        self.assertEqual(len(blocks), 3)  # no error block

    def test_failure_card_with_error(self):
        card = labdobby._build_card(
            status="failure", title="train failed", duration="3m1s",
            tag="lr_sweep_v2", error_line="RuntimeError: OOM",
        )
        self.assertEqual(card["attachments"][0]["color"], labdobby._COLOR_FAILURE)
        blocks = card["attachments"][0]["blocks"]

        fields = blocks[1]["fields"]
        self.assertEqual(len(fields), 3)  # Host + Duration + Tag
        self.assertIn("Tag", json.dumps(fields))
        self.assertIn("lr_sweep_v2", json.dumps(fields))

        # Error code block
        self.assertEqual(blocks[2]["type"], "section")
        self.assertIn("```", blocks[2]["text"]["text"])
        self.assertIn("OOM", blocks[2]["text"]["text"])

    def test_card_omits_tag_when_none(self):
        card = labdobby._build_card(status="success", title="x", duration="1s")
        fields = card["attachments"][0]["blocks"][1]["fields"]
        self.assertNotIn("Tag:", json.dumps(fields))

    def test_card_omits_duration_when_none(self):
        card = labdobby._build_card(status="success", title="x")
        fields = card["attachments"][0]["blocks"][1]["fields"]
        joined = json.dumps(fields)
        self.assertNotIn("Duration:", joined)
        self.assertIn("Host:", joined)


class _FakeUrlopen:
    """Capture request bodies for inspection."""

    def __init__(self):
        self.calls: list = []

    def __call__(self, req, timeout=None):
        body = req.data.decode("utf-8")
        self.calls.append(json.loads(body))
        return mock.MagicMock()


class TestPostJson(unittest.TestCase):
    def setUp(self):
        labdobby._warned_missing = False

    def test_no_webhook_warns_once(self):
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(labdobby, "_ENV_FILE", "/nonexistent/.env"), \
             mock.patch.object(sys, "stderr", buf):
            labdobby._post_json({"text": "hi"})
            labdobby._post_json({"text": "hi again"})
        self.assertEqual(buf.getvalue().count("Webhook URL이 없어요"), 1)

    def test_post_with_webhook(self):
        fake = _FakeUrlopen()
        with mock.patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://x"}), \
             mock.patch("urllib.request.urlopen", fake):
            labdobby._post_json({"text": "hello"})
        self.assertEqual(fake.calls, [{"text": "hello"}])

    def test_post_handles_network_error(self):
        def raising(req, timeout=None):
            raise urllib.error.URLError("network down")
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://x"}), \
             mock.patch("urllib.request.urlopen", raising), \
             mock.patch.object(sys, "stderr", buf):
            labdobby._post_json({"text": "hi"})  # must not raise
        self.assertIn("알림 전송 실패", buf.getvalue())


class TestNotify(unittest.TestCase):
    def test_plain(self):
        fake = _FakeUrlopen()
        with mock.patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://x"}), \
             mock.patch("urllib.request.urlopen", fake):
            labdobby.notify("epoch 10")
        self.assertEqual(len(fake.calls), 1)
        text = fake.calls[0]["text"]
        self.assertIn("epoch 10", text)
        # has [hostname] prefix
        self.assertTrue(text.startswith("["))
        # plain notify must NOT use attachments/blocks
        self.assertNotIn("attachments", fake.calls[0])

    def test_with_tag(self):
        fake = _FakeUrlopen()
        with mock.patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://x"}), \
             mock.patch("urllib.request.urlopen", fake):
            labdobby.notify("hello", tag="exp1")
        self.assertIn("[exp1]", fake.calls[0]["text"])

    def test_long_message_truncated(self):
        fake = _FakeUrlopen()
        long_msg = "x" * 5000
        with mock.patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://x"}), \
             mock.patch("urllib.request.urlopen", fake):
            labdobby.notify(long_msg)
        self.assertIn("(truncated)", fake.calls[0]["text"])
        self.assertLess(len(fake.calls[0]["text"]), 5000)


class TestOnFinish(unittest.TestCase):
    def test_success_posts_success_card(self):
        fake = _FakeUrlopen()
        with mock.patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://x"}), \
             mock.patch("urllib.request.urlopen", fake):
            @labdobby.on_finish
            def my_func():
                return 42
            result = my_func()

        self.assertEqual(result, 42)
        self.assertEqual(len(fake.calls), 1)
        card = fake.calls[0]
        self.assertEqual(card["attachments"][0]["color"], labdobby._COLOR_SUCCESS)
        title = card["attachments"][0]["blocks"][0]["text"]["text"]
        self.assertIn("my_func done", title)

    def test_failure_posts_failure_card_and_reraises(self):
        fake = _FakeUrlopen()
        with mock.patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://x"}), \
             mock.patch("urllib.request.urlopen", fake):
            @labdobby.on_finish
            def boom():
                raise ValueError("test error")

            with self.assertRaises(ValueError):
                boom()

        self.assertEqual(len(fake.calls), 1)
        card = fake.calls[0]
        self.assertEqual(card["attachments"][0]["color"], labdobby._COLOR_FAILURE)
        # ValueError appears somewhere in the card
        self.assertIn("ValueError", json.dumps(card))

    def test_with_explicit_name_and_tag(self):
        fake = _FakeUrlopen()
        with mock.patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://x"}), \
             mock.patch("urllib.request.urlopen", fake):
            @labdobby.on_finish(name="custom", tag="exp1")
            def f():
                pass
            f()

        card = fake.calls[0]
        title = card["attachments"][0]["blocks"][0]["text"]["text"]
        self.assertIn("custom done", title)
        fields_str = json.dumps(card["attachments"][0]["blocks"][1]["fields"])
        self.assertIn("exp1", fields_str)


class TestBlock(unittest.TestCase):
    def test_success(self):
        fake = _FakeUrlopen()
        with mock.patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://x"}), \
             mock.patch("urllib.request.urlopen", fake):
            with labdobby.block("preprocess"):
                pass

        card = fake.calls[0]
        self.assertEqual(card["attachments"][0]["color"], labdobby._COLOR_SUCCESS)
        title = card["attachments"][0]["blocks"][0]["text"]["text"]
        self.assertIn("preprocess done", title)

    def test_failure_reraises(self):
        fake = _FakeUrlopen()
        with mock.patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://x"}), \
             mock.patch("urllib.request.urlopen", fake):
            with self.assertRaises(RuntimeError):
                with labdobby.block("step"):
                    raise RuntimeError("oops")

        card = fake.calls[0]
        self.assertEqual(card["attachments"][0]["color"], labdobby._COLOR_FAILURE)
        self.assertIn("RuntimeError", json.dumps(card))


if __name__ == "__main__":
    unittest.main()
