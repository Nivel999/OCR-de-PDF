# Project Management Workflow (Notion or local)

<!--
  How the assistant reads and updates project management (tasks + docs). The same
  shape works in TWO storage modes — the user picks one at kickoff (Step 0 of
  project-kickoff.md):
    • Notion via MCP (default) — a parent page + two child databases.
    • Local Markdown — the same two collections as files/folders in-repo.
  Everything below (the two collections, their schemas, the task-naming rule, and
  the working lifecycle) applies to BOTH modes. The Notion path is written out
  first; the "Local Markdown alternative" section maps each piece to files.
  You can also adapt the same shape to Linear/Jira/GitHub Issues.
-->

## Storage mode

This project stores its docs and tasks in: **Local Markdown**.

Regardless of mode, every project has the same two collections:

- **Documents Hub** — one entry per document produced by `project-kickoff.md`.
- **Task Tracker** — one entry per task.

## Workspace

All project management lives in: docs/documents-hub.md, .ai/docs/, tasks/ and
this repository's Git history.

> **Notion setup:** the PM MCP server is declared in `.mcp.json`. Enable/authorise
> the connector and restart the agent so the tools load. Fill in the IDs below on
> first authenticated read.
>
> **Local setup:** no MCP needed — the collections are files in the repo (see
> "Local Markdown alternative" below).

## Project Page Structure (Notion)

In Notion mode, each project is a single **parent page** with exactly **two child
databases**. `project-kickoff.md` reconciles this structure at Step 0
(check-or-create — never duplicate).

```
{{Project}} (parent page)
├── 📚 Documents Hub   (child database) — one row per SE document
└── ✅ Task Tracker     (child database) — one row per task
```

Record the parent page URL and both database IDs here and in `ai.md`.

## Key Databases

| Database | Data Source ID | Purpose |
|---|---|---|
| **Task Tracker** | tasks/ | All project tasks |
| **Documents Hub** | docs/documents-hub.md | The project's Software Engineering documents |

## Documents Hub Schema

One row per document produced by `project-kickoff.md`. Register each document here
as soon as it is saved.

- **Doc name** — title
- **Category** — select — one of: `System Description` / `SRS` / `Use Cases` / `Data Model` / `Wireframes` / `Architecture` / `ARD` / `Design Doc`
- **Created by** — created by (Notion auto)
- **Created time** — created time (Notion auto)
- **Last edited by** — last edited by (Notion auto)
- **Last updated time** — last edited time (Notion auto)

> `Created by`, `Created time`, `Last edited by`, and `Last updated time` are
> Notion's built-in auto-managed property types — add them when creating the
> database; they populate themselves. When reconciling an existing Documents Hub,
> only `Category` options may need topping up to cover the categories above.

## Task Schema

- **Task name** — title
- **Status** — status — `Not started` / `In progress` / `Done` / `To test` / `ReFix` / `Postpone`
- **Assignee** — person
- **Due date** — date
- **Priority** — select — `High` / `Medium` / `Low`
- **Task type** — select — `🐞 Bug` / `💬 Feature request` / `💅 Polish`
- **Phase** — select — {{your project phases}}

### Status lifecycle

The six status values are not interchangeable labels — they encode who the task
is waiting on:

| Status | Meaning | Who moves it next |
|---|---|---|
| `Not started` | Specced, not begun. | The assistant, when it picks the task up. |
| `In progress` | Being worked on **right now**. Set this *before* touching code. | The assistant, when the work is done. |
| `To test` | Implemented; awaiting human verification. | The user tests it. The assistant moves it on the user's word: `Done` when the user says it passed, `ReFix` when the user reports failures. |
| `ReFix` | Tested and **failed**. The problems are written in the task's **"After tests"** section. | The assistant, by fixing what's listed there. |
| `Done` | Implemented **and** verified by the user. | — terminal. |
| `Postpone` | Deliberately parked. Record *why* and what would unblock it in the task body. | The user, when it becomes relevant again. |

The user does the testing; either the user or the assistant may then record the
result. When the user says a task is tested and done, the assistant sets `Done`.
The assistant never marks its own work `Done` because its own checks passed:
`To test` is the step where a person verifies it.

### The "After tests" section

When a task comes back as `ReFix`, what failed goes under an **"After tests"**
heading in the task body. The user writes it, or tells the assistant, who records
it there and sets `ReFix`:

```markdown
## After tests

- [ ] {{What broke, with steps to reproduce or the wrong output observed}}
- [ ] {{Next problem}}
```

The assistant reads that section first, fixes each item, checks it off, and sets
the status back to `To test`: the fix needs the user's test just as the first
version did.

## Task Naming & Ordering

Task titles are **prefixed so that an alphabetical sort equals execution order**.
When creating tasks, name them by which bucket they belong to:

**Phase tasks** — tasks that belong to an ordered project phase:

```
[Phase X] Task name
```

- `X` is the phase number. **Zero-pad** to keep the sort correct past 9
  (`[Phase 01]`, `[Phase 02]`, … `[Phase 10]`).
- Within a phase, create tasks in their intended execution order; if that order
  matters, add a step index too: `[Phase 02] 03 · Task name`.

**Epics** — work that sits outside the phase sequence:

```
[Epic] Epic name              ← the epic itself
[Epic name X] Task name       ← each task under that epic
```

- The epic row is titled `[Epic] Epic name`.
- Each of its tasks is prefixed with the epic's name + its sequence number,
  zero-padded: e.g. epic **Onboarding** → `[Onboarding 01] Task name`,
  `[Onboarding 02] Task name`.

**Why:** sorting the Task Tracker (or `task-queue.md`) alphabetically by title
then yields phases in order, tasks within each phase in order, and each epic's
tasks grouped and sequenced together. Keep the **Phase** property set as well —
the prefix and the property must agree.

The **same prefix rule applies to local Markdown** (below): use it for the task
**filename** so a directory listing sorts into execution order — e.g.
`[Phase 01] Task name.md`.

## Local Markdown alternative

If the user chose **Local Markdown** at kickoff, the same two collections live in
the repo instead of Notion — no MCP required. Suggested layout:

```
docs/                         ← Documents Hub (the .ai/docs/** files are the entries)
  documents-hub.md            ← index: one row per document (Doc name · Category · file · updated)
tasks/                        ← Task Tracker: one file per task
  [Phase 01] Task name.md     ← front-matter carries the schema fields
  [Onboarding 01] Task name.md
```

- **Documents Hub → `documents-hub.md`** — a Markdown table mirroring the schema
  above (Doc name · Category · Local file · Last updated). The document bodies are
  the `.ai/docs/**` files themselves.
- **Task Tracker → `tasks/` folder** — one `.md` per task. Put the schema fields
  in YAML front-matter (`status`, `assignee`, `due`, `priority`, `type`, `phase`)
  and name the file with the ordering prefix so the folder sorts correctly.
- **`task-queue.md`** stays the ordered checklist of what to work on next, in both
  modes.

Everything else in this file — the schemas, the naming rule, and the working
lifecycle below — is identical; read "database/row/property" as
"file/entry/front-matter field".

## Working on a Task

1. **Fetch the task** to read the spec and deliverables.
2. **Set status to "In progress"** before starting work — before touching any code —
   and **declare your work in project memory** (check other agents' `work/` pages,
   then write yours; see [project-memory.md](project-memory.md)). If another agent's
   page overlaps, wait and keep checking until it is released.
3. **If the status was `ReFix`,** read the **"After tests"** section first: it lists what failed verification. Fix those items and check them off.
4. **Check off deliverables** as you complete each one (`- [ ]` → `- [x]`) — *only if the task has a Deliverables section*. Many tasks don't; skip this step for those.
5. **Set status to "To test"** once the work is complete, and close your
   agent-work page as `done` (say the task is at `To test`). Nobody holds the
   files while the user tests; a `ReFix` later is new work with a new page.
6. **When the user says it is tested and done, set `Done`.** If the user reports
   failures instead, record them under "After tests" and set `ReFix`.

## Closing a Bug Task

Before moving a `🐞 Bug` out of `In progress`, record in the task's **Plan** section:

1. **Root Cause** — why it happened.
2. **Solution** — each file changed + a brief description.
3. **Result** — outcome and any safety improvements.
4. Set status to **`To test`** after writing the above.

## Updating a Task

Use the PM tool's update API to change properties. Status values: `Not started`,
`In progress`, `To test`, `ReFix`, `Done`, `Postpone` — see the Status lifecycle
table above for what each one means and who moves it.
