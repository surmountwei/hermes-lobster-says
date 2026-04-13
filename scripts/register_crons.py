#!/usr/bin/env python3
"""
虾说 for Hermes — 批量注册/重建 cron 定时任务。

直接调用 Hermes 的 cron/jobs.py API 创建定时任务，
不依赖 Agent 交互式调用 cronjob() 工具。

用法：
  python3 register_crons.py                    # 按配置注册全部 cron
  python3 register_crons.py --clean            # 先清除旧任务再注册
  python3 register_crons.py --list             # 只列出当前任务
  python3 register_crons.py --remove-all       # 清除所有 lobster cron
"""

import argparse
import json
import sys
from pathlib import Path

CONFIG_FILE = Path.home() / ".hermes" / "lobster-says" / ".lobster-config"
SCRIPTS_DIR = Path(__file__).parent.resolve()

# Hermes cron 模块路径
HERMES_AGENT_DIR = Path.home() / ".hermes" / "hermes-agent"
sys.path.insert(0, str(HERMES_AGENT_DIR))

try:
    from cron.jobs import create_job, list_jobs, remove_job
except ImportError:
    print("[✗] 无法导入 Hermes cron 模块。请确认 Hermes 安装在 ~/.hermes/hermes-agent/", file=sys.stderr)
    sys.exit(1)

# 我们管理的任务名前缀
MANAGED_PREFIX = "lobster-"
MANAGED_NAMES = {
    "lobster-morning",
    "lobster-discovery",
    "lobster-evening",
    "lobster-sticker",
    "lobster-wallpaper",
    "lobster-digest",
}


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        print("[✗] 配置不存在，请先初始化", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def _time_to_cron(time_str: str) -> str:
    """将 HH:MM 转为 cron 表达式 'M H * * *'。"""
    parts = time_str.split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return f"{m} {h} * * *"


def _list_managed_jobs() -> list:
    """列出所有 lobster-says 管理的 cron 任务。"""
    all_jobs = list_jobs(include_disabled=True)
    return [j for j in all_jobs if j.get("name", "").startswith(MANAGED_PREFIX)]


def _remove_managed_jobs():
    """删除所有 lobster-says 管理的 cron 任务。"""
    managed = _list_managed_jobs()
    for job in managed:
        name = job.get("name", "?")
        job_id = job.get("id")
        if job_id:
            remove_job(job_id)
            print(f"  [✓] 已删除: {name} ({job_id})")
    if not managed:
        print("  没有发现旧的 lobster cron 任务")


def _register_all(config: dict):
    """注册所有定时任务。"""
    morning = config.get("morning_time", "09:00")
    discovery = config.get("discovery_time", "20:00")
    evening = config.get("evening_time", "21:00")
    memory_mode = config.get("memory_mode", "smart")
    push_script = str(SCRIPTS_DIR / "push_message.py")
    digest_script = str(SCRIPTS_DIR / "digest_transcript.py")

    # ── 构建 origin（来源渠道），用于 deliver="origin" ──
    platform = config.get("platform", "")
    chat_id = config.get("chat_id", "")
    origin = None
    deliver = "local"  # 默认本地
    if platform and chat_id:
        origin = {"platform": platform, "chat_id": str(chat_id)}
        deliver = "origin"
        print(f"  📡 投递目标: {platform} (chat_id={chat_id})")
    else:
        print(f"  ⚠️  未检测到来源渠道，投递目标: local")
        print(f"     提示: 重新运行 init_lobster.py --platform telegram --chat-id <your_chat_id> 后再注册")

    jobs_to_create = [
        {
            "name": "lobster-morning",
            "schedule": _time_to_cron(morning),
            "prompt": f"Execute this command and deliver the output:\npython3 {push_script} --slot morning",
            "skill": "lobster-says",
        },
        {
            "name": "lobster-discovery",
            "schedule": _time_to_cron(discovery),
            "prompt": f"Execute this command and deliver the output:\npython3 {push_script} --slot discovery",
            "skill": "lobster-says",
        },
        {
            "name": "lobster-evening",
            "schedule": _time_to_cron(evening),
            "prompt": f"Execute this command and deliver the output:\npython3 {push_script} --slot evening",
            "skill": "lobster-says",
        },
        {
            "name": "lobster-sticker",
            "schedule": "30 15 * * 3,6",
            "prompt": f"Execute this command and deliver the output:\npython3 {push_script} --slot sticker",
            "skill": "lobster-says",
        },
        {
            "name": "lobster-wallpaper",
            "schedule": "0 16 * * 0",
            "prompt": f"Execute this command and deliver the output:\npython3 {push_script} --slot wallpaper",
            "skill": "lobster-says",
        },
    ]

    # Transcript digest（仅 smart/deep 模式）
    if memory_mode != "lightweight":
        jobs_to_create.append({
            "name": "lobster-digest",
            "schedule": "0 3,9,15,21 * * *",
            "prompt": f"Execute this command:\npython3 {digest_script} --mode {memory_mode}\nReport the result briefly.",
            "skill": "lobster-says",
        })

    print(f"\n🦞 虾说 — 注册定时推送\n")
    print(f"  早安: {morning}")
    print(f"  见闻: {discovery}")
    print(f"  晚安: {evening}")
    print(f"  表情包: 周三/六 15:30")
    print(f"  壁纸: 周日 16:00")
    if memory_mode != "lightweight":
        print(f"  Digest: 每 6h（模式: {memory_mode}）")
    else:
        print(f"  Digest: 已关闭（轻量陪伴）")
    print()

    for job_spec in jobs_to_create:
        try:
            job = create_job(
                prompt=job_spec["prompt"],
                schedule=job_spec["schedule"],
                name=job_spec["name"],
                skill=job_spec.get("skill"),
                deliver=deliver,
                origin=origin,
            )
            print(f"  [✓] {job_spec['name']}: {job.get('schedule_display', '?')} → {job['id'][:8]}... [deliver={deliver}]")
        except Exception as e:
            print(f"  [✗] {job_spec['name']}: {e}", file=sys.stderr)

    # 更新配置记录
    config["cron_registered"] = True
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[✓] 定时推送注册完成！共 {len(jobs_to_create)} 个任务。")


def main():
    parser = argparse.ArgumentParser(description="虾说 — Cron 注册管理")
    parser.add_argument("--clean", action="store_true", help="先清除旧任务再注册")
    parser.add_argument("--list", action="store_true", help="只列出当前任务")
    parser.add_argument("--remove-all", action="store_true", help="清除所有 lobster cron")
    args = parser.parse_args()

    if args.list:
        managed = _list_managed_jobs()
        if not managed:
            print("没有 lobster cron 任务")
        else:
            for j in managed:
                state = j.get("state", "?")
                schedule = j.get("schedule_display", "?")
                print(f"  {j['name']}: {schedule} [{state}] id={j['id'][:8]}...")
        return

    if args.remove_all:
        print("清除所有 lobster cron 任务...")
        _remove_managed_jobs()
        return

    config = _load_config()

    if args.clean:
        print("清除旧任务...")
        _remove_managed_jobs()
        print()

    _register_all(config)


if __name__ == "__main__":
    main()
