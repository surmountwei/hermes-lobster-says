#!/usr/bin/env python3
"""虾说 for Hermes — 手动触发生成一条消息。"""

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
        print(f"[✗] HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"[✗] 网络错误: {e.reason}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="event",
                        choices=["morning", "evening", "event", "discovery", "sticker", "wallpaper"])
    parser.add_argument("--extra-context", default="")
    args = parser.parse_args()

    if not CONFIG_FILE.exists():
        print("[✗] 配置不存在", file=sys.stderr)
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    api_base = config.get("api_base", "https://nixiashuo.com").rstrip("/")
    name = config.get("lobster_name", "虾")

    payload = {
        "user_id": config["user_id"],
        "message_type": args.type,
        "include_screenshot_base64": False,
    }
    if args.extra_context:
        payload["extra_context"] = args.extra_context

    resp = _http(f"{api_base}/api/generate", method="POST", data=payload, token=config["access_token"])

    if resp.get("skipped"):
        print(f"本次生成被跳过: {resp.get('reason', 'unknown')}")
        return

    msg = resp.get("message", {})
    content = msg.get("raw_content") or msg.get("content", "")
    print(f"🦞 {name}说：「{content}」")

    web_url = resp.get("web_url", "")
    if web_url:
        print(f"👀 工作室 → {web_url}")


if __name__ == "__main__":
    main()
