#!/usr/bin/env python3
"""
Fallback deliverable for the arctium-bess-outreach-emails skill's "sending
what's already logged" step, used when `outlook_create_draft` is blocked
(typically a FORBIDDEN / Mail.ReadWrite error from an unconsented app
registration — see SKILL.md). Turns drafts.json (and optionally
drafts.no_contact.json) from parse_and_format_drafts.py into one
self-contained HTML page: a card per contact with click-to-copy To/Cc/
Subject fields and a "Copy body" button that copies the formatted body as
HTML, so pasting into an Outlook compose window keeps the bold text and the
hyperlink intact instead of the user having to hand-reformat every email.

No network calls, no ClickUp/Outlook API access — this only reads local
JSON files and writes one local HTML file.

Usage:
    python3 build_copy_paste_artifact.py \\
        --records drafts.json \\
        --no-contact drafts.no_contact.json \\
        --out outreach_drafts.html \\
        --title "Arctium Outreach Drafts" \\
        --subtitle "HVAC Heavy C&I Sites" \\
        --cc ming@arctiumenergy.com sales@arctiumenergy.com

--no-contact is optional — omit it to skip that section entirely.
--cc accepts zero or more addresses; they're shown as a comma-joined Cc
field on every card.

The output is a complete standalone HTML document (its own <!DOCTYPE>,
<html>, <head>, <body>) meant to be opened directly or sent as a file. If
publishing it through the Artifact tool instead, strip the outer
doctype/html/head/body wrapper first, since that tool supplies its own.
"""

import argparse
import html
import json


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{
    --bg: #f7f7f5; --card-bg: #ffffff; --text: #1a1a1a; --muted: #6b6b6b;
    --border: #e3e3e0; --accent: #2e6b4f; --accent-fg: #ffffff;
    --field-bg: #f0f0ee;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #17181a; --card-bg: #202124; --text: #ececec; --muted: #9a9a9a;
      --border: #35363a; --accent: #5fae8a; --accent-fg: #0c120f;
      --field-bg: #2a2b2e;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 2rem 1.25rem 4rem; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }}
  .wrap {{ max-width: 760px; margin: 0 auto; }}
  h1 {{ font-size: 1.4rem; margin: 0 0 0.15rem; }}
  .subtitle {{ color: var(--muted); margin: 0 0 1.75rem; font-size: 0.95rem; }}
  .card {{
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px;
    padding: 1.1rem 1.25rem; margin-bottom: 1rem;
  }}
  .card h2 {{ font-size: 1.05rem; margin: 0 0 0.15rem; }}
  .card .company {{ color: var(--muted); font-size: 0.85rem; margin: 0 0 0.8rem; }}
  .field-row {{ display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.4rem; }}
  .field-label {{ width: 3.5rem; flex: none; color: var(--muted); font-size: 0.8rem; }}
  .field-value {{
    flex: 1; background: var(--field-bg); border-radius: 6px; padding: 0.35rem 0.6rem;
    font-size: 0.85rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    cursor: pointer; overflow-wrap: anywhere; user-select: all;
  }}
  .copy-btn {{
    border: none; border-radius: 6px; padding: 0.35rem 0.7rem; font-size: 0.78rem;
    cursor: pointer; background: var(--field-bg); color: var(--text); flex: none;
  }}
  .copy-body-btn {{
    margin-top: 0.6rem; border: none; border-radius: 6px; padding: 0.5rem 0.9rem;
    font-size: 0.85rem; cursor: pointer; background: var(--accent); color: var(--accent-fg);
    font-weight: 600;
  }}
  .body-preview {{
    margin-top: 0.7rem; border-top: 1px dashed var(--border); padding-top: 0.7rem;
    font-size: 0.88rem; line-height: 1.5;
  }}
  .no-contact {{ color: var(--muted); font-size: 0.9rem; }}
  .no-contact ul {{ padding-left: 1.2rem; }}
  .status {{ font-size: 0.75rem; color: var(--accent); margin-left: 0.3rem; opacity: 0; transition: opacity 0.15s; }}
  .status.show {{ opacity: 1; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{title}</h1>
  <p class="subtitle">{subtitle}</p>
  {cards}
  {no_contact_section}
</div>
<script>
function copyText(el, value) {{
  navigator.clipboard.writeText(value);
  flash(el);
}}
function flash(el) {{
  var status = el.parentElement.querySelector('.status');
  if (status) {{
    status.classList.add('show');
    setTimeout(function() {{ status.classList.remove('show'); }}, 1200);
  }}
}}
function copyBody(btn, id) {{
  var node = document.getElementById(id);
  var html = node.innerHTML;
  var text = node.innerText;
  try {{
    var item = new ClipboardItem({{
      'text/html': new Blob([html], {{type: 'text/html'}}),
      'text/plain': new Blob([text], {{type: 'text/plain'}})
    }});
    navigator.clipboard.write([item]).then(function() {{ flash(btn); }});
  }} catch (e) {{
    navigator.clipboard.writeText(text);
    flash(btn);
  }}
}}
</script>
</body>
</html>
"""

CARD_TEMPLATE = """
  <div class="card">
    <h2>{name}</h2>
    <p class="company">{company}</p>
    <div class="field-row">
      <span class="field-label">To</span>
      <span class="field-value" onclick="copyText(this, {to_js})">{to_html}</span>
      <span class="status">Copied</span>
    </div>
    <div class="field-row">
      <span class="field-label">Cc</span>
      <span class="field-value" onclick="copyText(this, {cc_js})">{cc_html}</span>
      <span class="status">Copied</span>
    </div>
    <div class="field-row">
      <span class="field-label">Subject</span>
      <span class="field-value" onclick="copyText(this, {subject_js})">{subject_html}</span>
      <span class="status">Copied</span>
    </div>
    <button class="copy-body-btn" onclick="copyBody(this, '{body_id}')">Copy body</button>
    <span class="status">Copied</span>
    <div class="body-preview" id="{body_id}">{html_body}</div>
  </div>
"""


def _js_string(s):
    # json.dumps() wraps the value in double quotes (and leaves any literal
    # apostrophe in the string untouched). It's then embedded inside an
    # onclick="..." HTML attribute that is itself double-quoted, so without
    # escaping, either character collides with the attribute delimiter and
    # truncates it — breaking the click-to-copy handler and, with an
    # apostrophe present (e.g. a subject like "the Fisherman's Ice Plant"),
    # corrupting the surrounding markup. HTML-escaping the JSON string before
    # inserting it keeps the attribute well-formed; the browser decodes the
    # entities back to the correct JS string literal at parse time.
    return html.escape(json.dumps(s), quote=True)


def _build_card(i, record, cc_display):
    return CARD_TEMPLATE.format(
        name=html.escape(record.get("name", "")),
        company=html.escape(record.get("company", "")),
        to_js=_js_string(record.get("email", "")),
        to_html=html.escape(record.get("email", "")),
        cc_js=_js_string(cc_display),
        cc_html=html.escape(cc_display) if cc_display else "<em>none</em>",
        subject_js=_js_string(record.get("subject", "")),
        subject_html=html.escape(record.get("subject", "")),
        body_id=f"body-{i}",
        html_body=record.get("html_body", ""),
    )


def _build_no_contact_section(no_contact):
    if not no_contact:
        return ""
    items = "\n".join(
        f"<li>{html.escape(c.get('company', '?'))} (task {html.escape(str(c.get('task_id', '')))})</li>"
        for c in no_contact
    )
    return (
        '<div class="card no-contact"><h2>No verified contact</h2>'
        f"<ul>{items}</ul></div>"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--records", required=True, help="Path to drafts.json from parse_and_format_drafts.py")
    parser.add_argument("--no-contact", default=None, help="Path to drafts.no_contact.json (optional)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--title", default="Outreach Drafts")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--cc", nargs="*", default=[])
    args = parser.parse_args()

    with open(args.records) as f:
        records = json.load(f)

    no_contact = []
    if args.no_contact:
        try:
            with open(args.no_contact) as f:
                no_contact = json.load(f)
        except FileNotFoundError:
            pass

    cc_display = ", ".join(args.cc)
    cards = "\n".join(_build_card(i, r, cc_display) for i, r in enumerate(records))
    no_contact_section = _build_no_contact_section(no_contact)

    page = PAGE_TEMPLATE.format(
        title=html.escape(args.title),
        subtitle=html.escape(args.subtitle),
        cards=cards,
        no_contact_section=no_contact_section,
    )

    with open(args.out, "w") as f:
        f.write(page)

    print(f"Wrote {len(records)} card(s) and {len(no_contact)} no-contact entr(y/ies) to {args.out}")


if __name__ == "__main__":
    main()
