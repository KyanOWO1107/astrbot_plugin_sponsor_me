# 项目交接

## 当前交付

- v0.1.0，功能、配置和安装说明见 `README.md`。
- 需求与任务状态见 `docs/plan.md`。黑白名单空值规则和主动赞助意图来自用户确认。
- 安装包位于 `dist/astrbot_plugin_sponsor_me-v0.1.0.zip`，不纳入 Git。只包含 `main.py`、`sponsor.py`、`_conf_schema.json`、`metadata.yaml` 和 `README.md`。
- 当前没有远程仓库配置。没有推送或部署。

## 接入约束

- AstrBot 4.9.2 中，注册表 `llm_tools` 是 `FunctionToolManager`，通过 `get_func()` 读取工具；请求中的 `ProviderRequest.func_tool` 是 `ToolSet`，使用 `get_tool()` 和 `remove_tool()`。不要混用两套接口。
- 禁用会话的工具过滤必须复制请求工具集，避免修改其他会话共享的对象。实际发送时仍需重新检查名单。
- AstrBot 的导入可能生成运行目录。测试必须在导入 SDK 前设置 `ASTRBOT_ROOT`。现有 SDK 测试隔离到 `.cache/sdk-tests`；根目录 `/data/` 也已加入 Git 忽略，避免误提交运行数据。
- 图片 URL 的 scheme 需要规范为小写。HTTP 标准允许大写 scheme，但 SDK 的图片构造方法按小写前缀判断。
- 发送返回正常只表示平台方法已返回。失败时可能已有部分内容发出，同一事件不能自动重试。

## 验证边界

2026-11-10：Python 3.12.10、真实 AstrBot 4.9.2 下 26 项测试通过；Python 3.10.11 下 13 项基础测试通过。Ruff、format、compileall、ZIP 完整性、解压后包内导入和真实 SDK 元数据、配置及工具注册检查通过。独立审查未发现阻塞问题。

平台发送使用测试替身。真实模型意图判断、运行中 AstrBot 完整安装与重载、QQ 等平台实际送达尚未运行。后续在测试会话中按 README 的验收说明检查，不能把 SDK 入口测试当作真实送达证据。
