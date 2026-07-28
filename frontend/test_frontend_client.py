#!/usr/bin/env python3
"""
Frontend API Test Client
Queries the frontend's FastAPI chat stream endpoint and prints the streaming response.
"""

import sys
import json
import argparse
import httpx

DEFAULT_FRONTEND_URL = "http://localhost:8000"
DEFAULT_QUERY = "How many EUR is 100 USD?"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test client for the Currency Agent Frontend API."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_FRONTEND_URL,
        help=f"Base URL of the frontend server (default: {DEFAULT_FRONTEND_URL})",
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help=f"Query message to send (default: '{DEFAULT_QUERY}')",
    )
    parser.add_argument(
        "--user",
        default="cli_test_user",
        help="User ID for the session (default: 'cli_test_user')",
    )
    return parser.parse_args()


def run_test_client(base_url: str, query: str, user_id: str):
    chat_stream_url = f"{base_url.rstrip('/')}/api/chat_stream"

    payload = {"message": query, "user_id": user_id}

    print("--- 🚀 Querying Frontend API Stream ---")
    print(f"Endpoint: {chat_stream_url}")
    print(f'Query:    "{query}"')
    print(f"User ID:  {user_id}")
    print("----------------------------------------")

    try:
        # Use streaming response to process NDJSON line-by-line
        with httpx.stream(
            "POST", chat_stream_url, json=payload, timeout=30.0
        ) as response:
            if response.status_code != 200:
                print(f"❌ Error: Server returned HTTP {response.status_code}")
                # Read response content for error info
                response.read()
                print(response.text)
                return

            for line in response.iter_lines():
                if not line.strip():
                    continue

                try:
                    event = json.loads(line)
                    event_type = event.get("type")
                    event_text = event.get("text", "")

                    if event_type == "progress":
                        # Print progress ticks in cyan
                        print(f"\033[96m[Progress]\033[0m {event_text}")
                    elif event_type == "result":
                        # Print final result in bold green
                        print("----------------------------------------")
                        print("\033[92m\033[1m[Final Result]\033[0m")
                        print(event_text)
                        print("----------------------------------------")
                    else:
                        print(f"[Unknown Event: {event_type}] {event_text}")

                except json.JSONDecodeError:
                    print(f"⚠️ Failed to parse JSON line: {line}")

    except httpx.ConnectError:
        print(
            f"❌ Connection Failed: Could not connect to frontend server at {base_url}."
        )
        print(
            "Ensure the frontend server is running (e.g. run 'make frontend' or python3 frontend/main.py)."
        )
    except Exception as e:
        print(f"❌ Error occurred: {e}")


if __name__ == "__main__":
    args = parse_args()
    # Force output encoding if necessary
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(
        sys.stdout, "reconfigure"
    ) else None
    run_test_client(args.url, args.query, args.user)
