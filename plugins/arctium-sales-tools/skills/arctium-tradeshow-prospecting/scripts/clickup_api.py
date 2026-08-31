#!/usr/bin/env python3
"""
Direct ClickUp REST API v2 helper for the arctium-tradeshow-prospecting skill.

Why REST instead of the ClickUp MCP server: ClickUp's MCP server enforces its
own call quota (as low as 300 calls per rolling 24h on paid plans, 50/24h on
Free), completely separate from ClickUp's normal API rate limits. That quota
gets burned fast by a batch job like this one. The REST API here uses
ClickUp's standard per-minute rate limits instead (100+ req/min on most
plans), which comfortably fits a full event's worth of contacts in one run.

Auth: reads a personal API token from the CLICKUP_API_TOKEN environment
variable. Get one from ClickUp: click your avatar -> Settings -> Apps ->
"Generate" under API Token. Never hardcode the token in this file, never log
it, never include it in any task content this script sends to ClickUp.

Usage:
    export CLICKUP_API_TOKEN="pk_..."

    # sanity check you can reach the list before doing anything else
    python3 clickup_api.py check-list --list-id 901716073824

    # get the set of contact emails already in the list, for dedup
    python3 clickup_api.py existing-emails --list-id 901716073824

    # create tasks from a JSON file (array of contact objects, see below)
    python3 clickup_api.py create-batch --list-id 901716073824 \
        --file contacts.json [--status "FIRST REACH OUT"]

contacts.json shape (array of objects), one entry per contact:
    {
        "company": "FortisBC",
        "contact_name": "Jason Wolfe",
        "contact_title": "Director, Energy Solutions (Marketing and Sales)",
        "email": "jason.wolfe@fortisbc.com",
        "linkedin": "http://www.linkedin.com/in/jason-wolfe-a7b90b10",
        "category": "Utility / Energy Program Partner",
        "angle": "One or two sentences on why this org is worth pursuing.",
        "subject": "Battery storage - a conversation, not a pitch",
        "body": "Full email body text. Separate paragraphs with a blank line.
Include the greeting and sign-off - this is inserted verbatim under the
Subject line."
    }
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

API_BASE = "https://api.clickup.com/api/v2"
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def get_token():
    token = os.environ.get("CLICKUP_API_TOKEN")
    if not token:
        print(
            "ERROR: CLICKUP_API_TOKEN environment variable is not set.\n"
            "Get a personal API token from ClickUp (avatar -> Settings -> Apps "
            "-> Generate), then run:\n"
            "  export CLICKUP_API_TOKEN=\"pk_...\"",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def _request(method, path, token, body=None, params=None):
    url = f"{API_BASE}{path}"
    if params:
        query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{query}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:500]
        return False, f"HTTP {e.code}: {detail}"
    except Exception as e:  # noqa: BLE001 - want to surface any failure, not crash the batch
        return False, str(e)


def cmd_check_list(args, token):
    ok, result = _request("GET", f"/list/{args.list_id}", token)
    if not ok:
        print(f"FAILED to reach list {args.list_id}: {result}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: list \"{result.get('name')}\" (id {args.list_id}) is reachable.")


def _fetch_all_tasks(list_id, token):
    tasks = []
    page = 0
    while True:
        ok, result = _request(
            "GET",
            f"/list/{list_id}/task",
            token,
            params={"include_closed": "true", "page": page},
        )
        if not ok:
            print(f"FAILED to list tasks (page {page}): {result}", file=sys.stderr)
            sys.exit(1)
        batch = result.get("tasks", [])
        tasks.extend(batch)
        if result.get("last_page", True) or not batch:
            break
        page += 1
    return tasks


def cmd_existing_emails(args, token):
    tasks = _fetch_all_tasks(args.list_id, token)
    emails = set()
    for t in tasks:
        text = " ".join(
            filter(None, [t.get("name", ""), t.get("text_content", ""), t.get("description", "")])
        )
        emails.update(m.lower() for m in EMAIL_RE.findall(text))
    for e in sorted(emails):
        print(e)
    print(f"# {len(emails)} existing contact email(s) found in list {args.list_id}", file=sys.stderr)


def _build_markdown(c):
    return (
        f"**Company:** {c['company']}\n"
        f"**Contact:** {c['contact_name']} — {c['contact_title']}\n"
        f"**Email:** {c['email']}\n"
        f"**LinkedIn:** {c.get('linkedin', 'n/a')}\n"
        f"**Source:** Apollo.io (verified email)\n"
        f"**Category:** {c['category']}\n\n"
        f"**Angle:** {c['angle']}\n\n"
        f"**Draft Outreach Email**\n\n"
        f"Subject: {c['subject']}\n\n"
        f"{c['body']}"
    )


def cmd_create_batch(args, token):
    with open(args.file) as f:
        contacts = json.load(f)
    if not isinstance(contacts, list):
        print("ERROR: --file must contain a JSON array of contact objects.", file=sys.stderr)
        sys.exit(1)

    ok, _ = _request("GET", f"/list/{args.list_id}", token)
    if not ok:
        print(f"FAILED: can't reach list {args.list_id}, aborting before creating anything.", file=sys.stderr)
        sys.exit(1)

    existing = set()
    for t in _fetch_all_tasks(args.list_id, token):
        text = " ".join(
            filter(None, [t.get("name", ""), t.get("text_content", ""), t.get("description", "")])
        )
        existing.update(m.lower() for m in EMAIL_RE.findall(text))

    created, skipped_dupe, failed = [], [], []
    for i, c in enumerate(contacts, 1):
        email = c.get("email", "").lower().strip()
        if not email:
            failed.append((c.get("company", "?"), "no email provided"))
            continue
        if email in existing:
            skipped_dupe.append((c.get("company", "?"), email))
            print(f"[{i}/{len(contacts)}] SKIP (duplicate): {c.get('company')} <{email}>")
            continue

        name = f"Arctium Outreach: {c['company']} — {c['contact_name']}"
        body = {"name": name, "markdown_content": _build_markdown(c)}
        if args.status:
            body["status"] = args.status

        ok, result = _request("POST", f"/list/{args.list_id}/task", token, body=body)
        if ok:
            created.append(c["company"])
            existing.add(email)  # guard against dupes within the same batch too
            print(f"[{i}/{len(contacts)}] OK: {name}")
        else:
            failed.append((c.get("company", "?"), result))
            print(f"[{i}/{len(contacts)}] FAILED: {name} -> {result}")

        time.sleep(0.3)  # be a good citizen even though the REST limit is generous

    print(
        f"\nDone: {len(created)} created, {len(skipped_dupe)} skipped as duplicates, "
        f"{len(failed)} failed, out of {len(contacts)} total."
    )
    if failed:
        print("Failed entries:", file=sys.stderr)
        for company, reason in failed:
            print(f"  - {company}: {reason}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check-list", help="Verify the API token can reach a list.")
    p.add_argument("--list-id", required=True)
    p.set_defaults(func=cmd_check_list)

    p = sub.add_parser("existing-emails", help="Print contact emails already present in a list (for dedup).")
    p.add_argument("--list-id", required=True)
    p.set_defaults(func=cmd_existing_emails)

    p = sub.add_parser("create-batch", help="Create one task per contact from a JSON file.")
    p.add_argument("--list-id", required=True)
    p.add_argument("--file", required=True, help="Path to a JSON array of contact objects.")
    p.add_argument("--status", default=None, help="Optional status name to set on created tasks.")
    p.set_defaults(func=cmd_create_batch)

    args = parser.parse_args()
    token = get_token()
    args.func(args, token)


if __name__ == "__main__":
    main()
