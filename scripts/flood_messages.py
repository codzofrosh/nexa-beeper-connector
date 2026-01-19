#!/usr/bin/env python3
"""Flood the sidecar /message endpoint with test messages.

Usage examples:
  python scripts/flood_messages.py --start 1 --end 2000
  python scripts/flood_messages.py --start 1 --end 2000 --concurrency 20

Requires: pip install requests
"""

from __future__ import annotations
import argparse
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

logger = logging.getLogger("flood")


def send(url: str, i: int, timeout: float = 5.0) -> tuple[int, int | None, str]:
    payload = {
        "platform": "whatsapp",
        "room_id": "r1",
        "sender": "+91",
        "sender_name": "Flood",
        "is_group": False,
        "timestamp": i,
        "text": "price",
        "message_id": f"flood-{i}",
    }

    logger.info("REQUEST %s -> %s", i, payload)

    try:
        r = requests.post(f"{url}/message", json=payload, timeout=timeout)
        logger.info("RESPONSE %s <- status=%s body=%s", i, r.status_code, r.text[:500])
        return i, r.status_code, r.text[:200]
    except Exception as e:
        logger.exception("ERROR %s -> %s", i, e)
        return i, None, str(e)


def main() -> None:
    p = argparse.ArgumentParser(description="Flood test script for Nexa sidecar /message endpoint")
    p.add_argument("--url", default="http://localhost:8080", help="Base URL of sidecar (default: http://localhost:8080)")
    p.add_argument("--start", type=int, default=1, help="Start index (default: 1)")
    p.add_argument("--end", type=int, default=2000, help="End index (inclusive, default: 2000)")
    p.add_argument("--concurrency", type=int, default=1, help="Number of concurrent workers (default: 1)")
    p.add_argument("--delay", type=float, default=0.0, help="Delay in seconds between requests when concurrency=1 (default: 0)")
    p.add_argument("--timeout", type=float, default=5.0, help="Per-request timeout in seconds (default: 5)")
    p.add_argument("--log-file", default="scripts/flood.log", help="Path to log file (default: scripts/flood.log)")
    args = p.parse_args()

    # Configure logging to stdout and file
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(args.log_file, encoding="utf-8")],
    )

    total = args.end - args.start + 1
    logger.info("Starting flood of %d messages to %s (concurrency=%d)", total, args.url, args.concurrency)

    if args.concurrency <= 1:
        for i in range(args.start, args.end + 1):
            i, status, info = send(args.url, i, timeout=args.timeout)
            logger.info("%s: %s %s", i, status, info)
            if args.delay:
                time.sleep(args.delay)

    else:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = {ex.submit(send, args.url, i, args.timeout): i for i in range(args.start, args.end + 1)}
            done = 0
            for fut in as_completed(futures):
                i, status, info = fut.result()
                done += 1
                logger.info("%d/%d - %s: %s %s", done, total, i, status, info)


if __name__ == "__main__":
    main()
