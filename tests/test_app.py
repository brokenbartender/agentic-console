import os
import tempfile
import unittest
from types import SimpleNamespace

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import app as app_mod


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def click(self):
        self.page.actions.append(("click", self.selector))

    def fill(self, text):
        self.page.actions.append(("fill", self.selector, text))


class FakeKeyboard:
    def __init__(self, page):
        self.page = page

    def press(self, key):
        self.page.actions.append(("press", key))


class FakePage:
    def __init__(self):
        self.actions = []
        self.keyboard = FakeKeyboard(self)

    def goto(self, url, wait_until=None):
        self.actions.append(("goto", url))

    def locator(self, selector):
        return FakeLocator(self, selector)

    def screenshot(self, path=None, full_page=None):
        self.actions.append(("screenshot", path))
        # write a small marker file to simulate output
        if path:
            with open(path, "wb") as handle:
                handle.write(b"PNG")


class FakeBrowser:
    def __init__(self):
        self.page = FakePage()

    def new_page(self):
        return self.page

    def close(self):
        return None


class FakeChromium:
    def __init__(self):
        self.browser = FakeBrowser()

    def launch(self, channel=None, headless=False):
        return self.browser


class FakePlaywright:
    def __init__(self):
        self.chromium = FakeChromium()

    def start(self):
        return self

    def stop(self):
        return None


class FakeInterpreter:
    def __init__(self):
        self.auto_run = False
        self.last_instruction = None
        self.offline = False
        self.llm = SimpleNamespace(model=None, api_base=None)

    def chat(self, instruction):
        self.last_instruction = instruction


class AgentAppShim(app_mod.AgentApp):
    def __init__(self):
        # bypass tkinter UI init
        pass


class AppCommandTests(unittest.TestCase):
    def setUp(self):
        self.app = AgentAppShim()
        self.app.playwright = None
        self.app.browser = None
        self.app.page = None
        self.app.chat_history = []
        self.logs = []
        self.app.log_line = lambda msg: self.logs.append(msg)

        # patch playwright and interpreter
        self._orig_pw = app_mod.sync_playwright
        self._orig_oi = app_mod.oi_interpreter
        app_mod.sync_playwright = FakePlaywright
        app_mod.oi_interpreter = FakeInterpreter()
        # stub agent chat
        self._orig_agent_chat = app_mod.AgentApp._agent_chat
        app_mod.AgentApp._agent_chat = lambda _self, _text: "hi"

        # patch os.startfile
        self._orig_startfile = getattr(os, "startfile", None)
        os.startfile = lambda path: self.logs.append(f"opened:{path}")

    def tearDown(self):
        app_mod.sync_playwright = self._orig_pw
        app_mod.oi_interpreter = self._orig_oi
        app_mod.AgentApp._agent_chat = self._orig_agent_chat
        if self._orig_startfile is not None:
            os.startfile = self._orig_startfile

    def test_browse_search_click_type_press(self):
        self.app._execute("browse example.com")
        self.app._execute("search openai")
        self.app._execute("click a.test")
        self.app._execute("type input.name | hello")
        self.app._execute("press Enter")

        page = self.app.page
        actions = page.actions
        self.assertIn(("goto", "https://example.com"), actions)
        self.assertIn(("goto", "https://www.google.com"), actions)
        self.assertIn(("click", "a.test"), actions)
        self.assertIn(("fill", "input.name", "hello"), actions)
        self.assertIn(("press", "Enter"), actions)

    def test_screenshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shot.png")
            self.app._execute(f"screenshot {path}")
            self.assertTrue(os.path.exists(path))

    def test_open(self):
        self.app._execute("open C:\\")
        self.assertTrue(any("opened:C:\\" in line for line in self.logs))

    def test_file_ops(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_file = os.path.join(tmp, "a.txt")
            dst_file = os.path.join(tmp, "b.txt")
            with open(src_file, "w", encoding="utf-8") as handle:
                handle.write("x")

            self.app._execute(f"copy {src_file} | {dst_file}")
            self.assertTrue(os.path.exists(dst_file))

            move_dst = os.path.join(tmp, "c.txt")
            self.app._execute(f"move {dst_file} | {move_dst}")
            self.assertTrue(os.path.exists(move_dst))

            folder = os.path.join(tmp, "dir")
            self.app._execute(f"mkdir {folder}")
            self.assertTrue(os.path.isdir(folder))

            self.app._execute(f"delete {move_dst}")
            self.assertFalse(os.path.exists(move_dst))

    def test_agent(self):
        os.environ["OLLAMA_MODEL"] = "dummy-model"
        try:
            self.app._execute("agent do a thing")
            # agent chat is stubbed in tests
            self.assertTrue(any("hi" in line for line in self.logs))
        finally:
            if "OLLAMA_MODEL" in os.environ:
                del os.environ["OLLAMA_MODEL"]

    def test_chat_fallback(self):
        self.app._execute("hello there")
        self.assertTrue(any("Agent task completed" in line or "hi" in line for line in self.logs))


if __name__ == "__main__":
    unittest.main()
