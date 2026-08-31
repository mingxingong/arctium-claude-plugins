# Apollo enrichment workflow — how to find contacts + verified emails without stalling

This skill runs autonomously end to end, with no pause for the user. That constrains which Apollo tools you can use: some Apollo tools (company-level enrich/search, e.g. `apollo_organizations_enrich`, `apollo_mixed_companies_search`) carry a mandatory confirmation step before they'll spend credits, which would block an unattended run. Avoid them. The two tools below don't have that restriction and are sufficient for this job.

## The two-step pattern

1. **`apollo_mixed_people_api_search`** — search for people at the target organization. This does NOT return an email, just candidate people (name, title, LinkedIn, person ID).
   - Search by company name/domain plus title keywords relevant to the category (see below).
   - If the first search returns nobody useful, broaden the title keywords before giving up on the org.

2. **`apollo_people_match`** — given a specific person (by Apollo person ID, or by name + company/domain), reveals their verified work email.
   - Some matched people come back with `email_status: "unavailable"`. When that happens, don't drop the organization — go back to step 1, pick a different candidate at the same org, and try again once. If a second contact also has no email, then drop the org and move on. Log which orgs were dropped and why so the final summary is honest about coverage.

## Title keywords by category

Pick keywords based on which category bucket the org falls into (see `arctium-profile.md`):

- Direct-sale orgs (ports, campuses, housing, industrial, data centers): Facilities Manager, Sustainability, Energy Manager, Director of Operations, VP Operations, Environment/Environmental.
- Utilities / energy programs: Energy Solutions, Program Manager, Director of Energy Programs.
- Engineering/consulting firms: Principal, President, Director, VP — these firms are often small enough that leadership is the right contact.
- Associations: Executive Director, VP Policy/Advocacy, Director of Engagement/Operations — the person who runs membership/events, not a random member-facing role.
- Equipment dealers: Director/VP Sales, Corporate Accounts.
- Funding/financing bodies: Executive Director, Program Manager, VP.

## Picking one contact per organization

One good contact per organization is enough — don't multi-thread the same org with several emails in one pass. If Apollo's search surfaces several plausible people, prefer the one whose title most directly owns the relevant budget or relationship (e.g. an Energy Manager over a generic Operations Manager), and prefer a title match over pure seniority (a Director of Sustainability beats a VP of something unrelated).

## Efficiency note

Apollo credits cost money. Don't run redundant searches — once you've found a working email for an org, stop searching that org. Don't call company-search/enrich tools "just to double check" a company you've already confirmed exists from the event source material.
