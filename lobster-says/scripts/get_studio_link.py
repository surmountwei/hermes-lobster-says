#!/usr/bin/env python3
"""虾说 for Hermes — 获取工作室短时链接。"""

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CONFIG_FILE = Path.home() / ".hermes" / "lobster-says" / ".lobster-config"


def _http(url: str, token: str) -> dict:
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        print(f"[✗] HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"[✗] 网络错误: {e.reason}", file=sys.stderr)
        sys.exit(1)


def main():
    if not CONFIG_FILE.exists():
        print("[✗] 配置不存在，请先初始化", file=sys.stderr)
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    api_base = config.get("api_base", "https://nixiashuo.com").rstrip("/")
    user_id = config["user_id"]
    token = config["access_token"]
    name = config.get("lobster_name", "虾")

    data = _http(f"{api_base}/api/lobster/{user_id}/studio-link", token)
    web_url = data.get("web_url", "")

    if not web_url:
        print("[✗] 短链获取失败", file=sys.stderr)
        sys.exit(1)

    print(f"给你，{name}的工作室短链：")
    print()
    print(web_url)
    print()
    print("这是短时 st 入口，到期我可以再给你刷新。")


if __name__ == "__main__":
    main()
