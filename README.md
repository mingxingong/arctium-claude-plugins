# arctium-plugins marketplace

Hosts one plugin, **arctium-sales-tools**, bundling 4 skills:

- `arctium-bess-outreach-emails` — drafts BESS/ESI cold outreach and pitch emails, and turns logged ClickUp drafts into Outlook drafts
- `arctium-esi-prospecting` — prospects a business or Google Maps link for the BC Hydro ESI list
- `arctium-tradeshow-prospecting` — runs a trade show exhibitor list into a full prospect + outreach pipeline
- `clickup-tasks` — shared helper the other three call for all ClickUp reads/writes (rate-limited REST API, not the ClickUp MCP server)

## Setup (one-time, per person)

1. Add this marketplace:
   ```
   /plugin marketplace add <git-url-or-owner/repo>
   ```
   (or, if you just unzipped this folder locally: `/plugin marketplace add /path/to/arctium-plugin`)

2. Install the plugin:
   ```
   /plugin install arctium-sales-tools@arctium-plugins
   ```

That installs all 4 skills together — they're meant to run as a set since three of them call `clickup-tasks` internally.

## Notes

- `arctium-tradeshow-prospecting` needs an environment with open network access (writes to ClickUp's REST API directly) — it will not work in a network-sandboxed session.
- `clickup-tasks` reads ClickUp auth from the macOS Keychain by default, with an environment-variable override. Whoever installs this needs their own ClickUp API credentials set up the same way.
- These skills reference Arctium Energy-specific context (BC Hydro ESI incentive, product lines, ClickUp list names) — treat this repo as internal, not for public distribution.

## Updating

Bump `version` in `plugins/arctium-sales-tools/.claude-plugin/plugin.json` whenever you push a change, so installed copies pick up the update.
