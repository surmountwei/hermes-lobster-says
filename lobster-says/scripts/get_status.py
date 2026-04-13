#!/usr/bin/env python3
"""虾说 for Hermes — 查询虾的状态。"""

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CONFIG_FILE = Path.home() / ".hermes" / "lobster-says" / ".lobster-config"

STATUS_LABELS = {
    "idle": "待命", "working": "忙活", "sleeping": "睡着",
    "daydreaming": "发呆", "slacking": "摸鱼", "running": "乱窜",
    "crazy": "发疯", "excited": "兴奋",
}


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
        print("[✗] 配置不存在，请先初始化", file=sys.stderr)
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    api_base = config.get("api_base", "https://nixiashuo.com").rstrip("/")
    data = _http(f"{api_base}/api/lobster/{config['user_id']}/status", config["access_token"])

    name = data.get("name", "虾")
    status = data.get("status", "idle")
    label = STATUS_LABELS.get(status, status)
    reason = data.get("status_reason", "")
    latest = data.get("latest_message", "")

    print(f"{name}现在在{label}。")
    if reason:
        print(f"• 状态说明：{reason}")
    if latest:
        print(f"• 最新一句：{latest}")


if __name__ == "__main__":
    main()
