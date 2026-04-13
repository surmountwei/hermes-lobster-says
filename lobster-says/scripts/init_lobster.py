#!/usr/bin/env python3
"""
虾说 for Hermes — 初始化脚本。

创建共情虾、保存配置、获取工作室短链。
与 nixiashuo.com 后端 REST API 通信，与 OpenClaw skill 共享同一个 server。
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ── 常量 ──
CONFIG_DIR = Path.home() / ".hermes" / "lobster-says"
CONFIG_FILE = CONFIG_DIR / ".lobster-config"
DEFAULT_API_BASE = "https://nixiashuo.com"


def _http_request(url: str, method: str = "GET", data: dict = None, token: str = None) -> dict:
    """发送 HTTP 请求到后端 API。"""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = Request(url, data=body, headers=headers, method=method)

    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"[✗] HTTP {e.code}: {error_body[:200]}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"[✗] 网络错误: {e.reason}", file=sys.stderr)
        sys.exit(1)


def _read_config() -> dict:
    """读取现有配置。"""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_config(config: dict):
    """写入配置文件。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="虾说 for Hermes — 初始化")
    parser.add_argument("--personality", default="warm",
                        choices=["warm", "sarcastic", "philosophical", "mouthpiece"])
    parser.add_argument("--memory-mode", default="smart",
                        choices=["lightweight", "smart", "deep"])
    parser.add_argument("--lobster-name", default="")
    parser.add_argument("--owner-nickname", default="打工人")
    parser.add_argument("--morning", default="09:00")
    parser.add_argument("--discovery", default="20:00")
    parser.add_argument("--evening", default="21:00")
    parser.add_argument("--platform", default="",
                        help="来源平台（telegram/discord/slack等），用于推送回原渠道")
    parser.add_argument("--chat-id", default="",
                        help="来源对话ID，用于推送回原渠道")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    existing = _read_config()

    # 来源平台信息由 SKILL.md 指示 Agent 通过 --platform/--chat-id 传入
    platform = args.platform or ""
    chat_id = args.chat_id or ""

    # ── 检查是否已有虾 ──
    if existing.get("user_id") and existing.get("access_token"):
        print(f"[!] 检测到已有配置，尝试复用...")
        try:
            status = _http_request(
                f"{api_base}/api/lobster/{existing['user_id']}/status",
                token=existing["access_token"],
            )
            if status.get("lobster_id"):
                lobster_name = status.get("name", "虾")
                nickname = status.get("nickname_for_user", args.owner_nickname)
                personality = status.get("personality", args.personality)
                print(f"[✓] 复用已有虾：{lobster_name}")

                # ── 同步修正 identity（与 OpenClaw 对齐）──
                identity_patch = {}
                if args.lobster_name and args.lobster_name != lobster_name:
                    identity_patch["lobster_name"] = args.lobster_name
                if args.owner_nickname != "打工人" and args.owner_nickname != nickname:
                    identity_patch["owner_nickname"] = args.owner_nickname
                if identity_patch:
                    try:
                        updated = _http_request(
                            f"{api_base}/api/lobster/{existing['user_id']}/identity",
                            method="PATCH",
                            data=identity_patch,
                            token=existing["access_token"],
                        )
                        lobster_name = updated.get("name", lobster_name)
                        nickname = updated.get("nickname_for_user", nickname)
                        print(f"[✓] 已同步修正身份：{lobster_name}，称呼={nickname}")
                    except SystemExit:
                        print("[!] identity 修正失败（不影响使用）")

                # 更新本地配置
                existing["lobster_name"] = lobster_name
                existing["nickname_for_user"] = nickname
                existing["morning_time"] = args.morning
                existing["discovery_time"] = args.discovery
                existing["evening_time"] = args.evening
                existing["memory_mode"] = args.memory_mode
                existing["api_base"] = api_base
                # 来源渠道：新传入的优先，否则保留旧的
                if platform:
                    existing["platform"] = platform
                if chat_id:
                    existing["chat_id"] = chat_id
                _write_config(existing)

                studio = _get_studio_link(api_base, existing["user_id"], existing["access_token"])

                _print_result(
                    success=True,
                    reused=True,
                    lobster_name=lobster_name,
                    personality=personality,
                    nickname=nickname,
                    user_id=existing["user_id"],
                    morning=args.morning,
                    discovery=args.discovery,
                    evening=args.evening,
                    memory_mode=args.memory_mode,
                    studio=studio,
                )
                return
        except SystemExit:
            print("[!] 已有虾验证失败，将重新创建")

    # ── 创建新虾 ──
    print("[…] 创建共情虾...")
    user_id = str(uuid.uuid4())
    create_payload = {
        "user_id": user_id,
        "personality": args.personality,
        "nickname_for_user": args.owner_nickname,
        "morning_time": args.morning,
        "evening_time": args.evening,
    }
    if args.lobster_name:
        create_payload["name"] = args.lobster_name

    resp = _http_request(f"{api_base}/api/lobster", method="POST", data=create_payload)

    access_token = resp["access_token"]
    lobster_name = resp["name"]
    actual_user_id = resp["user_id"]
    nickname = resp.get("nickname_for_user", args.owner_nickname)

    print(f"[✓] 虾创建成功：{lobster_name}")

    # ── 保存配置 ──
    config = {
        "user_id": actual_user_id,
        "access_token": access_token,
        "lobster_name": lobster_name,
        "lobster_personality": args.personality,
        "nickname_for_user": nickname,
        "api_base": api_base,
        "morning_time": args.morning,
        "discovery_time": args.discovery,
        "evening_time": args.evening,
        "memory_mode": args.memory_mode,
        "platform": platform,
        "chat_id": chat_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_config(config)
    print("[✓] 配置已保存")

    # ── 获取工作室链接 ──
    studio = _get_studio_link(api_base, actual_user_id, access_token)

    _print_result(
        success=True,
        reused=False,
        lobster_name=lobster_name,
        personality=args.personality,
        nickname=nickname,
        user_id=actual_user_id,
        morning=args.morning,
        discovery=args.discovery,
        evening=args.evening,
        memory_mode=args.memory_mode,
        studio=studio,
    )


def _get_studio_link(api_base: str, user_id: str, token: str) -> dict:
    """获取工作室短时链接。"""
    try:
        return _http_request(
            f"{api_base}/api/lobster/{user_id}/studio-link",
            token=token,
        )
    except SystemExit:
        print("[!] 工作室短链获取失败（不影响初始化）", file=sys.stderr)
        return {}


def _print_result(*, success, reused, lobster_name, personality, nickname,
                  user_id, morning, discovery, evening, memory_mode, studio):
    """输出初始化结果 JSON。"""
    result = {
        "success": success,
        "reused_existing": reused,
        "lobster_name": lobster_name,
        "personality": personality,
        "nickname_for_user": nickname,
        "user_id": user_id,
        "morning_time": morning,
        "discovery_time": discovery,
        "evening_time": evening,
        "memory_mode": memory_mode,
        "studio_web_url": studio.get("web_url", ""),
        "studio_screenshot_url": studio.get("screenshot_url", ""),
        "studio_link_expires_at": studio.get("expires_at", ""),
    }
    print("")
    print("INIT_RESULT_JSON:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
