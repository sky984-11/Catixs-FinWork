#!/usr/bin/env python3
"""Akvorado traffic anomaly detector with Feishu alerting.

Example:
    AKVORADO_FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" \
    python scripts/akvorado_alert.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CLICKHOUSE_CONTAINER = "akvorado-clickhouse-1"
DEFAULT_FLOW_TABLE = "flows"
DEFAULT_STATE_FILE = "/tmp/akvorado_alert_state.json"
AKVORADO_FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e176ae5c-bbd8-43e0-88f1-9a14a849644e"


@dataclass(frozen=True)
class AlertRow:
    subnet: str
    cur_bytes: int
    prev_bytes: int
    ratio: float
    level: str


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got: {value}") from exc


def build_query(
    *,
    flow_table: str,
    current_minutes: int,
    previous_minutes: int,
    min_bytes: int,
    ratio_threshold: float,
    limit: int,
) -> str:
    """Build a ClickHouse query for IPv4 /24 traffic bursts.

    Akvorado often stores IPv4 addresses as IPv4-mapped IPv6, such as
    ::ffff:45.129.228.1. The query normalizes those values before grouping.
    """
    return f"""
WITH
current AS
(
    SELECT
        concat(
            splitByChar('.', toString(DstAddr))[1], '.',
            splitByChar('.', toString(DstAddr))[2], '.',
            splitByChar('.', toString(DstAddr))[3], '.0/24'
        ) AS subnet,
        sum(Bytes) AS cur_bytes
    FROM
    (
        SELECT
            replaceRegexpOne(toString(DstAddr), '^::ffff:', '') AS DstAddr,
            Bytes
        FROM {flow_table}
        WHERE TimeReceived > now() - toIntervalMinute({current_minutes})
    )
    WHERE
        isIPv4String(toString(DstAddr))
    GROUP BY subnet
),
previous AS
(
    SELECT
        concat(
            splitByChar('.', toString(DstAddr))[1], '.',
            splitByChar('.', toString(DstAddr))[2], '.',
            splitByChar('.', toString(DstAddr))[3], '.0/24'
        ) AS subnet,
        sum(Bytes) AS prev_bytes
    FROM
    (
        SELECT
            replaceRegexpOne(toString(DstAddr), '^::ffff:', '') AS DstAddr,
            Bytes
        FROM {flow_table}
        WHERE TimeReceived BETWEEN
            now() - toIntervalMinute({current_minutes + previous_minutes})
            AND now() - toIntervalMinute({current_minutes})
    )
    WHERE
        isIPv4String(toString(DstAddr))
    GROUP BY subnet
)
SELECT
    c.subnet AS subnet,
    toUInt64(c.cur_bytes) AS cur_bytes,
    toUInt64(ifNull(p.prev_bytes, 0)) AS prev_bytes,
    round(c.cur_bytes / greatest(ifNull(p.prev_bytes, 0), 1), 2) AS ratio,
    multiIf(
        c.cur_bytes >= {min_bytes * 10} OR ratio >= {ratio_threshold * 5}, 'CRITICAL',
        c.cur_bytes >= {min_bytes * 3} OR ratio >= {ratio_threshold * 2}, 'HIGH',
        'WARN'
    ) AS level
FROM current c
LEFT JOIN previous p USING (subnet)
WHERE
    c.cur_bytes >= {min_bytes}
    AND c.cur_bytes >= greatest(ifNull(p.prev_bytes, 0) * {ratio_threshold}, 1)
ORDER BY ratio DESC, cur_bytes DESC
LIMIT {limit}
FORMAT JSONEachRow
""".strip()


def run_clickhouse_query(container: str, query: str, timeout: int) -> list[AlertRow]:
    cmd = ["docker", "exec", container, "clickhouse-client", "--query", query]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)

    if proc.returncode != 0:
        raise RuntimeError(f"clickhouse-client failed: {proc.stderr.strip() or proc.stdout.strip()}")

    rows: list[AlertRow] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        item: dict[str, Any] = json.loads(line)
        rows.append(
            AlertRow(
                subnet=str(item["subnet"]),
                cur_bytes=int(item["cur_bytes"]),
                prev_bytes=int(item["prev_bytes"]),
                ratio=float(item["ratio"]),
                level=str(item["level"]),
            )
        )
    return rows


def load_state(path: Path) -> dict[str, float]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_state(path: Path, state: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def filter_by_cooldown(rows: list[AlertRow], state_file: Path, cooldown_seconds: int) -> list[AlertRow]:
    if cooldown_seconds <= 0:
        return rows

    now = time.time()
    state = load_state(state_file)
    fresh_rows: list[AlertRow] = []

    for row in rows:
        key = f"{row.subnet}:{row.level}"
        last_sent_at = float(state.get(key, 0))
        if now - last_sent_at >= cooldown_seconds:
            fresh_rows.append(row)
            state[key] = now

    cutoff = now - cooldown_seconds * 3
    state = {key: value for key, value in state.items() if float(value) >= cutoff}
    save_state(state_file, state)
    return fresh_rows


def human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if size < 1024 or unit == "PB":
            return f"{size:.2f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024
    return f"{value}B"


def level_template(level: str) -> str:
    return {
        "CRITICAL": "red",
        "HIGH": "orange",
        "WARN": "yellow",
    }.get(level, "blue")


def build_feishu_card(rows: list[AlertRow], current_minutes: int, previous_minutes: int) -> dict[str, Any]:
    highest_level = rows[0].level if rows else "WARN"
    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**检测窗口**：最近 {current_minutes} 分钟 vs 前 {previous_minutes} 分钟\n"
                    f"**异常网段数**：{len(rows)}\n"
                    f"**最高等级**：{highest_level}"
                ),
            },
        },
        {"tag": "hr"},
    ]

    for row in rows:
        elements.append(
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**网段**\n{row.subnet}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**等级**\n{row.level}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**当前流量**\n{human_bytes(row.cur_bytes)}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**历史流量**\n{human_bytes(row.prev_bytes)}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**突增倍率**\n{row.ratio}x"}},
                ],
            }
        )
        elements.append({"tag": "hr"})

    elements.append(
        {
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": "由 Akvorado ClickHouse 流量突增检测脚本自动发送"}],
        }
    )

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": level_template(highest_level),
                "title": {"tag": "plain_text", "content": "Akvorado 流量异常告警"},
            },
            "elements": elements,
        },
    }


def send_feishu(webhook: str, payload: dict[str, Any], timeout: int) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to send Feishu alert: {exc}") from exc

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        result = {}
    if result and result.get("StatusCode", result.get("code", 0)) not in (0, "0"):
        raise RuntimeError(f"Feishu webhook returned error: {body}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect Akvorado traffic bursts and send Feishu alerts.")
    parser.add_argument("--container", default=os.getenv("AKVORADO_CLICKHOUSE_CONTAINER", DEFAULT_CLICKHOUSE_CONTAINER))
    parser.add_argument("--table", default=os.getenv("AKVORADO_FLOW_TABLE", DEFAULT_FLOW_TABLE))
    parser.add_argument("--current-minutes", type=int, default=env_int("AKVORADO_CURRENT_MINUTES", 5))
    parser.add_argument("--previous-minutes", type=int, default=env_int("AKVORADO_PREVIOUS_MINUTES", 5))
    parser.add_argument("--min-mb", type=int, default=env_int("AKVORADO_MIN_MB", 20))
    parser.add_argument("--ratio", type=float, default=float(os.getenv("AKVORADO_RATIO", "3")))
    parser.add_argument("--limit", type=int, default=env_int("AKVORADO_LIMIT", 5))
    parser.add_argument("--cooldown-seconds", type=int, default=env_int("AKVORADO_COOLDOWN_SECONDS", 1800))
    parser.add_argument("--state-file", default=os.getenv("AKVORADO_STATE_FILE", DEFAULT_STATE_FILE))
    parser.add_argument("--timeout", type=int, default=env_int("AKVORADO_TIMEOUT", 20))
    parser.add_argument("--dry-run", action="store_true", help="Print Feishu card payload without sending message.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    webhook = os.getenv("AKVORADO_FEISHU_WEBHOOK", AKVORADO_FEISHU_WEBHOOK)
    min_bytes = args.min_mb * 1024 * 1024

    query = build_query(
        flow_table=args.table,
        current_minutes=args.current_minutes,
        previous_minutes=args.previous_minutes,
        min_bytes=min_bytes,
        ratio_threshold=args.ratio,
        limit=args.limit,
    )
    rows = run_clickhouse_query(args.container, query, args.timeout)
    rows = filter_by_cooldown(rows, Path(args.state_file), args.cooldown_seconds)

    if not rows:
        print("No traffic anomalies detected.")
        return 0

    payload = build_feishu_card(rows, args.current_minutes, args.previous_minutes)
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not webhook:
        raise SystemExit("AKVORADO_FEISHU_WEBHOOK is required unless --dry-run is used.")

    send_feishu(webhook, payload, args.timeout)
    print(f"Sent {len(rows)} Akvorado traffic alert(s).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
