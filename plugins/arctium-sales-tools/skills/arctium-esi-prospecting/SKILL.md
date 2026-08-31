---
name: "arctium-esi-prospecting"
description: "Use whenever the user gives a business name or a Google Maps link (including short links like maps.app.goo.gl/...) and wants it prospected for Arctium Energy's BC Hydro Energy Storage Incentive (ESI) / BESS outreach. Trigger on things like \"add this location to the ESI list\", \"prospect this business for BC Hydro ESI\", or a bare Google Maps link in an Arctium prospecting context. Adds the business to Arctium's \"HVAC Heavy C&I Sites\" ClickUp list, researches the site, finds candidate contacts via Apollo, drafts tailored outreach for every candidate and logs it to ClickUp immediately using names/titles only (no verified emails yet), THEN pauses to confirm before spending Apollo credits to reveal emails, and finally updates the logged drafts with the revealed addresses. Reads/writes ClickUp only through the shared `clickup-tasks` skill, never the ClickUp connector directly, except as an explicit last resort if `clickup-tasks` is unavailable in the environment."
---

## Arctium ESI single-site prospecting

Turns one business — given as a name or a Google Maps link (including short links like `maps.app.goo.gl/...`) — into a fully-worked BC Hydro Energy Storage Incentive (ESI) prospect: a ClickUp task with researched site notes, candidate contacts, and drafted outreach for every one of them, with verified emails added once the user gives the go-ahead to spend Apollo credits.

This is the single-site counterpart to the `arctium-bess-outreach-emails` skill's "working a list of prospect companies" workflow. Use that skill's house style (tone, structure, recipient-based tailoring, incentive framing, CTA sizing) and its `prepare_batch.py` formatting logic rather than reinventing them here. This skill's contact-finding and ClickUp-write steps below intentionally diverge from that shared skill's default ordering — see "Why draft before enrich" — so follow the step order in *this* file for a single site, not the order implied by `arctium-bess-outreach-emails`'s own "working a list" section.

**Default target list:** Arctium's "HVAC Heavy C&I Sites" ClickUp list — `https://app.clickup.com/9017999415/v/l/6-901715151890-1`, list ID `901715151890`. Use this list unless the user names a different one.

**Every ClickUp interaction in this workflow — listing a list's tasks, reading a task, creating a task, updating a task — goes through the `clickup-tasks` skill, never the ClickUp connector.** That skill exists precisely so all of Arctium's ClickUp traffic (this skill, `arctium-bess-outreach-emails`, `arctium-tradeshow-prospecting`, anything scheduled) shares one rate-limited path instead of each caller hitting the API or the connector's low call quota independently. Reach for the ClickUp connector only if `clickup-tasks` itself is unavailable in the environment (e.g. its macOS Keychain-based auth has nothing to read from in a Linux sandbox and no `CLICKUP_API_TOKEN` override was set), and say so explicitly if that happens rather than silently switching tools.

### Why draft before enrich

Drafting the outreach email only takes a candidate's first name, title, and the site research — none of that requires a verified email address. Apollo's people-search step (`apollo_mixed_people_api_search`) already returns first names openly; only last names and email addresses are masked/withheld until enrichment (`apollo_people_match`), which is the step that spends credits. So there's no reason to gate drafting on enrichment, and doing it the other way around (enrich first, draft second) means a "no, don't spend credits" answer from the user throws away work that didn't need to touch Apollo credits at all.

The order in this skill is therefore: research the site, find candidates, **draft and log outreach for every candidate immediately**, and only *then* ask whether to spend Apollo credits revealing their emails. A "no" at that checkpoint still leaves the user with a complete, reviewable set of drafted emails per named candidate — just without verified addresses to send them to yet.

### 1. Resolve the input to a business identity

If given a Google Maps link, fetch it (`web_fetch` follows the redirect for short links) and read the resolved URL — it typically has the shape `.../maps/place/<Business+Name>/@<lat>,<lng>,...`. Extract the business name and coordinates from there. Cross-check with a web search to confirm the name, address, and what the business actually is (site listings, the business's own site, directories).

If given just a name, web search to find the address and confirm you have the right business — company names collide, so if the search turns up multiple plausible matches (e.g. multiple locations, or a same-named company in an unrelated industry/city), ask the user which one before going further rather than guessing.

### 2. Check for an existing ClickUp task first

List the target list's tasks with `clickup-tasks`' `list-tasks` command and check for a task already named after this company, allowing for minor naming variation. If one exists, **use that task** rather than creating a duplicate — pick up whatever site notes or contacts are already there (via `get-task`) and continue the workflow on it. Only create a new task when there's genuinely nothing for this company yet.

### 3. Research the site

Before drafting anything, spend a bit of web search effort finding facility-specific details: what the site does, approximate square footage, anything indicating a heavy or continuous electrical load (refrigeration, HVAC, process equipment, temperature control, dock/loading activity, shift patterns), industry, and anything else concrete. This is what makes outreach read as researched rather than templated — see `arctium-bess-outreach-emails`'s "Site-specific detail" guidance. Write these into a `site_notes` paragraph, e.g.:

> Refrigerated cross-dock facility — 13,200 sq ft refrigerated space within a 42,000 sq ft warehouse, dock held at a constant 2°C, 8 loading doors. Cold-chain logistics/3PL operator. Strong BESS fit given continuous refrigeration load.

If a genuine search doesn't turn up anything beyond name and address, say so plainly in the notes rather than inventing specifics — a thin-but-honest note beats a fabricated one. Also note plainly if the resolved place turns out to be a multi-tenant property (a shopping centre, an industrial park) rather than a single operating business — that changes who outreach should target (the property manager/owner, not a single on-site company) and is worth flagging to the user.

### 4. Create or update the ClickUp task with site notes

Write the task description with `clickup-tasks`: `create-task` (new company) or `update-task` (existing task found in step 2), against the list/task ID from step 2:

```
**Site:** <address> (Google Maps: [<link>](<link>))

**Site notes:** <the paragraph from step 3>

_Contacts and draft outreach to follow._
```

Leave the task's status alone (don't set it to anything other than the list's default) unless the user asks otherwise.

### 5. Find candidate contacts via Apollo — no email reveal yet

Use `apollo_mixed_people_api_search` filtered to the company's domain, with `person_titles` covering the roles that would plausibly touch a BESS decision (General Manager/President/COO, Controller/Finance, Facilities/Maintenance/Chief Engineer, Operations/Plant Manager, Energy/Sustainability Manager). This step does not require email reveal or enrichment and does not need a credit-spend confirmation — it just surfaces who exists. First names come back openly; last names may be partially masked (e.g. "Ka***k") until enrichment — that's fine for what comes next.

If the narrow title search comes back thin (fewer than ~6 people), broaden it the same way `arctium-bess-outreach-emails` does for a company that doesn't have a dedicated facilities function: drop the title filter and search the whole roster by domain, then hand-pick the most BESS-relevant people from whatever roles actually exist (a small trucking or logistics company might have a Terminal Manager or Fleet Manager instead of a Facilities Manager, for instance — that's a fine substitute). Aim for 6, but don't force it if the company genuinely doesn't have that many plausible people in Apollo's data.

If Apollo has no one at all for this company even after broadening, say so and stop the contact-finding part of the workflow — leave the site-info task in place rather than blocking on it.

### 6. Draft outreach for every candidate and log it to ClickUp — before spending any Apollo credits

For each candidate found in step 5, write a full subject + body email using `arctium-bess-outreach-emails`'s house style: standalone sentences, no em dashes, ~5 tight paragraphs (hook/intro, site-specific observation, benefit(s), incentive/funding hook, CTA), the BC Hydro ESI link inline, no "non-repayable" framing in first-touch outreach, recipient-based tailoring by role (GM leads with resilience, Finance/Controller leads with capex/ROI, technical/facilities contacts get the "reaching out to you directly" framing), and a 15-20 minute CTA that offers to work around their schedule. Address the recipient by their first name — that's all that's needed and all that's reliably available pre-enrichment.

Build a `companies.json` for this one company (shape documented in `arctium-bess-outreach-emails`'s `scripts/prepare_batch.py` docstring) with the `site_notes` from step 3 and one entry per candidate in `contacts`, each with `"email": ""` (not omitted, not guessed) since nothing has been enriched yet. Run `prepare_batch.py` to produce the ClickUp-ready markdown, then push it with `clickup-tasks`' `update-task` (or `update-batch` for just the one company). The formatter labels every contact "EMAIL NOT YET VERIFIED" automatically, which is accurate at this point — that's expected, not an error.

This means the ClickUp record always has full drafted outreach for every named candidate immediately after research, regardless of whether or when Apollo enrichment happens next.

### 7. Stop and confirm before spending Apollo credits

Show the user the candidate list (names and titles) — noting that outreach is already drafted and logged for each of them — and ask explicitly whether to proceed with enrichment to reveal verified emails. This is a deliberate checkpoint, not a formality — enrichment consumes Apollo credits and pulls personal contact data, and the user specifically wants a say before that happens on every new site. Don't skip this even if a previous run in the same conversation was approved; ask again per company.

If the user says no, stop here. The task keeps its site notes and full drafted outreach for every candidate, just with "EMAIL NOT YET VERIFIED" in place of an address — offer to come back and finish the enrichment later. Nothing needs to be re-drafted when that happens; only the email/source fields change.

### 8. Enrich and update the already-logged drafts (once approved)

1. Run `apollo_people_match` (by Apollo person ID from step 5) on each selected candidate to reveal name + verified email. If Apollo can't verify someone specific, the web-search fallback in `arctium-bess-outreach-emails`'s SKILL.md applies (public sources only — staff directories, bios, press — never a masked data-broker preview, never a guessed/pattern-inferred address). If Apollo runs out of credits partway through a batch, say so plainly, keep the already-revealed contacts, and leave the rest as "EMAIL NOT YET VERIFIED" rather than guessing or stalling the whole task.
2. Rebuild the same `companies.json` from step 6 with the revealed `email` (and `source`, defaulting to "Apollo.io (verified email)" unless the web-search fallback was used) filled in for each successfully-enriched contact — **do not re-draft the subject/body**, they were already written in step 6 and shouldn't change just because an email showed up. Re-run `prepare_batch.py` and push the update the same way as step 6.

Leave the task status as whatever it already was unless the user asks otherwise.

### 9. Report back

Summarize: which company, the task URL, how many contacts were found vs. how many got verified emails, and a one-line note on what's in the task now (drafts logged for all candidates, verified emails added for N of them / enrichment not yet run / enrichment declined).

### Notes

- This skill assumes `arctium-bess-outreach-emails` and `clickup-tasks` are both available — it leans on both rather than duplicating their logic. If either is missing, say so rather than reimplementing the email house style or the ClickUp write path from scratch.
- A single Maps link or business name is the common case, but if the user gives several at once, run steps 1-6 for each first (so all the tasks, site research, and drafted-but-unenriched outreach exist), then do the confirmation/enrichment steps (7-8) per company, confirming enrichment separately for each — don't bundle the credit-spend confirmation across companies into one yes/no.

