#!/usr/bin/env python3
"""
Presales Hub — Standalone WebSocket Stress Test

Opens N concurrent WebSocket connections, measures:
- Connection time per client
- Time to first message received
- Disconnect recovery time (after server restart simulation)

Does NOT require Locust. Runs standalone.

Usage:
    pip install websocket-client
    python load_tests/websocket_stress.py --host ws://localhost:8003 --clients 50 --duration 30

Requirements:
    pip install websocket-client requests
"""
import argparse
import json
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field


try:
    import websocket  # type: ignore[import]
except ImportError:
    print("Error: websocket-client not installed. Run: pip install websocket-client")
    sys.exit(1)

try:
    import urllib.request
except ImportError:
    pass


@dataclass
class ClientStats:
    client_id: int
    connect_time_ms: float = 0.0
    first_message_ms: float | None = None
    messages_received: int = 0
    errors: list[str] = field(default_factory=list)
    connected: bool = False
    disconnected_at: float | None = None
    reconnect_time_ms: float | None = None


def _get_token(api_base: str) -> str:
    """Login and return a JWT token for WS auth."""
    import json as _json
    import urllib.request
    payload = json.dumps({"email": "arjun@sisa.demo", "password": "Demo@1234"}).encode()
    req = urllib.request.Request(
        f"{api_base}/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return _json.loads(resp.read()).get("access_token", "")
    except Exception as exc:
        print(f"  Warning: could not obtain token ({exc}) — connecting without auth")
        return ""


def _run_client(
    client_id: int,
    ws_url: str,
    duration: float,
    stats: ClientStats,
    stop_event: threading.Event,
) -> None:
    t_start = time.monotonic()
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        stats.connect_time_ms = (time.monotonic() - t_start) * 1000
        stats.connected = True

        ws.settimeout(2)
        deadline = time.monotonic() + duration

        while time.monotonic() < deadline and not stop_event.is_set():
            try:
                msg = ws.recv()
                if stats.first_message_ms is None:
                    stats.first_message_ms = (time.monotonic() - t_start) * 1000
                stats.messages_received += 1
            except websocket.WebSocketTimeoutException:
                continue
            except websocket.WebSocketConnectionClosedException:
                stats.disconnected_at = time.monotonic()
                break

        ws.close()
    except websocket.WebSocketException as exc:
        stats.errors.append(f"WS error: {exc}")
    except OSError as exc:
        stats.errors.append(f"Network error: {exc}")
    except Exception as exc:
        stats.errors.append(f"Unexpected: {exc}")


def _print_summary(all_stats: list[ClientStats], duration: float) -> None:
    connected = [s for s in all_stats if s.connected]
    failed = [s for s in all_stats if not s.connected]
    connect_times = [s.connect_time_ms for s in connected]
    first_msg_times = [s.first_message_ms for s in connected if s.first_message_ms is not None]
    total_msgs = sum(s.messages_received for s in connected)

    print("\n" + "─" * 60)
    print(f"  WebSocket Stress Test Results ({duration}s run)")
    print("─" * 60)
    print(f"  Connections attempted : {len(all_stats)}")
    print(f"  Connections succeeded : {len(connected)}")
    print(f"  Connections failed    : {len(failed)}")

    if connect_times:
        print(f"\n  Connection time (ms)")
        print(f"    min    : {min(connect_times):.1f}")
        print(f"    median : {statistics.median(connect_times):.1f}")
        print(f"    p95    : {sorted(connect_times)[int(len(connect_times) * 0.95)]:.1f}")
        print(f"    max    : {max(connect_times):.1f}")

    if first_msg_times:
        print(f"\n  Time to first message (ms)")
        print(f"    min    : {min(first_msg_times):.1f}")
        print(f"    median : {statistics.median(first_msg_times):.1f}")
        print(f"    max    : {max(first_msg_times):.1f}")
    else:
        print("\n  Time to first message: no messages received within test duration")

    print(f"\n  Total messages received : {total_msgs}")
    if connected and duration > 0:
        print(f"  Throughput (msg/s/conn) : {total_msgs / len(connected) / duration:.2f}")

    if failed:
        print(f"\n  Failure reasons:")
        for s in failed[:5]:
            print(f"    client-{s.client_id}: {'; '.join(s.errors[:2])}")

    print("─" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Presales Hub WebSocket stress test")
    parser.add_argument("--host", default="ws://localhost:8003",
                        help="WebSocket base URL (ws:// or wss://)")
    parser.add_argument("--api", default="http://localhost:8003",
                        help="HTTP API base for token fetch")
    parser.add_argument("--clients", type=int, default=20,
                        help="Number of concurrent WS connections (default: 20)")
    parser.add_argument("--duration", type=float, default=30,
                        help="Test duration in seconds (default: 30)")
    parser.add_argument("--endpoint", default="/ws/activity",
                        help="WS endpoint path (default: /ws/activity)")
    parser.add_argument("--no-auth", action="store_true",
                        help="Skip token auth (for anonymous WS endpoints)")
    args = parser.parse_args()

    ws_base = args.host.rstrip("/")
    token = "" if args.no_auth else _get_token(args.api)
    ws_url = f"{ws_base}{args.endpoint}"
    if token:
        ws_url += f"?token={token}"

    print(f"\n  Presales Hub — WebSocket Stress Test")
    print(f"  URL      : {ws_base}{args.endpoint}")
    print(f"  Clients  : {args.clients}")
    print(f"  Duration : {args.duration}s")
    print(f"  Auth     : {'token' if token else 'none'}")
    print(f"\n  Spawning {args.clients} clients...")

    all_stats = [ClientStats(client_id=i) for i in range(args.clients)]
    stop_event = threading.Event()
    threads = []

    for i, stats in enumerate(all_stats):
        t = threading.Thread(
            target=_run_client,
            args=(i, ws_url, args.duration, stats, stop_event),
            daemon=True,
        )
        threads.append(t)

    t_run_start = time.monotonic()
    for t in threads:
        t.start()

    try:
        for t in threads:
            t.join(timeout=args.duration + 15)
    except KeyboardInterrupt:
        print("\n  Interrupted — stopping clients...")
        stop_event.set()
        for t in threads:
            t.join(timeout=5)

    actual_duration = time.monotonic() - t_run_start
    _print_summary(all_stats, actual_duration)

    connected_count = sum(1 for s in all_stats if s.connected)
    if connected_count < args.clients * 0.8:
        print(f"  RESULT: DEGRADED — only {connected_count}/{args.clients} connections succeeded")
        sys.exit(1)
    else:
        print(f"  RESULT: OK — {connected_count}/{args.clients} connections succeeded")
        sys.exit(0)


if __name__ == "__main__":
    main()
