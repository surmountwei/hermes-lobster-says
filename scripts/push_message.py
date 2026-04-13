#!/usr/bin/env python3
"""
虾说 for Hermes — 定时推送脚本。

从 nixiashuo.com 生成消息，输出格式化文本供 Hermes cron 投递。
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CONFIG_FILE = Path.home() / ".hermes" / "lobster-says" / ".lobster-config"


def _http(url: str, method: str = "GET", data: dict = None, token: str = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[✗] HTTP {e.code}: {body[:300]}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"[✗] 网络错误: {e.reason}", file=sys.stderr)
        sys.exit(1)


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        print("[✗] 配置不存在，请先初始化", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="虾说 — 推送消息")
    parser.add_argument("--slot", required=True,
                        choices=["morning", "evening", "discovery", "event", "sticker", "wallpaper"])
    parser.add_argument("--extra-context", default="")
    args = parser.parse_args()

    config = _load_config()
    api_base = config.get("api_base", "https://nixiashuo.com").rstrip("/")
    user_id = config["user_id"]
    token = config["access_token"]
    lobster_name = config.get("lobster_name", "虾")

    # ── 生成消息 ──
    payload = {
        "user_id": user_id,
        "message_type": args.slot,
        "include_screenshot_base64": False,
    }
    if args.extra_context:
        payload["extra_context"] = args.extra_context

    resp = _http(f"{api_base}/api/generate", method="POST", data=payload, token=token)

    # 处理跳过
    if resp.get("skipped"):
        reason = resp.get("reason", "unknown")
        print(f"[SILENT]本次 {args.slot} 生成被跳过: {reason}")
        return

    message = resp.get("message", {})
    content = message.get("raw_content") or message.get("content", "")
    web_url = resp.get("web_url", "")
    screenshot_url = resp.get("screenshot_url", "")
    message_id = message.get("id")

    if not content:
        print(f"[✗] 生成结果为空", file=sys.stderr)
        sys.exit(1)

    # ── 格式化输出 ──
    lines = [f"🦞 {lobster_name}说：「{content}」", ""]
    if screenshot_url:
        lines.append(f"📸 {lobster_name}的工作室截图：{screenshot_url}")
    if web_url:
        lines.append(f"👀 看看{lobster_name}在干嘛 → {web_url}")

    print("\n".join(lines))

    # ── 回写送达报告 ──
    if message_id and isinstance(message_id, int) and message_id > 0:
        try:
            _http(f"{api_base}/api/delivery/report", method="POST", data={
                "user_id": user_id,
                "message_id": message_id,
                "status": "sent",
                "channel": "hermes",
                "delivery_mode": "text_only",
                "delivered_text": "\n".join(lines),
                "delivered_screenshot_url": screenshot_url or None,
            }, token=token)
        except SystemExit:
            pass  # 送达报告失败不影响用户已收到的消息

    # ── 将推送内容注入虾的记忆，作为"虾说过的话" ──
    from datetime import datetime, timezone
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    slot_label = {"morning": "早安", "evening": "晚安", "discovery": "见闻",
                  "event": "事件", "sticker": "表情包", "wallpaper": "壁纸"}.get(args.slot, args.slot)
    memory_text = f"[{now_str}] {lobster_name}发送了{slot_label}推送：「{content}」"
    try:
        _http(f"{api_base}/api/memory/ingest", method="POST", data={
            "user_id": user_id,
            "memory_text": memory_text,
            "source": "hermes_cron_push",
        }, token=token)
    except SystemExit:
        pass  # memory ingest 失败不影响推送本身


if __name__ == "__main__":
    main()
