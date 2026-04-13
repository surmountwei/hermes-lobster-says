#!/usr/bin/env python3
"""虾说 for Hermes — 更新本地配置。"""

import argparse
import json
import sys
from pathlib import Path

CONFIG_FILE = Path.home() / ".hermes" / "lobster-says" / ".lobster-config"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-mode", choices=["lightweight", "smart", "deep"])
    parser.add_argument("--morning")
    parser.add_argument("--discovery")
    parser.add_argument("--evening")
    parser.add_argument("--owner-nickname")
    args = parser.parse_args()

    if not CONFIG_FILE.exists():
        print("[✗] 配置不存在", file=sys.stderr)
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    updated = []

    if args.memory_mode:
        config["memory_mode"] = args.memory_mode
        updated.append(f"理解模式 → {args.memory_mode}")
    if args.morning:
        config["morning_time"] = args.morning
        updated.append(f"早安 → {args.morning}")
    if args.discovery:
        config["discovery_time"] = args.discovery
        updated.append(f"见闻 → {args.discovery}")
    if args.evening:
        config["evening_time"] = args.evening
        updated.append(f"晚安 → {args.evening}")
    if args.owner_nickname:
        config["nickname_for_user"] = args.owner_nickname
        updated.append(f"称呼 → {args.owner_nickname}")

    if not updated:
        print("[!] 没有需要更新的配置")
        return

    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[✓] 配置已更新：{', '.join(updated)}")
    print("[!] 提醒：如果修改了推送时间，需要同步更新 Hermes cron 任务的 schedule。")


if __name__ == "__main__":
    main()
