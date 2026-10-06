# Task Queue

Sequential task list. Process **top to bottom** — only start the next task after the current one is fully complete and committed.

> **Running tasks in parallel?** This queue is sequential by default. If the user
> asks for parallel execution — or a batch of tasks is demonstrably independent —
> each concurrent agent MUST get its own git worktree and branch. See
> [parallel-agents.md](parallel-agents.md); never run two writing agents in the
> same working directory.

> **Ordering:** tasks are named `[Phase X] Task name` (or `[Epic name X] Task name`
> for epics) per the Task Naming & Ordering convention in `notion-workflow.md`, so
> listing them **alphabetically by title yields execution order**. Keep this list
> in that order.

## How to process

For each task URL below:

1. **Fetch** the task page to read the spec and deliverables.
2. **If the task status is `ReFix`:** find the **"After tests"** section — work on the problems described there (see the Status lifecycle table in `notion-workflow.md`).
3. **Follow `notion-workflow.md`** to work on it (set status, declare your work in project memory per `project-memory.md`, implement, update deliverables/plan).
4. **Commit** all changes with a conventional commit message once the task is done.
5. **Mark the task as handled** below by changing `- [ ]` to `- [x]`. Note this tracks *your* pass through the queue — the task itself lands on `To test`, and reaches `Done` once the user says it is tested (the assistant may then set it).
6. **Move to the next task.**

## Tasks

<!-- Add task URLs below, one per line, as a checkbox list. -->
<!-- Example:
- [ ] https://app.notion.com/p/TASK_PAGE_ID
- [x] https://app.notion.com/p/ANOTHER_TASK_PAGE_ID
-->
