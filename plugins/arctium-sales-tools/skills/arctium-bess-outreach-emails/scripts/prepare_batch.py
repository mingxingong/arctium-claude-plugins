#!/usr/bin/env python3
"""
Domain-specific formatting step for the arctium-bess-outreach-emails skill's
"working a list of prospect companies" workflow. Turns a companies.json file
(one object per company, each with a list of contacts + their drafted
emails) into the update-batch file shape expected by the shared
`clickup-tasks` skill's scripts/clickup_task.py.

This script does NOT talk to ClickUp at all — no network calls, no auth, no
rate limiting. It just formats. Actually pushing the result to ClickUp is
the clickup-tasks skill's job, run separately afterward:

    python3 <clickup-tasks skill dir>/scripts/clickup_task.py update-batch \
        --file clickup_batch.json

Usage:
    python3 prepare_batch.py --in companies.json --out clickup_batch.json

companies.json shape (array of objects), one entry per company:
    {
        "task_id": "86e2uq2ng",
        "company": "Steveston Harbour Authority",
        "site_notes": "Optional freeform text kept verbatim at the top of
            the task description — e.g. pulled forward from the task's
            existing content (via `clickup_task.py get-task`) so this
            update doesn't clobber notes that live outside the contacts
            list.",
        "contacts": [
            {
                "name": "Jane Doe",
                "title": "General Manager",
                "email": "jane@example.com",
                "linkedin": "https://www.linkedin.com/in/janedoe",
                "source": "Web search - published on example.com staff
                    directory (https://example.com/staff)",
                "subject": "Battery storage at the Fisherman's Ice Plant",
                "body": "Full email body text. Separate paragraphs with a
                    blank line. Include the greeting and sign-off - this is
                    inserted verbatim under the Subject line."
            }
        ]
    }

Field notes:
- "task_id" and "company" are required per company; "site_notes" is optional.
- Every contact needs "name", "title", "subject", and "body". "linkedin" is
  optional.
- "email": leave as "" (not omitted, not fabricated) when Apollo could not
  verify an address for this person. The contact is still included in the
  output — the formatter labels it "EMAIL NOT YET VERIFIED" rather than
  silently dropping the person or the company from the ClickUp record.
- "source": optional override for the one-line attribution shown under the
  contact's email. Defaults to "Apollo.io (verified email)" whenever
  "email" is non-empty and no override is given. Set this explicitly (e.g.
  "Web search - published on [site] ([URL])") when the email came from the
  web-search fallback described in SKILL.md, so the ClickUp record doesn't
  misattribute it to Apollo. Ignored when "email" is empty.

Output shape — a JSON array ready for clickup_task.py update-batch:
    [{"task_id": "86e2uq2ng", "markdown_content": "## Steveston...\n..."}]

One combined update per company (not one task per contact) — every
contact's block is folded into that company's single markdown_content.
"""

import argparse
import json
import sys

DEFAULT_SOURCE = "Apollo.io (verified email)"
UNVERIFIED_LABEL = "EMAIL NOT YET VERIFIED"


def _build_contact_block(i, c):
    email = (c.get("email") or "").strip()
    lines = [f"### {i}. {c['name']} — {c['title']}"]
    if email:
        lines.append(f"**Email:** {email}")
        lines.append(f"**Source:** {c.get('source') or DEFAULT_SOURCE}")
    else:
        lines.append(f"**Email:** {UNVERIFIED_LABEL}")
    if c.get("linkedin"):
        lines.append(f"**LinkedIn:** {c['linkedin']}")
    lines.append("")
    lines.append("**Draft Outreach Email**")
    lines.append("")
    lines.append(f"Subject: {c['subject']}")
    lines.append("")
    lines.append(c["body"])
    return "\n".join(lines)


def _build_company_markdown(company):
    contacts = company.get("contacts") or []
    parts = [f"## {company['company']} — Arctium Outreach Contacts"]
    if company.get("site_notes"):
        parts.append(company["site_notes"].strip())
    blocks = [_build_contact_block(i, c) for i, c in enumerate(contacts, 1)]
    parts.append("\n\n---\n\n".join(blocks))
    return "\n\n".join(p for p in parts if p)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in", dest="infile", required=True, help="Path to companies.json")
    parser.add_argument("--out", dest="outfile", required=True,
                         help="Path to write the clickup-tasks update-batch JSON file")
    args = parser.parse_args()

    with open(args.infile) as f:
        companies = json.load(f)
    if not isinstance(companies, list):
        raise SystemExit("ERROR: --in must contain a JSON array of company objects.")

    out = []
    verified_count, unverified_count = 0, 0
    for company in companies:
        missing = [k for k in ("task_id", "company") if not company.get(k)]
        if missing:
            print(f"SKIP: company entry missing {missing}: {company}", file=sys.stderr)
            continue
        for c in company.get("contacts") or []:
            if (c.get("email") or "").strip():
                verified_count += 1
            else:
                unverified_count += 1
        out.append({
            "task_id": company["task_id"],
            "markdown_content": _build_company_markdown(company),
        })

    with open(args.outfile, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote {len(out)} compan(y/ies) to {args.outfile}")
    print(f"Contacts: {verified_count} with verified email, {unverified_count} unverified")


if __name__ == "__main__":
    main()
