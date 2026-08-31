---
name: "clickup-tasks"
description: "Use whenever creating or updating ClickUp tasks programmatically — via ClickUp's REST API directly, not the ClickUp MCP server (its call quota, as low as 300 calls/24h, is too low for anything beyond a handful of tasks). Handles auth (macOS Keychain, with an env var override) and a shared, cross-process rate limiter so any number of concurrent agents, skills, or scheduled tasks stay under ClickUp's real API rate limit collectively, not per-caller. Domain-agnostic: takes a list ID or task ID and plain markdown content, nothing else — any skill that needs to read, create, or update ClickUp tasks in bulk should call this instead of writing its own ClickUp REST calls."
---

## clickup-tasks

A shared, reusable skill for talking to ClickUp's REST API v2. It knows nothing about what the tasks are *for* — no contacts, no email drafts, no domain logic of any kind. It just creates, reads, and updates ClickUp tasks, singly or in batches, with two things handled correctly so you don't have to reinvent them: **auth** and **rate limiting**.

If you're writing or running a different skill that needs to touch ClickUp — creating prospect tasks, updating a status, logging research results, anything — use this rather than calling ClickUp's API yourself. The whole point is that everyone's ClickUp traffic goes through the same rate-limited path.

### Why this exists

Two failure modes drove this:
1. **The ClickUp MCP server's call quota is too low** for batch work (as low as 300 calls/rolling-24h on paid plans, 50/24h on Free) — a run touching more than a few dozen tasks burns through it fast. The REST API here uses ClickUp's normal per-minute rate limit instead, which comfortably handles batch work.
2. **Multiple agents hitting ClickUp's REST API concurrently, uncoordinated, can still blow past ClickUp's real rate limit** even though each one individually paces itself — e.g. 7 parallel agents each self-limiting to "a modest pace" can still collectively exceed the limit ClickUp actually enforces. This script's rate limiter is a shared, file-locked token bucket that every invocation of this script draws from, regardless of which process or skill started it, so N parallel callers correctly share one 50-calls/60-seconds budget instead of each getting their own.

### Auth

`scripts/clickup_task.py` checks `CLICKUP_API_TOKEN` in the environment first (useful for a one-off override), then falls back to macOS Keychain automatically — no prompt, no asking the user to paste a token into chat. Service name: `clickup-api-token`.

If it's not already stored, set it up once:
```bash
security add-generic-password -a "$USER" -s "clickup-api-token" -w "pk_..." -T /usr/bin/security -U
```
Get the token from ClickUp: avatar → Settings → Apps → Generate under API Token. If the script reports no token found, tell the user and give them that command — don't invent a workaround, and don't ask them to paste the token into chat if it might already be stored (check first by just running any command; the error message is unambiguous about what's missing).

### Usage

```bash
# sanity check
python3 scripts/clickup_task.py check-task --task-id 86e2uq2ng

# read a task's current name/status/description as JSON
python3 scripts/clickup_task.py get-task --task-id 86e2uq2ng

# list every task in a list as JSON (id, name, status, text_content) —
# useful for dedup checks before creating, or auditing before updating
python3 scripts/clickup_task.py list-tasks --list-id 901715151890 [--include-closed]

# create one task
python3 scripts/clickup_task.py create-task --list-id 901715151890 \
    --name "New prospect" --markdown "**Notes:**\n..." [--status "not started"]
# (--markdown-file <path> also works, for longer content)

# create many tasks from a JSON array file — see the script's docstring
# for the exact shape: [{"name": "...", "markdown_content": "...", "status": "..."}]
python3 scripts/clickup_task.py create-batch --list-id 901715151890 --file tasks.json

# update one existing task — only the fields you pass are changed
python3 scripts/clickup_task.py update-task --task-id 86e2uq2ng \
    --markdown-file description.md [--name "..."] [--status "..."]

# update many existing tasks from a JSON array file — shape:
# [{"task_id": "...", "markdown_content": "...", "name": "...", "status": "..."}]
# (only "task_id" is required; include only the fields you want changed)
python3 scripts/clickup_task.py update-batch --file tasks.json
```

None of these touch a task's status unless you explicitly pass `--status` (or include `"status"` in a batch entry) — leave it alone by default.

### Building the content

This skill takes `markdown_content` as a plain string — it has no idea what should be in it. Whatever calling skill needs to write structured content (a formatted list of contacts and drafted emails, a project status update, whatever) should build that string itself, in its own instructions, and pass the finished text here. Don't add domain-specific formatting logic to this script — if you find yourself wanting to, that logic belongs in the calling skill instead, so this one stays reusable for everything else that needs it.

### Batching and failure handling

Both `create-batch` and `update-batch` process their whole file in one run, print per-item success/failure as they go, and don't let one failure stop the rest — they finish with a summary count and list any failures to stderr. Don't retry a failure more than once; if something's genuinely broken (bad list ID, malformed entry), surface it rather than looping.
