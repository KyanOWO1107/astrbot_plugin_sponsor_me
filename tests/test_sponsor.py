import tempfile
import unittest
from pathlib import Path

from sponsor import load_content, session_enabled

SESSION = "qq_main:GroupMessage:123456"


class SessionPolicyTests(unittest.TestCase):
    def test_allow_and_deny_lists_follow_the_six_required_cases(self):
        cases = [
            ("whitelist", [], False),
            ("whitelist", [SESSION], True),
            ("whitelist", ["qq_other:GroupMessage:123456"], False),
            ("blacklist", [], True),
            ("blacklist", [SESSION], False),
            ("blacklist", ["qq_main:FriendMessage:123456"], True),
        ]
        for mode, sessions, expected in cases:
            with self.subTest(mode=mode, sessions=sessions):
                self.assertEqual(
                    session_enabled({"list_mode": mode, "sessions": sessions}, SESSION),
                    expected,
                )

    def test_initial_configuration_disables_every_session(self):
        self.assertFalse(session_enabled({}, SESSION))

    def test_invalid_policy_does_not_fall_back_to_allowing_everyone(self):
        for config in (
            {"list_mode": "unknown"},
            {"list_mode": "blacklist", "sessions": "123456"},
            {"list_mode": "blacklist", "sessions": [123456]},
            {"list_mode": "blacklist", "sessions": ["123456"]},
        ):
            with self.subTest(config=config), self.assertRaises(ValueError):
                session_enabled(config, SESSION)

    def test_blank_current_session_is_never_enabled(self):
        self.assertFalse(session_enabled({"list_mode": "blacklist"}, ""))


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.data = self.root / "plugin_data"
        self.data.mkdir()
        self.image = self.data / "pay.png"
        self.image.write_bytes(b"\x89PNG\r\n\x1a\n")

    def test_text_links_and_remote_images_preserve_configured_values(self):
        content = load_content(
            {
                "message": "谢谢支持",
                "links": ["https://example.com/support?a=1"],
                "images": ["https://example.com/pay.png"],
            },
            self.data,
        )
        self.assertEqual(content.message, "谢谢支持")
        self.assertEqual(content.links, ("https://example.com/support?a=1",))
        self.assertEqual(content.images, ("https://example.com/pay.png",))

    def test_image_only_and_link_only_configurations_are_supported(self):
        image_content = load_content({"images": ["pay.png"], "message": ""}, self.data)
        self.assertEqual(image_content.images, (str(self.image.resolve()),))
        link_content = load_content({"links": ["https://example.com"]}, self.data)
        self.assertEqual(link_content.links, ("https://example.com",))

    def test_absolute_image_paths_are_supported(self):
        content = load_content({"images": [str(self.image.resolve())]}, self.data)
        self.assertEqual(content.images, (str(self.image.resolve()),))

    def test_url_schemes_are_case_insensitive_and_normalized_for_the_sdk(self):
        content = load_content({"images": ["HTTPS://example.com/pay.png"]}, self.data)
        self.assertEqual(content.images, ("https://example.com/pay.png",))

    def test_message_alone_is_not_a_payment_destination(self):
        for config in ({}, {"message": "谢谢支持"}, {"images": ["  "], "links": [""]}):
            with (
                self.subTest(config=config),
                self.assertRaisesRegex(ValueError, "尚未配置"),
            ):
                load_content(config, self.data)

    def test_invalid_urls_are_rejected(self):
        for link in (
            "javascript:alert(1)",
            "file:///secrets.txt",
            "https:///no-host",
            "https://user:password@example.com",
            "https://example.com/a b",
            "https://example.com/\nnext",
            "https://example.com:bad",
            "https://[broken",
            "https://example.com:99999",
        ):
            with self.subTest(link=link), self.assertRaises(ValueError):
                load_content({"links": [link]}, self.data)

    def test_invalid_config_types_are_rejected(self):
        for config in (
            {"links": "https://example.com"},
            {"images": [None]},
            {"message": False, "links": ["https://example.com"]},
        ):
            with self.subTest(config=config), self.assertRaises(ValueError):
                load_content(config, self.data)

    def test_local_images_cannot_be_missing_directories_or_non_images(self):
        (self.data / "secret.txt").write_text("private", encoding="utf-8")
        (self.data / "directory.png").mkdir()
        for image in ("missing.png", "secret.txt", "directory.png", "file:///pay.png"):
            with self.subTest(image=image), self.assertRaises(ValueError):
                load_content({"images": [image]}, self.data)

    def test_relative_image_paths_cannot_escape_the_data_directory(self):
        (self.root / "outside.png").write_bytes(b"image")
        with self.assertRaises(ValueError):
            load_content({"images": ["../outside.png"]}, self.data)


if __name__ == "__main__":
    unittest.main()
