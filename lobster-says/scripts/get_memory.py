#!/usr/bin/env python3
"""虾说 for Hermes — 查看虾的记忆。"""

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CONFIG_FILE = Path.home() / ".hermes" / "lobster-says" / ".lobster-config"


def _http(url: str, token: str) -> dict:
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        print(f"[✗] HTTP {e.code}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"[✗] 网络错误: {e.reason}", file=sys.stderr)
        sys.exit(1)


def main():
    if not CONFIG_FILE.exists():
        print("[✗] 配置不存在", file=sys.stderr)
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    api_base = config.get("api_base", "https://nixiashuo.com").rstrip("/")
    data = _http(f"{api_base}/api/lobster/{config['user_id']}/memory", config["access_token"])

    summary = data.get("memory_summary", "暂时还不太了解，正在慢慢认识中。")
    print(f"🧠 {config.get('lobster_name', '虾')}的记忆：")
    print()
    print(summary)


if __name__ == "__main__":
    main()
