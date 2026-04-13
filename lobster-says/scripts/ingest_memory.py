#!/usr/bin/env python3
"""
虾说 for Hermes — 记忆注入脚本。

将用户在聊天中提到的信息注入到虾的记忆系统。
对应 OpenClaw skill 的 /api/memory/ingest 调用。
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CONFIG_FILE = Path.home() / ".hermes" / "lobster-says" / ".lobster-config"


def _http(url: str, method: str = "GET", data: dict = None, token: str = None) -> tuple:
    """返回 (response_dict, error_string)。成功时 error 为空。"""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8")), ""
    except HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:300]
        return {}, f"HTTP {e.code}: {err}"
    except URLError as e:
        return {}, f"网络错误: {e.reason}"


def main():
    parser = argparse.ArgumentParser(description="虾说 — 记忆注入")
    parser.add_argument("--text", required=True, help="要注入的记忆文本")
    parser.add_argument("--source", default="hermes_chat", help="记忆来源标识")
    args = parser.parse_args()

    if not CONFIG_FILE.exists():
        print("[✗] 配置不存在，请先初始化", file=sys.stderr)
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    api_base = config.get("api_base", "https://nixiashuo.com").rstrip("/")

    resp, err = _http(
        f"{api_base}/api/memory/ingest",
        method="POST",
        data={
            "user_id": config["user_id"],
            "memory_text": args.text,
            "source": args.source,
        },
        token=config["access_token"],
    )

    if err:
        # 500 通常是 LLM 调用暂时失败（新虾无历史上下文时常见），不算致命错误
        if "500" in err:
            print(f"[!] 记忆注入暂时失败（服务端处理异常，稍后重试即可）: {err}")
        else:
            print(f"[✗] 记忆注入失败: {err}", file=sys.stderr)
            sys.exit(1)
        return

    summary = resp.get("memory_summary", "")
    name = config.get("lobster_name", "虾")
    print(f"[✓] {name}已记住了这些信息。")
    if summary:
        preview = summary[:120] + ("..." if len(summary) > 120 else "")
        print(f"    记忆预览：{preview}")


if __name__ == "__main__":
    main()
