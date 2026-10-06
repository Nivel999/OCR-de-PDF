# Parallel Agents — Isolation with Git Worktrees

<!--
  How to run MORE THAN ONE agent at a time in this repository without agents
  overwriting each other's work. The rule is simple: parallel work happens in
  separate git worktrees, never in the same checkout.

  Golden rule: one agent = one worktree = one branch. Sequential work stays in
  the main checkout — don't create a worktree for work that isn't parallel.
-->

## ⛔ The rule

**Never run two agents concurrently in the same working directory.**

If work is going to be done in parallel — you are spawning subagents, the user
asked for several tasks "at the same time", or a second agent is already running
in this repo — **each agent MUST work inside its own git worktree, on its own
branch.**

Why: agents share one filesystem. Two agents editing the same checkout produce
half-applied edits, clobbered files, a `git status` that mixes unrelated
changes, and commits that capture another agent's work-in-progress. A worktree
gives each agent a private directory backed by the same repository — isolated
files, isolated branch, shared history.

**When NOT to use a worktree:** a single agent doing one task at a time. Stay in
the main checkout; worktrees add setup cost and cleanup for no benefit.

---

## Decision check — before spawning parallel work

Ask, in order:

1. **Will more than one agent write files at the same time?**
   → No: work in the main checkout. Done.
   → Yes: continue.
2. **Are the tasks truly independent** (different files, no shared migration, no
   ordering dependency)?
   → No: **do not parallelise.** Sequence them via
     [task-queue.md](task-queue.md) — the queue is explicitly top-to-bottom.
   → Yes: continue.
3. **Give each agent its own worktree** using the protocol below.

Read-only agents (search, review, audit — no writes) do **not** need a worktree
and may share the main checkout.

---

## Protocol

```
main checkout  ──┬── .worktrees/feat-a   (agent A, branch feat/a)
                 ├── .worktrees/feat-b   (agent B, branch feat/b)
                 └── .worktrees/fix-c    (agent C, branch fix/c)
```

### 1. Create one worktree per parallel agent

```bash
# from the main checkout, branch off the up-to-date base
git fetch origin
git worktree add -b feat/task-a .worktrees/feat-task-a origin/main
```

- **Branch name** follows the git convention in
  [../coding_conventions.md](../coding_conventions.md): `feat/`, `fix/`,
  `chore/`, `infra/`.
- **Directory name** mirrors the branch (slashes → dashes) so it's obvious which
  worktree holds what.
- **Base off the shared base branch** (`origin/main`), not off another agent's
  branch — that would couple two "independent" tasks.
- Keep worktrees under `.worktrees/` at the repo root and make sure that path is
  in `.gitignore`.

### 2. Brief each agent explicitly

Every parallel agent must be told, in its prompt:

- **its absolute worktree path** — and that it works **only** inside it;
- **its branch name**;
- **the exact scope** of its task (files/areas it owns);
- that it must **never** `cd` into the main checkout or another worktree, and
  never touch another agent's branch;
- that it **declares its own agent-work page** in project memory (worktree,
  branch, areas) before starting, and closes it when it stops — see
  [project-memory.md](project-memory.md).

### 3. Each agent commits on its own branch

Agents commit their own work, in their own worktree, with conventional commit
messages. No agent commits on behalf of another, and no agent commits from the
main checkout while parallel work is in flight.

### 4. Integrate sequentially, then clean up

Merging is **not** parallel work — the orchestrator does it, one branch at a
time, after each agent has finished and reported:

```bash
git -C . merge --no-ff feat/task-a     # or open a PR per branch
# resolve conflicts here, in the main checkout, one branch at a time

git worktree remove .worktrees/feat-task-a
git branch -d feat/task-a              # once merged
```

If a worktree was abandoned or its directory deleted manually:

```bash
git worktree list      # what still exists
git worktree prune     # drop stale registrations
```

**Leave no orphans: delete the worktree when its work is finished.** The agent
that owns a worktree removes it, in the same session, as soon as its branch is
merged into `main` (or the work is abandoned) and nothing more is planned there.
Worktrees are not free: each holds its own build output (for a Rust project,
10–60 GB of `target/`), and on one project seventeen of them accumulated and
filled the disk, which made test gates fail with "disk full".

```bash
git -C <worktree> status --porcelain                   # must print nothing
git fetch origin
git merge-base --is-ancestor <branch> origin/main && echo merged
git worktree remove <worktree>
git branch -d <branch>     # refused? the local main is stale; the check above
                           # against origin/main is what counts, then use -D
git worktree prune
```

- Check against `origin/main`, not the local `main`: the local one is often
  days behind, so `git branch -d` refuses branches that are in fact merged.
- Uncommitted changes or unmerged commits mean the work is **not** finished:
  keep the worktree, or ask the user before discarding anything.
- Never remove a worktree another agent is using (its work page in project
  memory is `in-progress`, `paused` or `waiting-response`).
- If you run *inside* the worktree, leave it before removing it.

---

## Shared state that worktrees do NOT isolate

A worktree isolates *tracked files and the branch*. It does not isolate anything
outside the repo. Before parallelising, check these and either give each agent
its own or serialise the work:

| Shared resource | Risk | Handling |
|---|---|---|
| **Dependencies** (`node_modules`, `.venv`, …) | Not copied into a new worktree | Install per worktree, or symlink/share a cache deliberately |
| **`.env` / local secrets** | Untracked → missing in the worktree | Copy them into each worktree as part of setup |
| **Dev server / DB ports** | Two agents binding the same port | Assign a distinct port per agent, or only one agent runs the app |
| **Local database, seeds, migrations** | Concurrent migrations corrupt shared state | One database per worktree, or serialise migration tasks |
| **External services** (PM tool, deploys, cloud resources) | Two agents mutating the same remote record | The orchestrator owns these; agents don't touch them concurrently |
| **Task tracker statuses** | Duplicate/conflicting status updates | One agent per task — see [notion-workflow.md](notion-workflow.md) |
| **Work claimed by agents in other sessions** (other harnesses, other machines) | Two agents take the same files, branch or production without seeing each other | Every agent declares a `work/` page in project memory and waits on an overlap — see [project-memory.md](project-memory.md) |

If two tasks contend for anything in this table and it can't be split, they are
**not** independent — run them sequentially.

---

## Interaction with the task queue

[task-queue.md](task-queue.md) is deliberately sequential: one task at a time,
finished and committed before the next. Parallel agents are the **exception**,
used only when the user asks for parallel execution or when a batch of tasks is
demonstrably independent. In that case:

- Each parallel task gets its own worktree, branch, and agent.
- Each still follows the full lifecycle in
  [notion-workflow.md](notion-workflow.md) (`In progress` → implement →
  `To test`) — for its **own** task only.
- The queue is marked off per task as each one is integrated, not when all the
  agents are spawned.

---

## Checklist

- [ ] Parallel work is genuinely independent (else: sequence it).
- [ ] One worktree + one branch per writing agent, based on `origin/main`.
- [ ] `.worktrees/` is git-ignored.
- [ ] Each agent briefed with its path, branch, and scope — and told not to leave it.
- [ ] Each agent declares its own agent-work page in project memory, and closes it when it stops.
- [ ] Untracked prerequisites (`.env`, deps) present in each worktree.
- [ ] Shared resources (ports, DB, remote records) split or serialised.
- [ ] Branches integrated one at a time by the orchestrator.
- [ ] Each worktree deleted by its owner as soon as its branch is merged (checked against `origin/main`); branch deleted; `git worktree prune` run.
