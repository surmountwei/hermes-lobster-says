#!/usr/bin/env python3
"""
虾说 for Hermes — Transcript 消化脚本。

读取 Hermes 本地会话日志 (~/.hermes/sessions/*.jsonl)，
提取用户/助手对话内容，按 memory_mode 处理后上传到 nixiashuo.com。

三档模式：
  lightweight: 不执行任何读取或上传
  smart:       本地提炼为摘要+标签，仅上传摘要（privacy_mode=true）
  deep:        上传原始 transcript 条目到服务端消化
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CONFIG_FILE = Path.home() / ".hermes" / "lobster-says" / ".lobster-config"
SESSIONS_DIR = Path.home() / ".hermes" / "sessions"
APP_TZ = timezone(timedelta(hours=8))
APP_TZ_LABEL = "Asia/Shanghai"


def _http(url: str, method: str = "GET", data: dict = None, token: str = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:300]
        print(f"[✗] HTTP {e.code}: {err}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"[✗] 网络错误: {e.reason}", file=sys.stderr)
        sys.exit(1)


def _extract_text(content) -> str:
    """从 Hermes 消息内容中提取纯文本。"""
    if isinstance(content, str):
        return content.strip()
    texts = []
    if isinstance(content, list):
        for part in content:
            if isinstance(part, str):
                texts.append(part.strip())
            elif isinstance(part, dict):
                t = part.get("type", "")
                if t in ("text", "input_text", "output_text"):
                    texts.append((part.get("text") or "").strip())
    elif isinstance(content, dict):
        t = content.get("type", "")
        if t in ("text", "input_text", "output_text"):
            texts.append((content.get("text") or "").strip())
    return "\n".join(t for t in texts if t)


def _strip_metadata(text: str) -> str:
    """去除 bridge metadata 前缀。"""
    fence = re.escape("```")
    patterns = [
        rf"^Conversation info \(untrusted metadata\):\s*{fence}json\n.*?{fence}\s*",
        rf"^Sender \(untrusted metadata\):\s*{fence}json\n.*?{fence}\s*",
    ]
    for p in patterns:
        text = re.sub(p, "", text, flags=re.S)
    return text.strip()


def _parse_timestamp(ts_str: str, fallback: datetime) -> datetime:
    """尝试多种格式解析时间戳。"""
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return fallback


def collect_entries(hours: int, max_entries: int) -> tuple:
    """从 Hermes sessions 收集最近的对话条目。"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    entries = []
    source_session_ids = []
    time_start = None
    time_end = None

    signal_tags = {
        "late_night_count": 0,
        "early_morning_count": 0,
        "weekend_active_count": 0,
        "total_user_messages": 0,
        "time_range_hours": hours,
        "timezone": APP_TZ_LABEL,
    }

    if not SESSIONS_DIR.exists():
        return entries, source_session_ids, signal_tags, time_start, time_end

    jsonl_files = sorted(
        SESSIONS_DIR.glob("*.jsonl"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    for jsonl_path in jsonl_files:
        mtime = datetime.fromtimestamp(jsonl_path.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            break

        session_entries = []
        has_real_user = False

        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except Exception:
                        continue

                    ts_str = record.get("timestamp") or record.get("ts", "")
                    ts = _parse_timestamp(ts_str, mtime) if ts_str else mtime
                    if ts < cutoff:
                        continue

                    # 提取内容
                    msg_obj = record.get("message") if isinstance(record.get("message"), dict) else None
                    if msg_obj:
                        role = msg_obj.get("role", "")
                        content = _extract_text(msg_obj.get("content"))
                    else:
                        role = record.get("role", "")
                        content = _extract_text(record.get("content", record.get("message", "")))

                    if role not in ("user", "human", "assistant"):
                        continue

                    content = _strip_metadata(content)
                    if not content:
                        continue

                    normalized_role = "user" if role in ("user", "human") else "assistant"

                    # 过滤自动触发
                    if normalized_role == "user" and any(
                        content.startswith(p) for p in ("[cron:", "[hook:", "[automation:")
                    ):
                        continue

                    if normalized_role == "user":
                        has_real_user = True
                        signal_tags["total_user_messages"] += 1
                        local_hour = (ts.hour + 8) % 24
                        if 0 <= local_hour < 5:
                            signal_tags["late_night_count"] += 1
                        elif 5 <= local_hour < 7:
                            signal_tags["early_morning_count"] += 1
                        if (ts + timedelta(hours=8)).weekday() >= 5:
                            signal_tags["weekend_active_count"] += 1

                    local_ts = ts.astimezone(APP_TZ)
                    session_entries.append({
                        "timestamp": f"{local_ts.strftime('%Y-%m-%d %H:%M')} {APP_TZ_LABEL}",
                        "role": normalized_role,
                        "content": content[:5000],
                    })

                    if time_start is None or ts < time_start:
                        time_start = ts
                    if time_end is None or ts > time_end:
                        time_end = ts
        except Exception:
            continue

        if session_entries and has_real_user:
            source_session_ids.append(jsonl_path.stem)
            for entry in session_entries:
                if len(entries) < max_entries:
                    entries.append(entry)

    entries.sort(key=lambda e: e["timestamp"])
    return entries, source_session_ids, signal_tags, time_start, time_end


def _build_smart_summary(entries: list, signal_tags: dict) -> tuple:
    """本地提炼摘要和语义标签（不需要调 LLM，用规则提取）。"""
    user_msgs = [e["content"] for e in entries if e.get("role") == "user"][-15:]

    # 构建摘要文本
    parts = ["用户近期对话摘要：", ""]
    for msg in user_msgs:
        snippet = msg[:200].replace("\n", " ")
        parts.append(f"- {snippet}")
    parts.append("")
    parts.append(f"统计信号: {json.dumps(signal_tags, ensure_ascii=False)}")
    summary = "\n".join(parts)

    # 规则提取语义标签
    tags = []
    keywords_map = {
        "deadline": ["deadline", "截止", "上线", "提测", "发版", "ddl"],
        "mood-shift": ["情绪变化", "情绪波动", "焦虑", "烦躁"],
        "milestone": ["完成", "搞定", "里程碑", "上线成功"],
        "life-event": ["生日", "搬家", "旅行", "家人", "宠物"],
        "burnout-risk": ["疲惫", "累", "撑不住", "倦怠"],
        "late-night": ["凌晨", "深夜", "半夜"],
        "weekend-work": ["周末", "周六", "周日"],
    }
    combined = " ".join(user_msgs).lower()
    for tag, kws in keywords_map.items():
        if any(kw in combined for kw in kws):
            tags.append(tag)

    if signal_tags.get("late_night_count", 0) > 0 and "late-night" not in tags:
        tags.append("late-night")

    return summary, tags


def main():
    parser = argparse.ArgumentParser(description="虾说 — Transcript 消化")
    parser.add_argument("--hours", type=int, default=6)
    parser.add_argument("--max-entries", type=int, default=300)
    parser.add_argument("--mode", choices=["lightweight", "smart", "deep"], default="")
    args = parser.parse_args()

    if not CONFIG_FILE.exists():
        print("[✗] 配置不存在，请先初始化", file=sys.stderr)
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    mode = args.mode or config.get("memory_mode", "smart")
    api_base = config.get("api_base", "https://nixiashuo.com").rstrip("/")
    user_id = config["user_id"]
    token = config["access_token"]

    if mode == "lightweight":
        print("[✓] 轻量陪伴模式：不执行 transcript digest")
        return

    print(f"🧠 虾说 — Transcript 消化（模式: {mode}，回溯: {args.hours}h）")

    entries, session_ids, signal_tags, t_start, t_end = collect_entries(args.hours, args.max_entries)

    if not entries:
        print(f"[✓] 过去 {args.hours} 小时没有新的 transcript 记录，跳过消化。")
        return

    print(f"[…] 收集到 {len(entries)} 条记录，来自 {len(session_ids)} 个会话")

    if mode == "smart":
        # Smart 模式：本地提炼，上传摘要
        summary, semantic_tags = _build_smart_summary(entries, signal_tags)
        payload = {
            "user_id": user_id,
            "entries": [],
            "signal_tags": signal_tags,
            "source_type": "skill_cron",
            "source_session_ids": session_ids,
            "source_sessions": len(session_ids),
            "privacy_mode": True,
            "pre_digested_summary": summary,
            "pre_digested_semantic_tags": semantic_tags,
        }
    else:
        # Deep 模式：上传原始 transcript
        payload = {
            "user_id": user_id,
            "entries": entries,
            "signal_tags": signal_tags,
            "source_type": "skill_cron",
            "source_session_ids": session_ids,
            "source_sessions": len(session_ids),
        }

    if t_start:
        payload["time_range_start"] = t_start.strftime("%Y-%m-%dT%H:%M:%S")
    if t_end:
        payload["time_range_end"] = t_end.strftime("%Y-%m-%dT%H:%M:%S")

    resp = _http(f"{api_base}/api/transcript/digest", method="POST", data=payload, token=token)

    digest_id = resp.get("digest_id", "?")
    summary_len = len(resp.get("digest_summary", ""))
    print(f"[✓] Transcript 消化成功：digest_id={digest_id}, 摘要长度={summary_len}")


if __name__ == "__main__":
    main()
