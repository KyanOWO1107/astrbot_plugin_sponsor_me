"""使用真实 AstrBot SDK；仅替换最终平台发送边界，不连接模型或聊天平台。"""

import asyncio
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

if importlib.util.find_spec("astrbot") is None:
    raise unittest.SkipTest(
        "需要真实 AstrBot SDK；使用 .venv 中的 Python 运行接入测试。"
    )

ROOT = Path(__file__).resolve().parents[1]
os.environ["ASTRBOT_ROOT"] = str(ROOT / ".cache" / "sdk-tests")

from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import Image, Plain
from astrbot.core.agent.tool import ToolSet
from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_type import MessageType
from astrbot.core.platform.platform_metadata import PlatformMetadata
from astrbot.core.provider.entities import ProviderRequest
from astrbot.core.provider.register import llm_tools

from main import SponsorMePlugin


class RecordingEvent(AstrMessageEvent):
    def __init__(self, *, admin=False, fail=False, private=False):
        message = AstrBotMessage()
        message.type = (
            MessageType.FRIEND_MESSAGE if private else MessageType.GROUP_MESSAGE
        )
        message.sender = MessageMember("user", "Tester")
        message.self_id = "bot"
        message.message_id = "message-1"
        message.message = [Plain("怎么赞助你")]
        message.message_str = "怎么赞助你"
        super().__init__(
            message.message_str,
            message,
            PlatformMetadata("aiocqhttp", "Test", "qq_main"),
            "123456",
        )
        self.role = "admin" if admin else "member"
        self.sent = []
        self.fail = fail

    async def send(self, message):
        await asyncio.sleep(0)
        if self.fail:
            raise RuntimeError("a simulated platform failure")
        self.sent.append(message)


class PluginTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = {
            "list_mode": "blacklist",
            "sessions": [],
            "message": "谢谢支持",
            "links": ["https://example.com/support"],
            "images": [],
        }
        self.plugin = SponsorMePlugin(None, self.config)

    async def command(self, event):
        return [result async for result in self.plugin.sponsor(event)]

    def text(self, chain):
        return "\n".join(part.text for part in chain.chain if isinstance(part, Plain))

    async def test_command_and_tool_send_the_same_configured_content(self):
        command_event, tool_event = RecordingEvent(), RecordingEvent()
        self.assertEqual(await self.command(command_event), [])
        feedback = await self.plugin.send_sponsor_info(tool_event)
        self.assertEqual(len(command_event.sent), 1)
        self.assertEqual(len(tool_event.sent), 1)
        self.assertEqual(
            self.text(command_event.sent[0]), "谢谢支持\nhttps://example.com/support"
        )
        self.assertEqual(
            self.text(command_event.sent[0]), self.text(tool_event.sent[0])
        )
        self.assertIn("已提交", feedback)
        self.assertTrue(command_event.is_stopped())

    async def test_both_entry_points_obey_the_session_policy(self):
        for mode, sessions in (
            ("whitelist", []),
            ("blacklist", [RecordingEvent().unified_msg_origin]),
        ):
            self.config.update(list_mode=mode, sessions=sessions)
            with self.subTest(mode=mode):
                command_event, tool_event = RecordingEvent(), RecordingEvent()
                self.assertEqual(await self.command(command_event), [])
                feedback = await self.plugin.send_sponsor_info(tool_event)
                self.assertEqual(command_event.sent + tool_event.sent, [])
                self.assertIn("未启用", feedback)
                self.assertNotIn("https://", feedback)

    async def test_private_chats_are_supported_without_group_assumptions(self):
        event = RecordingEvent(private=True)
        self.config.update(list_mode="whitelist", sessions=[event.unified_msg_origin])
        await self.command(event)
        self.assertEqual(len(event.sent), 1)

    async def test_remote_and_local_images_use_real_sdk_components(self):
        image = Path(self.directory.name) / "payment.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\n")
        self.config["images"] = ["https://example.com/pay.png", str(image)]
        event = RecordingEvent()
        await self.command(event)
        images = [part for part in event.sent[0].chain if isinstance(part, Image)]
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0].file, "https://example.com/pay.png")
        self.assertTrue(images[1].file.startswith("file:///"))

    async def test_duplicate_and_concurrent_tool_calls_send_only_once(self):
        event = RecordingEvent()
        await asyncio.gather(*(self.plugin.send_sponsor_info(event) for _ in range(3)))
        await self.command(event)
        self.assertEqual(len(event.sent), 1)

    async def test_new_requests_can_send_again(self):
        first, second = RecordingEvent(), RecordingEvent()
        await self.plugin.send_sponsor_info(first)
        await self.plugin.send_sponsor_info(second)
        self.assertEqual(len(first.sent) + len(second.sent), 2)

    async def test_unconfigured_or_invalid_content_never_sends_payment_information(
        self,
    ):
        for changes in (
            {"links": []},
            {"links": ["javascript:bad"]},
            {"images": ["missing.png"]},
        ):
            config = self.config | changes
            plugin = SponsorMePlugin(None, config)
            event = RecordingEvent()
            with self.subTest(changes=changes):
                feedback = await plugin.send_sponsor_info(event)
                self.assertFalse(event.sent)
                self.assertIn("配置", feedback)

    async def test_send_failure_is_reported_without_automatic_retry(self):
        event = RecordingEvent(fail=True)
        first = await self.plugin.send_sponsor_info(event)
        second = await self.plugin.send_sponsor_info(event)
        self.assertIn("失败", first)
        self.assertNotIn("已提交", first)
        self.assertIn("重复", second)
        self.assertFalse(event.sent)

    async def test_policy_changes_apply_to_the_next_request(self):
        first, second = RecordingEvent(), RecordingEvent()
        await self.command(first)
        self.config.update(list_mode="whitelist", sessions=[])
        await self.command(second)
        self.assertEqual(len(first.sent), 1)
        self.assertFalse(second.sent)

    async def test_disallowed_sessions_do_not_receive_the_tool_in_llm_requests(self):
        tool = llm_tools.get_func("send_sponsor_info")
        self.assertIsNotNone(tool, "真实 SDK 必须成功注册工具")
        self.assertEqual(tool.parameters.get("properties"), {})
        shared = ToolSet(tools=[tool])
        request = ProviderRequest(func_tool=shared)
        self.config["list_mode"] = "whitelist"
        await self.plugin.filter_sponsor_tool(RecordingEvent(), request)
        self.assertIsNone(request.func_tool.get_tool("send_sponsor_info"))
        self.assertIsNotNone(
            shared.get_tool("send_sponsor_info"), "不能修改其他会话共享的工具集"
        )

    async def test_enabled_session_keeps_the_tool(self):
        request = ProviderRequest(
            func_tool=ToolSet(tools=[llm_tools.get_func("send_sponsor_info")])
        )
        await self.plugin.filter_sponsor_tool(RecordingEvent(), request)
        self.assertIsNotNone(request.func_tool.get_tool("send_sponsor_info"))

    async def test_status_is_admin_only_and_works_before_whitelisting(self):
        self.config.update(list_mode="whitelist", sessions=[])
        member = RecordingEvent()
        self.assertEqual([r async for r in self.plugin.sponsor_status(member)], [])
        admin = RecordingEvent(admin=True)
        results = [r async for r in self.plugin.sponsor_status(admin)]
        self.assertEqual(len(results), 1)
        text = self.text(results[0])
        self.assertIn(admin.unified_msg_origin, text)
        self.assertIn("未启用", text)
        self.assertNotIn("https://example.com", text)

    async def test_schema_defaults_disable_the_plugin_and_use_real_astrbot_config(self):
        from astrbot.api import AstrBotConfig

        schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
        config = AstrBotConfig(
            str(Path(self.directory.name) / "plugin.json"), schema=schema
        )
        plugin = SponsorMePlugin(None, config)
        event = RecordingEvent()
        self.assertEqual(config["list_mode"], "whitelist")
        self.assertEqual(config["sessions"], [])
        self.assertIn("未启用", await plugin.send_sponsor_info(event))
        self.assertFalse(event.sent)


if __name__ == "__main__":
    unittest.main()
