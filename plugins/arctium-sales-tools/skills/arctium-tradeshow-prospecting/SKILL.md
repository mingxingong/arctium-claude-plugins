---
name: "arctium-tradeshow-prospecting"
description: "Use whenever the user gives a trade show, conference, or industry event (a URL to an exhibitor/sponsor list, an event guide PDF, or just an event name) and wants Arctium Energy prospects out of it — finding which exhibitors/attendees Arctium could sell BESS/EV charging/DataTrack to or partner with, then turning that into verified contacts with drafted outreach emails logged in ClickUp. Trigger on requests like 'prospect this trade show for Arctium', 'find exhibitors at [event] we should reach out to', 'who at [conference] should we pitch', 'run the tradeshow pipeline on [event]', or a pasted exhibitor prospectus / event guide link with no further instructions. This skill must run in Claude Code (or another environment with open network access), not a network-sandboxed environment — it writes to ClickUp over the REST API directly rather than through the ClickUp MCP server, because the MCP server's call quota (as low as 300 calls/24h) can't handle a full event's worth of tasks."
---

# Arctium trade show prospecting pipeline

This runs the full pipeline end to end, autonomously, with no pause for approval: research the event, shortlist relevant organizations, enrich contacts, draft emails, and log everything in ClickUp. Only stop and ask the user if you hit something you genuinely can't resolve on your own (the event source is unreadable, ClickUp auth fails, etc.) — not for routine judgment calls covered below.

## Before you start

Two things need to be true, check both first:

1. **`CLICKUP_API_TOKEN` is set.** If not, tell the user: get a personal API token from ClickUp (avatar → Settings → Apps → Generate under API Token) and `export CLICKUP_API_TOKEN="pk_..."` in their shell. Don't proceed without it — there's no fallback to the MCP server for this skill (that's the whole reason it exists).
2. **Apollo MCP tools are available** (`apollo_mixed_people_api_search`, `apollo_people_match`). If they're not connected, tell the user and stop — there's no other reliable way to get verified emails.

## Step 1 — Get the event's exhibitor/attendee list

The user may give you a direct URL (a prospectus PDF, an event guide, a sponsors page) or just an event name.

- If given a URL, fetch it. If it's blocked (robots.txt, 403, paywall) or fails, search the web for the event's official site and try its sponsors/exhibitors/partners page, or a speaker list (speaker companies are often exhibitors too even when a full exhibitor list isn't public).
- If given only a name, search for the event's official site first — that's more reliable than aggregator/listing sites.
- Extract every organization name you can find: exhibitors, sponsors, speaker companies, partners. Note the event's dates, location, and theme too — you'll want the theme for framing the "Angle" in Step 2.
- It's fine if the list you can access is partial (e.g. a homepage lists 9 companies but the full exhibitor floor plan is paywalled). Work with what's available and say so plainly in your final summary rather than presenting a partial list as complete.

## Step 2 — Shortlist and categorize

Read `references/arctium-profile.md` for Arctium's business and the category framework, then go through the extracted organization list and sort each one into: skip (not relevant), direct-sale prospect, or channel/ecosystem partner. Write one or two sentences of "Angle" for each org you keep — why it's worth pursuing, grounded in something specific about the org or the event (not generic boilerplate).

Don't cap the shortlist at a round number. Some events yield 5 good prospects, some yield 40 — cover what's genuinely relevant and skip the rest.

## Step 3 — Find a contact and verified email per organization

Read `references/apollo-workflow.md` and follow it. In short: search for a person at the org with a relevant title, then match to get their verified email. If the first candidate has no email on file, try one more candidate at the same org before dropping it. Keep a running list of orgs you had to drop (no contact found, no email available) — this goes in the final summary, not silently discarded.

One good contact per organization is enough.

## Step 4 — Draft the outreach email

Use the `arctium-bess-outreach-emails` skill for the substance and craft of the pitch (structure, length, recipient-based tailoring, incentive framing, CTA sizing). On top of that, these apply to every email this pipeline writes, no exceptions:

- **Short and concise.** Say the minimum that earns a reply. Cut anything that doesn't change the reader's decision to respond.
- **Never salesy.** No superlatives, no "industry-leading," no exclamation points, no hard-sell framing.
- **No em dashes, anywhere.** Use two sentences instead of one joined by a dash.
- **Never lead with price or cost comparisons.** Most C&I recipients are new to battery storage and aren't comparison-shopping yet — the goal of a first email is to start a conversation and educate, not win on price. Leave dollar figures and "cheaper than X" framing out entirely. If a program/incentive has a public source (like BC Hydro's ESI), it's fine to link it, but that's about funding a project, not about Arctium being the low-cost option.

Write a subject line and a full body (greeting through sign-off) for each contact.

## Step 5 — Push everything to ClickUp

Use `scripts/clickup_api.py`, which talks to ClickUp's REST API directly (not MCP). Default target list is `901716073824` (the Business Development & Outreach list) unless the user specifies a different list for this run.

```bash
# 1. sanity check before doing anything else
python3 scripts/clickup_api.py check-list --list-id 901716073824

# 2. build a JSON file, one object per contact (see the script's docstring
#    for the exact shape), then create tasks in one batch:
python3 scripts/clickup_api.py create-batch --list-id 901716073824 \
    --file contacts.json --status "FIRST REACH OUT"
```

`create-batch` automatically fetches existing tasks in the list first and skips any contact whose email is already present — this pipeline gets run repeatedly across different events over time, and you don't want the same person added twice just because two events overlapped on exhibitors. The script prints per-contact success/failure and a final count; don't let one failed task silently stop the batch, and don't retry a failure more than once.

If the list has a different status workflow than "FIRST REACH OUT" (or the user didn't ask for a status at all), omit `--status` and let ClickUp use the list's default.

## Step 6 — Report back

Give the user a plain-language summary: how many organizations were found in the event source, how many were shortlisted, how many contacts were successfully created in ClickUp, how many were skipped as duplicates, and which orgs were dropped and why (no contact found, no email, or judged not relevant). This is the only place a long list is appropriate — don't paste all the draft emails into the chat, they're already in ClickUp.
