import contextlib
import functools
import http.server
import shutil
import socket
import tempfile
import threading
import unittest
from pathlib import Path

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - 环境缺少浏览器测试依赖时由 unittest 跳过
    sync_playwright = None
    PlaywrightError = Exception
    PlaywrightTimeoutError = Exception


ROOT_DIR = Path(__file__).resolve().parents[1]


def _find_free_port():
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass


@unittest.skipIf(sync_playwright is None, "playwright is not installed")
class FrontendSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.site_dir = Path(cls.temp_dir.name)

        shutil.copy2(ROOT_DIR / "index.html", cls.site_dir / "index.html")
        shutil.copy2(ROOT_DIR / "favicon.svg", cls.site_dir / "favicon.svg")
        shutil.copytree(ROOT_DIR / "assets", cls.site_dir / "assets")
        (cls.site_dir / "files.json").write_text(
            """[
  "illustration/000AinSophAur.Yumeji.png",
  "music/000AinSophAur.mp3",
  "chart/000AinSophAur/HD.json",
  "info/illustration.txt",
  "info/version.txt",
  "avatar/player.png"
]""",
            encoding="utf-8",
        )
        (cls.site_dir / "version.txt").write_text("3.18.3 (141)\n", encoding="utf-8")

        cls.port = _find_free_port()
        handler = functools.partial(QuietHandler, directory=str(cls.site_dir))
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", cls.port), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch()
        except PlaywrightError as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"chromium browser is not available: {exc}") from exc

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
        if hasattr(cls, "playwright"):
            cls.playwright.stop()
        if hasattr(cls, "server"):
            cls.server.shutdown()
            cls.server.server_close()
        if hasattr(cls, "thread"):
            cls.thread.join(timeout=5)
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)

    def _goto_home(self):
        self.page.goto(f"http://127.0.0.1:{self.port}/", wait_until="networkidle")
        self.page.get_by_text("OPERATIONAL").wait_for(timeout=5000)

    def test_search_results_have_type_badges_and_keyboard_selection(self):
        self._goto_home()

        search = self.page.get_by_label("Search resources")
        self.assertFalse(search.is_disabled())
        self.assertEqual("3.18.3 (141)", self.page.locator("#version-text").inner_text())

        search.fill("illustration")
        first_result = self.page.locator("#search-results a.result-item").first
        first_result.wait_for(timeout=5000)

        self.assertEqual("true", search.get_attribute("aria-expanded"))
        self.assertEqual("ILL", first_result.locator(".result-type").inner_text())
        self.assertIn("illustration/000AinSophAur.Yumeji.png", first_result.inner_text())

        search.press("ArrowDown")
        self.assertEqual("result-0", search.get_attribute("aria-activedescendant"))
        self.assertEqual("true", first_result.get_attribute("aria-selected"))

    def test_quick_actions_and_empty_state(self):
        self._goto_home()

        search = self.page.get_by_label("Search resources")
        search.focus()
        self.page.get_by_role("option", name="音频").click()
        self.page.locator("#search-results a.result-item").first.wait_for(timeout=5000)
        self.assertEqual("music", search.input_value())

        search.fill("no-such-resource")
        self.page.get_by_text("No echoes found.").wait_for(timeout=5000)
        self.assertEqual("true", search.get_attribute("aria-expanded"))


if __name__ == "__main__":
    unittest.main()
