"""赞助配置和会话规则。此模块不依赖 AstrBot。"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_MESSAGE = "感谢你的支持，请按需选择赞助方式。"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def _strings(config: Mapping, key: str) -> tuple[str, ...]:
    values = config.get(key, [])
    if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
        raise ValueError(f"{key} 必须是字符串列表。")
    return tuple(v.strip() for v in values if v.strip())


def session_enabled(config: Mapping, session: str) -> bool:
    mode = config.get("list_mode", "whitelist")
    if mode not in ("whitelist", "blacklist"):
        raise ValueError("list_mode 必须是 whitelist 或 blacklist。")
    sessions = _strings(config, "sessions")
    if any(
        len(parts := value.split(":", 2)) != 3 or not all(parts) for value in sessions
    ):
        raise ValueError("sessions 必须填写完整会话标识，请用 /赞助状态 查询。")
    if not session:
        return False
    return (session in sessions) if mode == "whitelist" else (session not in sessions)


def _http_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value)
        ):
            raise ValueError
        _ = parsed.port
    except ValueError:
        raise ValueError(
            "链接或图片 URL 必须是有效的 HTTP(S) 地址，且不能包含凭据或空白。"
        ) from None
    return parsed.scheme + ":" + value.split(":", 1)[1]


@dataclass(frozen=True)
class SponsorContent:
    message: str
    links: tuple[str, ...]
    images: tuple[str, ...]


def load_content(config: Mapping, data_dir: Path) -> SponsorContent:
    message = config.get("message", DEFAULT_MESSAGE)
    if not isinstance(message, str):
        raise ValueError("message 必须是文本。")  # noqa: TRY004 - 配置校验统一使用 ValueError。
    links = tuple(_http_url(value) for value in _strings(config, "links"))
    images = []
    for value in _strings(config, "images"):
        if value.lower().startswith(("http:", "https:")):
            images.append(_http_url(value))
            continue
        try:
            path = Path(value)
            if not path.is_absolute():
                root = data_dir.resolve()
                path = (root / path).resolve()
                if not path.is_relative_to(root):
                    raise ValueError("收款码相对路径不能超出插件数据目录。")
            if path.suffix.lower() not in IMAGE_SUFFIXES or not path.is_file():
                raise ValueError(
                    "本地收款码必须是存在的 PNG、JPG、JPEG、GIF、WebP 或 BMP 文件。"
                )
            with path.open("rb"):
                pass
            images.append(str(path.resolve()))
        except OSError:
            raise ValueError("无法读取本地收款码，请检查路径和权限。") from None
    if not links and not images:
        raise ValueError("尚未配置收款码或赞助链接，请联系管理员。")
    return SponsorContent(message.strip(), links, tuple(images))
