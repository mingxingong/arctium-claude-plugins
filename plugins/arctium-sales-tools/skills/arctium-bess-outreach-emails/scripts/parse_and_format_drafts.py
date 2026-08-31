#!/usr/bin/env python3
"""
"Sending what's already logged" step for the arctium-bess-outreach-emails
skill. Pulls a ClickUp list's tasks (via the shared `clickup-tasks` skill),
parses out the contacts + drafted emails that `prepare_batch.py` logged into
each company task's description, applies Arctium's send-formatting house
style, and writes a drafts.json ready to hand to `outlook_create_draft`.

This script makes exactly one call out, to the clickup-tasks skill's
clickup_task.py (list-tasks) — everything else is local parsing/formatting.

Usage:
    python3 parse_and_format_drafts.py \\
        --list-id 901715151890 \\
        --status "not started" \\
        --admin-task-names "Check contact info for every company in the list" "Follow Up (include overview)" \\
        --clickup-script "<clickup-tasks skill dir>/scripts/clickup_task.py" \\
        --out drafts.json
        [--signature-file signature.html]

Parsing assumptions:
    This expects each company task's text_content to contain the labels
    `prepare_batch.py` writes — "N. Name — Title" headings, "Email:",
    "Source:", "Subject:" — as literal text. ClickUp's API returns
    text_content as a plain-text rendition of the task description, which
    may or may not keep markdown emphasis characters (**, ###) depending on
    how ClickUp renders it; this parser deliberately keys off the label
    words rather than the markdown syntax around them, so it should survive
    that either way. If ClickUp ever changes text_content rendering enough
    to break this, dump one task with:
        python3 <clickup-tasks skill dir>/scripts/clickup_task.py get-task --task-id <id>
    and adjust the regexes below to match what comes back.

Output:
    <out> (default drafts.json) — one record per contact with a verified
    email: {"company", "task_id", "name", "email", "subject", "html_body"}.
    html_body has send-formatting applied: the benefit paragraph and the
    incentive/funding paragraph are bolded, "Energy Storage Incentive" is
    hyperlinked to the BC Hydro ESI page, and the plain-text sign-off is
    replaced with one copy of the real signature block.

    <out>, with .json replaced by .no_contact.json — companies where every
    contact came back with no verified email (task_id + company only).
    Per SKILL.md: confirm with the user before changing anything in
    ClickUp based on this file.
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys

BC_HYDRO_ESI_URL = "https://www.bchydro.com/powersmart/business/programs/large-demand-response/energy-storage-system-incentive.html"
INCENTIVE_LINK_TEXT = "Energy Storage Incentive"

DEFAULT_SIGNATURE_HTML = (
    "<p>Ming Gong<br>"
    "Arctium Energy Company</p>"
)

HEADING_RE = re.compile(r"^[#\s]*\d+\.\s+(?P<name>.+?)\s+[—-]\s+(?P<title>.+?)\s*$", re.MULTILINE)
EMAIL_RE = re.compile(r"Email:\*{0,2}\s*(?P<email>EMAIL NOT YET VERIFIED|\S+)")
SUBJECT_RE = re.compile(r"Subject:\s*(?P<subject>.+)")
TRAILING_DIVIDER_RE = re.compile(r"\n*-{3,}\s*$")


def _load_signature(path):
    if not path:
        print(
            "NOTE: no --signature-file given, using a minimal placeholder signature "
            "(name + company only). Confirm the real signature block with the user "
            "and pass --signature-file next time.",
            file=sys.stderr,
        )
        return DEFAULT_SIGNATURE_HTML
    with open(path) as f:
        return f.read().strip()


def _list_tasks(clickup_script, list_id):
    result = subprocess.run(
        [sys.executable, clickup_script, "list-tasks", "--list-id", list_id],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: clickup_task.py list-tasks failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def _parse_company_task(text):
    """Yield dicts of {name, title, email, subject, body} for each contact
    block found in a company task's text_content."""
    headings = list(HEADING_RE.finditer(text))
    for i, m in enumerate(headings):
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        segment = text[start:end]

        email_m = EMAIL_RE.search(segment)
        email = (email_m.group("email") if email_m else "").strip()
        if "NOT" in email.upper() or "VERIFIED" in email.upper():
            email = ""

        subject_m = SUBJECT_RE.search(segment)
        subject = subject_m.group("subject").strip() if subject_m else ""
        body = segment[subject_m.end():].strip() if subject_m else ""
        body = TRAILING_DIVIDER_RE.sub("", body).strip()

        yield {
            "name": m.group("name").strip(),
            "title": m.group("title").strip(),
            "email": email,
            "subject": subject,
            "body": body,
        }


def _paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _html_escape_paragraph(p):
    return html.escape(p).replace("\n", "<br>")


def _format_html_body(body, signature_html):
    paras = _paragraphs(body)

    incentive_idx = None
    for i, p in enumerate(paras):
        if INCENTIVE_LINK_TEXT.lower() in p.lower() or "bc hydro" in p.lower():
            incentive_idx = i
            break
    if incentive_idx is None:
        print("WARNING: no incentive/BC Hydro paragraph found — nothing bolded or linked for this email.", file=sys.stderr)

    signoff_idx = None
    for i, p in enumerate(paras):
        if "arctium energy" in p.lower() and re.search(r"\bming gong\b", p, re.IGNORECASE):
            signoff_idx = i
            break

    html_parts = []
    for i, p in enumerate(paras):
        if signoff_idx is not None and i == signoff_idx:
            html_parts.append(signature_html)
            continue

        escaped = _html_escape_paragraph(p)
        is_benefit = incentive_idx is not None and i == incentive_idx - 1
        is_incentive = i == incentive_idx

        if is_incentive:
            linked = re.sub(
                re.escape(INCENTIVE_LINK_TEXT),
                f'<a href="{BC_HYDRO_ESI_URL}">{INCENTIVE_LINK_TEXT}</a>',
                escaped,
                flags=re.IGNORECASE,
            )
            html_parts.append(f"<p><strong>{linked}</strong></p>")
        elif is_benefit:
            html_parts.append(f"<p><strong>{escaped}</strong></p>")
        else:
            html_parts.append(f"<p>{escaped}</p>")

    if signoff_idx is None:
        html_parts.append(signature_html)

    return "\n".join(html_parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list-id", required=True)
    parser.add_argument("--status", default=None, help="Only process tasks with this status (case-insensitive). Omit to process every task.")
    parser.add_argument("--admin-task-names", nargs="*", default=[], help="Task names to skip (non-company checklist items in the same list).")
    parser.add_argument("--clickup-script", required=True, help="Path to the clickup-tasks skill's scripts/clickup_task.py")
    parser.add_argument("--out", default="drafts.json")
    parser.add_argument("--signature-file", default=None, help="Path to an HTML file with the real Arctium signature block.")
    args = parser.parse_args()

    signature_html = _load_signature(args.signature_file)
    tasks = _list_tasks(args.clickup_script, args.list_id)

    admin_names = {n.strip().lower() for n in args.admin_task_names}
    status_filter = args.status.strip().lower() if args.status else None

    drafts, no_contact = [], []
    for task in tasks:
        name = (task.get("name") or "").strip()
        if name.lower() in admin_names:
            continue
        status = (task.get("status") or "").strip().lower()
        if status_filter is not None and status != status_filter:
            continue

        contacts = list(_parse_company_task(task.get("text_content") or ""))
        verified = [c for c in contacts if c["email"]]

        if not verified:
            no_contact.append({"task_id": task.get("id"), "company": name})
            continue

        for c in verified:
            drafts.append({
                "company": name,
                "task_id": task.get("id"),
                "name": c["name"],
                "email": c["email"],
                "subject": c["subject"],
                "html_body": _format_html_body(c["body"], signature_html),
            })

    with open(args.out, "w") as f:
        json.dump(drafts, f, indent=2)

    no_contact_path = re.sub(r"\.json$", ".no_contact.json", args.out) if args.out.endswith(".json") else args.out + ".no_contact.json"
    with open(no_contact_path, "w") as f:
        json.dump(no_contact, f, indent=2)

    print(f"Wrote {len(drafts)} draft(s) to {args.out}")
    print(f"Wrote {len(no_contact)} no-contact compan(y/ies) to {no_contact_path}")


if __name__ == "__main__":
    main()
