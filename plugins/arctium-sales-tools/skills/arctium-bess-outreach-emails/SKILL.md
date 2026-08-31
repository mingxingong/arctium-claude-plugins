---
name: "arctium-bess-outreach-emails"
description: "Use when drafting cold outreach or pitch emails for Arctium Energy's battery energy storage (BESS) offering — peak shaving, demand response, resilience, or BC Hydro ESI incentive pitches to prospective commercial/industrial customers. Also covers the full workflow for a list of prospect companies (e.g. an existing ClickUp list): finding at least 6 relevant contacts per company via Apollo, drafting a tailored email for each, and logging everything into the company's ClickUp task description via the shared `clickup-tasks` skill (never the ClickUp connector directly). Also use this whenever the user wants already-logged ClickUp draft emails turned into actual Outlook drafts — e.g. 'draft these in Outlook', 'push the not-started companies' emails out' — which applies Arctium's send-formatting (bolding, the BC Hydro incentive hyperlink, signature) and falls back to a copy-paste-ready page if Outlook draft creation is blocked."
---

## Arctium BESS outreach email guidelines

These are learned from comparing hand-drafted outreach emails against AI-drafted versions for the same prospect (Steveston Harbour Authority ice plant), refined through several rounds of review. Apply these when writing cold outreach or pitch emails selling Arctium's battery energy storage (BESS) systems.

### Company name
- Use the full name "Arctium Energy Company" when introducing the company in the opening line (e.g. "I'm Ming with Arctium Energy Company."). Confirm with the user whether the sign-off should also use the full name or the shorthand "Arctium Energy" if unclear.

### Sentence structure and tone
- Prefer standalone sentences over em-dash-joined independent clauses. E.g. write "I'm Ming with Arctium Energy Company. We design and install battery energy storage systems (BESS)..." as two sentences, not one joined with an em dash. This applies throughout the email, including trailing clauses like "Happy to go into specifics..." — give those their own sentence rather than tacking them on after a dash.
- This produces a more measured, conventional business tone versus a breezier em-dash-heavy style.

### Structure and length
- Aim for ~5 tight paragraphs: hook/intro, site-specific observation, benefit(s), incentive/funding hook, CTA.
- Do not break benefits into three separately bolded/labeled sub-sections (e.g. "Peak shaving:", "Demand response revenue:", "Resilience:") by default — this reads as listy and sales-deck-like. Fold benefits into flowing prose in one or two sentences unless the recipient is technical and would want an itemized breakdown.
- Prefer concise over comprehensive. It's fine to leave out a minor benefit (e.g. demand response revenue as a separate line item) if including it makes the email longer without changing the reader's decision.

### Citations and links
- When citing a specific program, incentive, or claim that has a public page (e.g. BC Hydro's Energy Storage Incentive), include the actual hyperlink inline, not just a prose description. A working link adds credibility and lets the reader verify the claim themselves. Never describe a specific numbered claim (e.g. "80% incentive") without linking to the source if a source URL is available.
- BC Hydro ESI program URL: https://www.bchydro.com/powersmart/business/programs/large-demand-response/energy-storage-system-incentive.html

### Site-specific detail
- Reference concrete facts about the prospect's site (equipment models, capacity figures, production volumes) to show the outreach is researched, not templated.
- Avoid redundant or awkward phrasing when naming the company/site — e.g. don't write "Steveston Harbor's Steveston Fisherman's Ice Plant" (repeats the location name). Say "the Fisherman's Ice Plant" once contextualized.

### Incentive framing
- Do NOT include the "non-repayable / not a loan" clause in initial/first-touch outreach emails. This was tried and explicitly walked back by the user — drop it from cold emails entirely. (It's fine to explain this verbally on an intro call if it comes up, just not in the first written outreach.)
- Do NOT claim in initial outreach that "Arctium has secured additional funding for select projects that can cover most or all of the remaining cost" — also removed from first-touch emails per the same feedback.
- State the incentive plainly instead: e.g. "BC Hydro's Energy Storage Incentive covers up to 80% of eligible project costs" with the hyperlink, and stop there — no repayability framing, no secondary-funding claim, in the initial email.
- A light urgency note (e.g. "while the program is active") is optional and should only be added if it's factually true and doesn't feel forced.

### Recipient-based tailoring
Tailor emphasis by the recipient's role at the prospect company:
- General Manager / decision-maker: lead with resilience and strategic framing (keeping operations running, mission-critical framing).
- Controller / Finance: lead with capex reduction and ROI — the incentive percentage should be earlier in the email, not buried at the end (but still without the "non-repayable" clause — see Incentive framing above).
- Maintenance / Electrician / technical contact: it's fine to explain that you're reaching out to them specifically because they'd own the electrical side of a project like this — but do NOT itemize detailed technical questions (panel/switchgear configuration, available space, shared vs. dedicated service, etc.) in the cold email itself. That's presumptuous before they've even agreed to talk. Keep the first email at the same "here's the pitch, here's the incentive" level as other recipients, and save the specific technical questions for the intro call — you can mention in the CTA that the call will cover a general sense of their electrical setup, without listing the specifics upfront.

### Closing / CTA sizing
- Keep the first-touch ask small: a short intro call is the right size for a first email. Do not ask for a site walk-through, a detailed technical questionnaire, or anything bigger as the initial ask, even with a technical contact — those are natural follow-ups once there's mutual interest, not the opening request.
- Give a time range rather than a fixed number, e.g. "15-20 minutes" rather than "15 minutes" — reads as more natural and accommodating while still keeping the ask small.
- End with a low-friction CTA, explicitly offering to work around the recipient's schedule. Keep this consistent across variants sent to the same company/deal so multiple recipients see a coherent story if they compare notes.

### General
- Sign consistently: name, then company (e.g. "Ming Gong / Arctium Energy Company").
- Proofread for repeated words/phrases introduced by combining templated and site-specific text.

## ClickUp access: always go through the clickup-tasks skill

Every ClickUp read or write anywhere in this workflow — pulling a list's tasks, reading a task's current description before overwriting it, updating tasks in bulk — must go through the `clickup-tasks` skill's `scripts/clickup_task.py`, never the ClickUp MCP connector's tools (functions named like `clickup_create_task`, `clickup_get_task`, `clickup_update_task`, `clickup_filter_tasks`, etc.), even if those connector tools are sitting right there in your tool list and calling one directly feels faster in the moment.

The reason is concrete, not stylistic: `clickup-tasks` enforces a shared rate limiter (50 calls/60s) across every concurrent caller on the machine — other agents, other skills, scheduled runs — so the combined traffic stays under ClickUp's real API limit. The MCP connector has no visibility into that shared budget and its own call quota can be as low as 300 calls/24h, which a batch of even a few dozen companies can blow through on its own. Mixing the two paths means neither one actually knows the true call volume, so bypass the connector entirely for this skill's ClickUp work and route everything through `clickup-tasks` as described below.

## Working a list of prospect companies

This applies whenever the task is to run outreach against a list of companies rather than a single one-off email — most commonly an existing ClickUp list of prospects (e.g. a list like "HVAC Heavy C&I Sites"), but the same approach applies to any batch of company names supplied by the user.

### Find at least 6 relevant contacts per company

Don't stop at one contact per company. For each prospect, use Apollo (`apollo_mixed_people_api_search` then `apollo_people_match`, the same two-step pattern as `arctium-tradeshow-prospecting`'s `apollo-workflow.md`) to find **a minimum of 6 people with verified emails**, spread across roles that would plausibly touch a BESS decision:

- Facilities Manager / Director of Facilities
- Energy Manager / Sustainability Manager
- Maintenance Manager / Chief Engineer / Plant Manager
- Director of Operations / VP Operations / Senior Operations Manager
- General Manager / President / COO (decision-maker)
- Controller / Finance / VP Finance (budget holder)

Adjust the exact title mix to what actually exists at the company (a 10-person shop won't have all six; lean on whichever senior/technical roles are present) but keep pushing past the first hit — search multiple title buckets, not just one, before considering a company covered. If a company has fewer than 6 people in Apollo's database entirely, get everyone plausible and note the shortfall rather than treating it as a failure.

Only drop a company entirely (no task update) if Apollo has no people at all for it after broadening the search (try the parent/DBA name, drop location filters, try without title filters).

### Fallback: web search for a specific person's email when Apollo can't verify it

This is a **fallback only** — never a substitute for Apollo, and never a blind "who works here" search. Apollo remains the primary and default method for finding people and emails; only reach for this when Apollo has already given you a specific person's **name and title** but `apollo_people_match` came back `unavailable` or Apollo is out of credits/rate-limited. At that point, a targeted web search for that one named person (`"[Full Name]" "[Company]" email`, or checking the company's own staff/leadership/contact page for their name) can sometimes recover a real address for free — a backtest across 43 such Apollo gaps recovered 8 (~19%), but the hit rate is sharply source-dependent, not general:

- **Worth trying:** government/municipal bodies (staff directories are usually public by design), and small brokerages/advisory/real-estate firms where individual visibility is part of the business model (some publish a bio page with a direct email per person).
- **Not worth trying:** ordinary private companies — manufacturers, food processors, retailers, warehouses. In the same backtest, this was **0 for 34** across six such companies; every lead dead-ended at a masked/paywalled preview on a data-broker site (ZoomInfo, RocketReach, SignalHire, LeadIQ, ContactOut, etc.). Don't burn time running this fallback broadly across a private-company-heavy list — it reliably won't pay off outside the two categories above.

Same verification bar as everywhere else in this workflow: only count an email if it's explicitly published somewhere with a source URL (company site, press release, news article, staff directory, conference bio, a public LinkedIn "Contact info" section). Never guess or pattern-infer an address (e.g. constructing `firstname.lastname@company.com` from a known format), and never treat a masked/paywalled data-broker listing (`j***@company.com`) as a find — those are the same category of tool as Apollo, just previewable without paying, and "found" here means genuinely public, not "technically discoverable behind a paywall."

If this fallback recovers an email, set that contact's optional `"source"` field in the JSON (see `scripts/prepare_batch.py`'s docstring) to something like `"Web search - published on [site] ([URL])"` so the ClickUp record accurately shows it didn't come from Apollo, instead of leaving it to default to the Apollo-branded label.

### Draft one tailored email per contact

Write a full subject + body for each of the 6+ contacts, not one generic email copy-pasted across recipients. Apply the recipient-based tailoring guidance above (GM leads with resilience, Finance leads with capex/ROI, technical contacts get the "reaching out to you directly" framing) so each contact gets an email that actually fits their role — this is the point of gathering more than one contact per company.

### Log everything to the company's ClickUp task

For each company, all of its contacts and their drafted emails go into **one combined update to that company's existing ClickUp task description** — do not create separate tasks per contact. This is a two-step handoff between two skills:

1. **This skill formats the content.** Build a `companies.json` file (one object per company, with a `contacts` array — see `scripts/prepare_batch.py`'s docstring for the exact shape, including the optional `source` override for fallback-recovered emails), then run:
   ```bash
   python3 scripts/prepare_batch.py --in companies.json --out clickup_batch.json
   ```
   This produces the file shape the `clickup-tasks` skill expects (`[{"task_id": "...", "markdown_content": "..."}]`) — no network calls, no auth, just formatting. Contacts without a verified email still get included — leave `"email": ""` rather than fabricating one or dropping the contact; the formatter labels these "EMAIL NOT YET VERIFIED" so the ClickUp record never claims a verification that never happened.

2. **The `clickup-tasks` skill does the actual ClickUp API traffic — this is the only path in, never the ClickUp connector.** Load it (`Skill` tool, name `clickup-tasks`) to get its base directory, then run:
   ```bash
   python3 <clickup-tasks skill dir>/scripts/clickup_task.py update-batch --file clickup_batch.json
   # or, to read a task's current content first (e.g. to pull forward site_notes
   # before overwriting it): clickup_task.py get-task --task-id <id>
   ```
   That skill handles auth (macOS Keychain, no prompting) and the shared rate limiter (50 calls/60s, shared across every concurrent caller on the machine — including other agents running this same workflow in parallel) — see its own `SKILL.md` for details. This skill has no ClickUp-auth or rate-limiting logic of its own; don't reinvent either here. Don't call ClickUp's REST API directly with `curl`, and don't reach for the ClickUp MCP connector's tools either — both bypass the shared rate-limit budget that `clickup-tasks` is there to enforce.

Neither step touches task status — leave whatever status the list already has (e.g. "not started") unless the user asks otherwise. `clickup_task.py update-batch` prints per-company success/failure and doesn't let one failure stop the batch.

## Sending what's already logged: pushing drafts to Outlook

Once a ClickUp list has contacts + draft emails logged in each company's task description (the workflow above), the next step is turning those into real Outlook drafts. This is a distinct pass — it doesn't touch Apollo or re-research anything — and it's the one to reach for when the user says things like "draft these in Outlook", "send the drafts for the not-started companies", or "push the logged emails out."

### 1. Parse + apply send-formatting

Run the bundled script (it pulls the list via the `clickup-tasks` skill itself, so load that skill first to get its base directory):

```bash
python3 scripts/parse_and_format_drafts.py \
    --list-id <clickup list id> \
    --status "not started" \
    --admin-task-names "Check contact info for every company in the list" "Follow Up (include overview)" \
    --clickup-script "<clickup-tasks skill dir>/scripts/clickup_task.py" \
    --out drafts.json
```

`--admin-task-names` skips any non-company checklist items that live in the same list (every list tends to have a couple — check the task names first if unsure). The script writes two files:

- `drafts.json` — one record per contact with a verified email (`company`, `task_id`, `name`, `email`, `subject`, `html_body`), with Arctium's send-formatting house style already applied: the benefit paragraph and the incentive paragraph are bolded, "Energy Storage Incentive" is hyperlinked to the BC Hydro ESI page, and the plain-text "Ming Gong / Arctium Energy Company" sign-off is replaced with one copy of the real signature block (Outlook drafts created via Microsoft Graph don't inherit the mailbox's signature automatically — it has to be in the body, exactly once).
- `drafts.no_contact.json` — companies where every contact came back with an unverified email only. **Confirm with the user before changing anything in ClickUp based on this file** — whether that means marking those tasks "no contact found" via `clickup_task.py update-batch` or leaving them alone depends on what they want that status to mean in this particular list.

### 2. Create the Outlook drafts

Loop over `drafts.json` and call `outlook_create_draft` once per record: `to=[record.email]`, `cc` = the internal team that should see every outreach email as it goes out (confirm this list with the user the first time — don't assume — then reuse it), `subject=record.subject`, `bodyType="html"`, `body=record.html_body`. Batch a handful of calls per turn rather than one at a time.

### 3. If `outlook_create_draft` fails

A `FORBIDDEN` / `Mail.ReadWrite` error means the mail connector's app registration hasn't been admin-consented for write access in the org's Entra tenant — this is an admin action outside the agent's reach, and retrying will not help. Don't loop on it. Tell the user plainly what's blocked and why, then fall back to a deliverable they can act on by hand:

```bash
python3 scripts/build_copy_paste_artifact.py \
    --records drafts.json \
    --no-contact drafts.no_contact.json \
    --out outreach_drafts.html \
    --title "<short page title>" \
    --subtitle "<e.g. the ClickUp list name>" \
    --cc <cc address 1> <cc address 2>
```

Publish the resulting HTML with the Artifact tool (or send the file directly). It renders every contact as a card with click-to-copy To/Cc/Subject fields and a "Copy body" button that copies the formatted HTML to the clipboard — pasting into an Outlook compose window preserves the bold text and the hyperlink, so the user isn't stuck manually re-formatting 100+ emails by hand.

