#!/usr/bin/env python3
"""
Generic ClickUp REST API v2 helper — the shared implementation behind the
`clickup-tasks` skill. Any skill, scheduled task, or Claude Code session can
call this directly; it carries no domain-specific knowledge (no "contacts",
no email drafts, nothing Arctium-specific) — just create/read/update ClickUp
tasks, singly or in a batch, with auth and rate limiting handled for you.

Why REST instead of the ClickUp MCP server: the MCP server enforces its own
call quota (as low as 300 calls per rolling 24h on paid plans, 50/24h on
Free), separate from ClickUp's normal API rate limits — that quota gets
burned fast by any batch job. This uses ClickUp's standard per-minute rate
limit instead, via the shared token bucket described below.

Rate limiting: every API call this script makes (reads AND writes) goes
through a shared, file-locked token bucket capped at 50 calls per 60
seconds, stored next to this script in .clickup_rate_state.json. That
budget is shared across EVERY concurrent invocation of this script on the
machine — by any skill, any agent, any scheduled task — not per-process. If
you're writing a new skill that needs to talk to ClickUp, call this script
rather than hand-rolling your own requests, specifically so your calls
share this budget instead of adding an uncoordinated second stream of
traffic against ClickUp's real limit.

Auth: checks the CLICKUP_API_TOKEN environment variable first (useful for a
one-off override), then falls back to macOS Keychain automatically —
service name "clickup-api-token", no prompt. Store it once with:
    security add-generic-password -a "$USER" -s "clickup-api-token" \
        -w "pk_..." -T /usr/bin/security -U
Never hardcode a token in code, never log it, never write it into any task
content sent to ClickUp.

Usage:
    # sanity check you can reach a task
    python3 clickup_task.py check-task --task-id 86e2uq2ng

    # read a task's current name/status/description as JSON
    python3 clickup_task.py get-task --task-id 86e2uq2ng

    # list tasks in a list as JSON (id, name, status, text_content)
    python3 clickup_task.py list-tasks --list-id 901715151890 [--include-closed]

    # create one task
    python3 clickup_task.py create-task --list-id 901715151890 \
        --name "New prospect" --markdown "**Notes:**\n..." [--status "not started"]
    # (or --markdown-file notes.md instead of --markdown)

    # create many tasks from a JSON array file
    python3 clickup_task.py create-batch --list-id 901715151890 --file tasks.json

    # update one existing task (only the fields you pass are changed)
    python3 clickup_task.py update-task --task-id 86e2uq2ng \
        --markdown-file description.md [--name "..."] [--status "..."]

    # update many existing tasks from a JSON array file
    python3 clickup_task.py update-batch --file tasks.json

create-batch file shape — array of objects, one per new task:
    [
      {"name": "Company X", "markdown_content": "...", "status": "not started"}
      // "status" is optional; omit to use the list's default
    ]

update-batch file shape — array of objects, one per existing task:
    [
      {"task_id": "86e2uq2ng", "markdown_content": "...", "name": "...", "status": "..."}
      // only "task_id" is required; include only the fields you want changed
    ]

This script has no opinion about what goes in markdown_content — building
domain-specific content (e.g. formatting a list of contacts and drafted
emails) is the calling skill's job. Build the string, hand it to this
script, done.
"""

import argparse
import fcntl
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

API_BASE = "https://api.clickup.com/api/v2"

# Some macOS Python installs (notably python.org's installer, as opposed to
# Homebrew or Xcode's) don't wire the interpreter up to the system trust
# store, so urllib's default SSL context fails every HTTPS call with
# CERTIFICATE_VERIFY_FAILED. Building the context from certifi's bundle
# up front — rather than requiring every caller to remember to export
# SSL_CERT_FILE — means this is fixed once, here, for every skill and
# script that shells out to this file. Falls back to urllib's default
# context if certifi isn't installed or SSL_CERT_FILE is already set.
def _ssl_context():
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return None  # caller already pinned a trust store; don't override it
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return None


_SSL_CONTEXT = _ssl_context()

# --- Rate limiting: shared, file-locked token bucket -----------------------
_RATE_LIMIT_MAX_CALLS = 50
_RATE_LIMIT_WINDOW_SECONDS = 60.0
_RATE_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".clickup_rate_state.json")
_RATE_LOCK_PATH = _RATE_STATE_PATH + ".lock"


def _rate_limit_gate():
    """Block until it's safe to make one more ClickUp API call, honoring a
    shared cross-process budget of _RATE_LIMIT_MAX_CALLS per
    _RATE_LIMIT_WINDOW_SECONDS. Safe to call concurrently from many separate
    processes, regardless of which skill/agent/task started them."""
    while True:
        with open(_RATE_LOCK_PATH, "a+") as lockf:
            fcntl.flock(lockf, fcntl.LOCK_EX)
            try:
                now = time.time()
                try:
                    with open(_RATE_STATE_PATH) as sf:
                        timestamps = json.load(sf)
                except (FileNotFoundError, json.JSONDecodeError):
                    timestamps = []
                timestamps = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW_SECONDS]
                if len(timestamps) < _RATE_LIMIT_MAX_CALLS:
                    timestamps.append(now)
                    with open(_RATE_STATE_PATH, "w") as sf:
                        json.dump(timestamps, sf)
                    return
                wait_for = _RATE_LIMIT_WINDOW_SECONDS - (now - min(timestamps)) + 0.05
            finally:
                fcntl.flock(lockf, fcntl.LOCK_UN)
        time.sleep(max(wait_for, 0.1))


# --- Auth: env var, then Keychain -------------------------------------------
_KEYCHAIN_SERVICE = "clickup-api-token"


def _token_from_keychain():
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""),
             "-s", _KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=10,
        )
        token = result.stdout.strip()
        return token if result.returncode == 0 and token else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def get_token():
    token = os.environ.get("CLICKUP_API_TOKEN") or _token_from_keychain()
    if not token:
        print(
            "ERROR: no ClickUp token found in CLICKUP_API_TOKEN or in macOS Keychain "
            f"(service \"{_KEYCHAIN_SERVICE}\").\n"
            "Either export it directly:\n"
            "  export CLICKUP_API_TOKEN=\"pk_...\"\n"
            "or store it in Keychain once:\n"
            f"  security add-generic-password -a \"$USER\" -s \"{_KEYCHAIN_SERVICE}\" "
            "-w \"pk_...\" -T /usr/bin/security -U",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


# --- HTTP --------------------------------------------------------------------
def _request(method, path, token, body=None, params=None):
    _rate_limit_gate()
    url = f"{API_BASE}{path}"
    if params:
        query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{query}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CONTEXT) as resp:
            return True, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:500]
        return False, f"HTTP {e.code}: {detail}"
    except Exception as e:  # noqa: BLE001 - want to surface any failure, not crash the batch
        return False, str(e)


def _markdown_arg(args):
    if getattr(args, "markdown_file", None):
        with open(args.markdown_file) as f:
            return f.read()
    return getattr(args, "markdown", None)


# --- Commands ------------------------------------------------------------
def cmd_check_task(args, token):
    ok, result = _request("GET", f"/task/{args.task_id}", token)
    if not ok:
        print(f"FAILED to reach task {args.task_id}: {result}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: task \"{result.get('name')}\" (id {args.task_id}) is reachable.")


def cmd_get_task(args, token):
    ok, result = _request("GET", f"/task/{args.task_id}", token)
    if not ok:
        print(f"FAILED to reach task {args.task_id}: {result}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({
        "id": result.get("id"),
        "name": result.get("name"),
        "status": (result.get("status") or {}).get("status"),
        "text_content": result.get("text_content", ""),
    }, indent=2))


def cmd_list_tasks(args, token):
    tasks, page = [], 0
    while True:
        params = {"page": page}
        if args.include_closed:
            params["include_closed"] = "true"
        ok, result = _request("GET", f"/list/{args.list_id}/task", token, params=params)
        if not ok:
            print(f"FAILED to list tasks (page {page}): {result}", file=sys.stderr)
            sys.exit(1)
        batch = result.get("tasks", [])
        tasks.extend(batch)
        if result.get("last_page", True) or not batch:
            break
        page += 1
    print(json.dumps([
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "status": (t.get("status") or {}).get("status"),
            "text_content": t.get("text_content", ""),
        }
        for t in tasks
    ], indent=2))


def cmd_create_task(args, token):
    body = {"name": args.name}
    md = _markdown_arg(args)
    if md is not None:
        body["markdown_content"] = md
    if args.status:
        body["status"] = args.status
    ok, result = _request("POST", f"/list/{args.list_id}/task", token, body=body)
    if not ok:
        print(f"FAILED: {result}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: created task \"{args.name}\" (id {result.get('id')})")


def cmd_create_batch(args, token):
    with open(args.file) as f:
        items = json.load(f)
    if not isinstance(items, list):
        print("ERROR: --file must contain a JSON array of task objects.", file=sys.stderr)
        sys.exit(1)

    created, failed = [], []
    for i, item in enumerate(items, 1):
        name = item.get("name")
        if not name:
            failed.append(("?", "no name in entry"))
            print(f"[{i}/{len(items)}] SKIP: entry has no name")
            continue
        body = {"name": name}
        if "markdown_content" in item:
            body["markdown_content"] = item["markdown_content"]
        if item.get("status"):
            body["status"] = item["status"]

        ok, result = _request("POST", f"/list/{args.list_id}/task", token, body=body)
        if ok:
            created.append(name)
            print(f"[{i}/{len(items)}] OK: {name} (id {result.get('id')})")
        else:
            failed.append((name, result))
            print(f"[{i}/{len(items)}] FAILED: {name} -> {result}")

    print(f"\nDone: {len(created)} created, {len(failed)} failed, out of {len(items)} total.")
    if failed:
        print("Failed entries:", file=sys.stderr)
        for name, reason in failed:
            print(f"  - {name}: {reason}", file=sys.stderr)


def cmd_update_task(args, token):
    body = {}
    md = _markdown_arg(args)
    if md is not None:
        body["markdown_content"] = md
    if args.name:
        body["name"] = args.name
    if args.status:
        body["status"] = args.status
    if not body:
        print("ERROR: nothing to update — pass at least one of --markdown/--markdown-file/--name/--status.", file=sys.stderr)
        sys.exit(1)
    ok, result = _request("PUT", f"/task/{args.task_id}", token, body=body)
    if not ok:
        print(f"FAILED: {result}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: updated task {args.task_id}")


def cmd_update_batch(args, token):
    with open(args.file) as f:
        items = json.load(f)
    if not isinstance(items, list):
        print("ERROR: --file must contain a JSON array of task objects.", file=sys.stderr)
        sys.exit(1)

    updated, failed = [], []
    for i, item in enumerate(items, 1):
        task_id = item.get("task_id")
        if not task_id:
            failed.append(("?", "no task_id in entry"))
            print(f"[{i}/{len(items)}] SKIP: entry has no task_id")
            continue
        body = {}
        if "markdown_content" in item:
            body["markdown_content"] = item["markdown_content"]
        if item.get("name"):
            body["name"] = item["name"]
        if item.get("status"):
            body["status"] = item["status"]
        if not body:
            failed.append((task_id, "nothing to update in entry"))
            print(f"[{i}/{len(items)}] SKIP: {task_id} -> no fields to update")
            continue

        ok, result = _request("PUT", f"/task/{task_id}", token, body=body)
        if ok:
            updated.append(task_id)
            print(f"[{i}/{len(items)}] OK: {task_id}")
        else:
            failed.append((task_id, result))
            print(f"[{i}/{len(items)}] FAILED: {task_id} -> {result}")

    print(f"\nDone: {len(updated)} updated, {len(failed)} failed, out of {len(items)} total.")
    if failed:
        print("Failed entries:", file=sys.stderr)
        for task_id, reason in failed:
            print(f"  - {task_id}: {reason}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check-task", help="Verify the API token can reach a specific task.")
    p.add_argument("--task-id", required=True)
    p.set_defaults(func=cmd_check_task)

    p = sub.add_parser("get-task", help="Print a task's id/name/status/description as JSON.")
    p.add_argument("--task-id", required=True)
    p.set_defaults(func=cmd_get_task)

    p = sub.add_parser("list-tasks", help="Print all tasks in a list as a JSON array.")
    p.add_argument("--list-id", required=True)
    p.add_argument("--include-closed", action="store_true")
    p.set_defaults(func=cmd_list_tasks)

    p = sub.add_parser("create-task", help="Create one new task.")
    p.add_argument("--list-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--markdown", default=None, help="Description text (markdown).")
    p.add_argument("--markdown-file", default=None, help="Path to a file with the description text.")
    p.add_argument("--status", default=None)
    p.set_defaults(func=cmd_create_task)

    p = sub.add_parser("create-batch", help="Create many new tasks from a JSON array file.")
    p.add_argument("--list-id", required=True)
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_create_batch)

    p = sub.add_parser("update-task", help="Update one existing task (only passed fields change).")
    p.add_argument("--task-id", required=True)
    p.add_argument("--markdown", default=None)
    p.add_argument("--markdown-file", default=None)
    p.add_argument("--name", default=None)
    p.add_argument("--status", default=None)
    p.set_defaults(func=cmd_update_task)

    p = sub.add_parser("update-batch", help="Update many existing tasks from a JSON array file.")
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_update_batch)

    args = parser.parse_args()
    token = get_token()
    args.func(args, token)


if __name__ == "__main__":
    main()
