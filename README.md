# 赞助我

AstrBot 赞助信息插件。用户可以通过指令，或在对话中主动索取赞助方式，获取管理员设置的收款码和赞助链接。

需要 AstrBot 4.9.2 或更新版本。插件没有额外运行依赖。

## 安装与首次配置

1. 将插件目录放到 AstrBot 的 `data/plugins/astrbot_plugin_sponsor_me`，或在插件管理页面上传插件 ZIP。
2. 在 WebUI 插件设置中填写 `images` 或 `links`，至少填写其中一种。可以同时填写，也可以填写多个。
3. 默认是白名单模式，空名单下所有会话均不启用。机器人管理员在目标群聊或私聊执行 `/赞助状态`，复制返回的完整会话标识到 `sessions`。
4. 保存配置，按 AstrBot 提示重载插件。在已启用的会话发送 `/赞助`。

也可以切换为黑名单模式。黑名单为空时，所有会话均启用。

## 指令与对话

| 入口 | 行为 |
| --- | --- |
| `/赞助` | 发送配置的文案、全部赞助链接及全部收款码 |
| `/sponsor`、`/打赏` | 与 `/赞助` 相同 |
| `/赞助状态` | 仅机器人管理员可用，显示当前会话标识、启用状态及配置检查结果 |
| 对话中主动索取赞助方式 | 模型调用 `send_sponsor_info` 后，插件发送赞助信息 |

指令前缀和唤醒方式遵循 AstrBot 配置。群聊中通常需要 @机器人或使用已配置的唤醒前缀。

对话示例：“怎么赞助你？”“给我你的收款码。”“想请你喝咖啡，链接在哪？”

工具描述要求模型仅在用户主动索取当前机器人的赞助方式时调用。拒绝赞助、讨论赞助话题、引用他人话语或索取第三方收款信息，不应调用。

对话触发需要 AstrBot 已启用 LLM，对话使用的模型支持工具调用，并且当前人格允许使用 `send_sponsor_info`。插件不额外请求模型，也不监听所有消息进行关键词匹配。最终意图判断由所用模型决定，仍可能误判或漏判；指令入口不依赖 LLM。

## 会话名单

| `list_mode` | 名单内 | 名单外 | 空名单 |
| --- | --- | --- | --- |
| `whitelist` | 启用 | 不启用 | 全部不启用 |
| `blacklist` | 不启用 | 启用 | 全部启用 |

名单填写 AstrBot 的完整 `unified_msg_origin`，格式为 `平台实例ID:消息类型:会话ID`，不要只填写群号或用户号。请复制 `/赞助状态` 的实际输出，不要照抄示例。

赞助指令和 LLM tool 共用名单检查。未启用的会话不会收到赞助信息；插件会从该次 LLM 请求中移除赞助工具，工具执行时也会再次检查名单。管理员诊断指令 `/赞助状态` 不受名单限制，方便首次配置；它不会显示收款链接或本地文件路径。

## 配置

以下内容仅为格式示例，示例地址不是真实收款目标：

```json
{
  "list_mode": "whitelist",
  "sessions": ["qq_main:GroupMessage:123456"],
  "message": "谢谢支持，可以通过以下方式赞助：",
  "images": ["wechat.png", "https://example.com/alipay.png"],
  "links": ["https://example.com/support"]
}
```

- `message`：发送在收款码和链接前的文案，可以留空。只配置文案不能发送赞助信息。
- `images`：图片地址或本地路径，每项一张。支持 PNG、JPG、JPEG、GIF、WebP、BMP 本地文件。
- `links`：HTTP(S) 赞助页面或收款页面地址，每项一个。

本地相对路径以 `data/plugin_data/astrbot_plugin_sponsor_me/` 为根。例如 `wechat.png` 对应该目录下的同名文件。相对路径不能使用 `..` 越界。也可填写绝对路径；Docker 中应填写容器内路径，且 AstrBot 进程必须能读取该文件。

HTTP(S) 图片由 AstrBot 和平台适配器按需处理。插件只检查 URL 格式，不预先下载或检查远程图片是否可访问。图片 URL、赞助链接不能含账号密码、空白或控制字符。

配置无效或本地图片不存在时，该次请求不会发送赞助内容。机器人管理员可以使用 `/赞助状态` 查看原因。请在配置页面修改收款目标；聊天消息和工具参数不能修改目标。

## 发送行为

每次请求发送一个包含文本与图片的消息链。适配器可能将它拆成多条消息。是否支持图文混排、外部图片和可点击链接，由具体平台决定。

同一条用户消息中的重复或并发工具调用只尝试发送一次。新的用户消息可以再次请求。插件不保存跨消息的冷却记录或用户数据。

发送异常后不自动重试。平台抛出错误时，可能已有部分内容发出；插件会提示发送失败，避免自动重试造成重复消息。工具返回“已提交”仅表示平台发送方法正常返回，不代表对端已经收到、已读或完成支付。

## 验证

基础规则测试只需要 Python 标准库：

```powershell
python -m unittest discover -s tests -p test_sponsor.py -v
```

真实 SDK 接入测试需要安装 AstrBot。它使用真实配置类、工具注册和消息组件，只替换平台发送方法，不连接聊天平台或 LLM：

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe astrbot==4.9.2 ruff
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m compileall -q main.py sponsor.py tests
.venv/Scripts/python.exe -m ruff check main.py sponsor.py tests
```

SDK 测试使用项目内 `.cache/sdk-tests` 作为 `ASTRBOT_ROOT`，不会加载真实 AstrBot 配置。未安装 SDK 时，接入测试显示 `skipped`，不能视为通过。

真实环境验收：先在白名单会话测试 `/赞助`，再测试主动意图和拒绝赞助两类对话，检查实际消息是否送达。切换黑白名单并测试空名单，最后检查群聊和私聊。真实模型意图识别及平台送达不能由离线测试代替。
