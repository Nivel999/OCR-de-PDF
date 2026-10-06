# Project Kickoff — Guided Document Generation

<!--
  THE STARTING POINT for a brand-new software project built with this template.
  This workflow tells the AI how to interview the user and produce the core
  Software Engineering documents, in order, saving each to the chosen storage.

  Golden rule: ONE document at a time. Interview → draft → get the user's
  sign-off → save → only then move to the next. Never invent facts to fill a
  gap — if you lack information to write a section safely, STOP and ask.
-->

## ⛔ How to run this — READ BEFORE DOING ANYTHING

This is an **interactive interview**, not a batch job. The failure mode to avoid:
reading this file and then generating every document in one go, inventing the
answers (especially the tech stack). **Do not do that.**

**The run protocol — non-negotiable:**

1. **One step per turn.** Do the current step, then **stop and wait** for the
   user. Never run ahead to the next document in the same turn.
2. **Ask, then WAIT.** For each step, ask that step's questions (in small
   batches — a wall of 15 questions is as bad as asking none). **End your turn
   and wait for the user's answers.** Do not draft the document until they reply.
3. **Never assume, never dictate.** You may *recommend* with rationale, but every
   decision the user hasn't made — **especially the tech stack, framework,
   hosting, and architecture** (e.g. "Vercel + Nuxt")— must be **presented as
   options and chosen by the user.** Picking a stack for them is a bug, not a
   convenience. If unsure whether something is decided, ask.
4. **Get an explicit "approved"** on each drafted document before moving on.
   Silence is not approval.
5. **When in doubt, stop and ask.** Missing information is a reason to pause, not
   to invent.

If you catch yourself about to produce multiple documents at once, or writing a
stack/architecture choice the user never made — **stop and ask instead.**

---

## What this is

A step-by-step protocol for turning an idea into a documented software project.
You (the AI) act as a senior engineer + architect running a structured intake.
You produce **seven documents in a fixed order**, each building on the last:

| # | Document | Local template | Produces |
|---|---|---|---|
| 1 | **System Description** | [docs/system-description.md](../docs/system-description.md) | The wide-angle picture: what, who, why |
| 2 | **Software Requirements Specification (SRS)** | [docs/SRS.md](../docs/SRS.md) | What it must do + how it must behave |
| 3a | **Use Cases & User Flows** | [docs/use-cases.md](../docs/use-cases.md) | Actors, use cases, diagrams, workflows |
| 3b | **Data Model** | [docs/data-model.md](../docs/data-model.md) | Entities, schema, types, classes, ERD |
| 3c | **Wireframes** | [docs/wireframes.md](../docs/wireframes.md) | Low-fidelity screens per target device |
| 4 | **Architecture** | [architecture.md](../architecture.md) + [docs/ARD.md](../docs/ARD.md) | Stack, services, data flow, infrastructure |
| 5 | **Design Doc** | [docs/design-doc.md](../docs/design-doc.md) + [ui_guidelines.md](../ui_guidelines.md) | Visual system, components, design system |

Documents 3a–3c are the **modeling phase** and are produced together, in that
sub-order, after the SRS is signed off.

---

## Ground rules (apply to every step)

1. **One document at a time, one step per turn.** Do not start — or draft — the
   next document until the current one is interviewed, drafted, reviewed by the
   user, and saved. Never emit several documents in a single turn.
2. **Interview first, write second — and WAIT.** Ask the step's questions, then
   end your turn and wait for answers. Do not draft from assumptions. Ask
   follow-ups whenever an answer is vague, contradictory, or incomplete.
3. **Never invent; never dictate decisions.** If the user hasn't decided
   something, ask — or record it as an **Open Question** rather than guessing.
   **Tech stack, frameworks, hosting, and architecture are the user's decisions**
   — present options with a recommendation and let them choose. Flag every
   assumption explicitly.
4. **Each doc builds on the prior ones.** Re-read the earlier documents before
   drafting; keep terminology, actor names, and entity names consistent.
5. **Two copies stay in sync — *unless* storage is Local Markdown.** When the
   authoritative copy lives in an external store (see Step 0), the `.ai/**` file
   is a local summary that links to it, and you update both. If the user chose
   **Local Markdown** there is only one copy: the `.ai/**` file *is* the source
   of truth — drop the `{{LINK to authoritative copy}}` header instead of
   filling it with a self-reference.
6. **Diagrams are ASCII by default.** A plain ASCII/box sketch inside a fenced
   block is the standard: it renders everywhere — plain Markdown, a terminal, a
   diff. Use **Mermaid only when the chosen storage renders it** (Notion, or
   another store with Mermaid support). Even then, keep the ASCII version in the
   `.ai/**` copy so the in-repo file stays readable.
7. **Register every document** in the Documents Hub (see `notion-workflow.md`)
   as soon as it is saved.
8. **Get an explicit "approved"** from the user before advancing. Offer to
   revise; do not assume silence is approval.

---

## Step 0 — Choose storage & set up the workspace

Before writing any document, decide where the authoritative copies live.

**Ask the user:**
- Where should project documents be stored? Options:
  - **Notion (default, recommended)** — via the Notion MCP already declared in `.mcp.json`.
  - **Local Markdown** — the `.ai/**` files are themselves the source of truth.
  - **Other MCP-connected store** — e.g. Confluence, GitHub wiki, Linear docs.
- If a store other than local: is the MCP connector authorised and loaded?
  (If not, ask the user to enable it in `.mcp.json` and restart the agent.)

### If Notion (default)

1. **Locate or create the parent project page.** Ask the user for an existing
   parent page (URL or ID). If they don't have one, create it in the workspace
   they name.
2. **Reconcile the two required child databases** under that page —
   **Documents Hub** and **Task Tracker**. For **each** one:
   - **Search first.** Look for a child database of that page whose title
     matches (case-insensitive; accept close variants like "Docs Hub",
     "Tasks Tracker"). Use the Notion MCP's search/query tools.
   - **If it exists → reuse it.** Do not create a duplicate. Read its current
     properties and compare against the schema in
     [notion-workflow.md](notion-workflow.md). If a required property is
     missing, **add** it (don't rename or delete the user's existing
     properties); if a `select`/`status` option the workflow relies on is
     missing, add that option. Report to the user what you reused vs. added.
   - **If it does not exist → create it** as a child database of the parent
     page, with the properties defined in
     [notion-workflow.md](notion-workflow.md) (Documents Hub schema / Task Schema).
3. **Record** the parent page URL and both database IDs in:
   - `.ai/ai.md` → "Project Management IDs" table, and
   - `notion-workflow.md` → "Key Databases" table.

> **Idempotent:** re-running Step 0 must never create a second Documents Hub or
> Task Tracker. Always search-then-decide; create only what's absent.

### If local Markdown

The same two collections live in the repo instead of Notion — see
[notion-workflow.md](notion-workflow.md) → "Local Markdown alternative". Check-or-create:

1. **Documents Hub** — ensure a `documents-hub.md` index exists (create it with the
   schema's columns if absent; reuse it if present). The document bodies are the
   `.ai/docs/**` files filled out in the steps below.
2. **Task Tracker** — ensure a `tasks/` folder exists for one-file-per-task, with
   task filenames prefixed per the Task Naming & Ordering rule.
3. Note the folder/space as the "Source of truth" at the top of `.ai/ai.md`.

### If another MCP store

- Confirm the connector is authorised and loaded, then map the two collections
  (Documents Hub, Task Tracker) onto that tool's equivalent of pages/databases —
  same check-or-create discipline. Note the location in `.ai/ai.md`.

### Project memory (lore) — always, whatever the storage above

lore is the project's memory by default. It does not replace the store chosen
above: that holds the plan and the documents, lore holds what happened and who is
working on what (see [project-memory.md](project-memory.md)).

**Ask the user:** which lore server, workspace and project name to use. Suggest
their own workspace (named after their username) and the repository's name.

1. Confirm lore's MCP tools are loaded (it is registered per machine, never in
   `.mcp.json`; setup is in [project-memory.md](project-memory.md) → "Once per
   machine"). If they are not, give the user the setup steps and wait.
2. Fill `.ai-memory.toml` at the repo root with the workspace and project, and keep
   it committed.
3. Check the connection with `memory_status` for that workspace and project.
4. Record the server, workspace and project in `.ai/ai.md` ("Project memory"), in
   `config/system.md` and in `project-memory.md` ("This project").

### Autonomous runs (optional) — ask, then set up or remove

**Ask the user** whether they want to enable autonomous runs. Before they answer,
explain it in two or three sentences:

> An autonomous run is when you tell the agents to work through the pending tasks
> on their own — overnight, say — without stopping to ask you. They coordinate
> through lore so each takes a different task. Whenever a decision would be yours,
> they choose the recommended option and write it down for you to review, and they
> leave you a to-do list for anything only you can do. You start one by saying
> "autonomous run". The agent then asks once whether merging and deploying are
> allowed, what the scope is, and when to stop.

- **Yes:**
  1. Keep [autonomous-run.md](autonomous-run.md) and fill its placeholders. Ask the
     user for the main branch and the quality gates now. The migrations folder, the
     shared files and the deploy procedure can wait until the architecture exists:
     leave those placeholders, and add a note in `task-queue.md` to fill them after
     Step 4.
  2. Keep its row in `.ai/ai.md` and the "Autonomous runs" hard rule.
- **No:** delete `autonomous-run.md`, its row in `.ai/ai.md` and the "Autonomous
  runs" hard rule. The user can add it back later from the template.

**Gate:** storage is chosen and reachable, and the two collections (Documents Hub
+ Task Tracker) exist — created if missing, reused if present, IDs/paths recorded.
Project memory answers for the recorded workspace and project. The user has said
yes or no to autonomous runs, and the files match that answer.
Only then proceed to Step 1.

---

## Step 1 — System Description

**Goal:** a wide, non-technical description of the whole system so everyone
shares the same mental model before requirements are pinned down.

**Interview — ask the user:**
- In one sentence, what is this product?
- What problem does it solve, and for whom? What happens today without it?
- Who are the users / actors? (roles, rough scale, technical level)
- What are the top 3–5 goals or outcomes the product must achieve?
- What's the scope of the first release vs. the long-term vision?
- Any constraints already fixed? (budget, deadline, platform, compliance, team)
- Are there existing systems it must integrate with or replace?
- What does success look like — how will you know it worked?

**Produce:** fill [docs/system-description.md](../docs/system-description.md).
Keep it readable by a non-engineer. Capture unknowns as Open Questions.

**Save & register**, get approval, then continue.

---

## Step 2 — Software Requirements Specification (SRS)

**Goal:** turn the description into concrete, testable requirements — what the
app will *do* and how it must *behave*.

**Interview — ask the user:**
- Walk me through what the app will *do*, feature by feature. What's the goal
  of each feature?
- For each capability: who triggers it, and what's the expected result?
- Which features are **must-have for launch (MVP)** vs. **later (Post-MVP)**?
- Behavioural / non-functional needs — probe each:
  - **Performance:** expected load, response-time expectations?
  - **Availability / reliability:** uptime, offline support, data-loss tolerance?
  - **Security & privacy:** auth model, roles/permissions, sensitive/PII data,
    regulations (GDPR, HIPAA, PCI…)?
  - **Scalability:** expected growth in users/data?
  - **Accessibility & localisation:** standards to meet, languages/regions?
  - **Compatibility:** browsers, OS versions, devices?
- Hard constraints? (must use / must not use a given tech, integration, vendor)
- What is explicitly **out of scope** for now?
- Any assumptions or dependencies the project relies on?

Ask any additional question you need that isn't answered by the System
Description. If an answer is ambiguous, drill down before writing it as a requirement.

**Produce:** fill [docs/SRS.md](../docs/SRS.md) — numbered functional
requirements (FR), non-functional requirements (NFR), constraints, out-of-scope.
Every requirement must be specific enough to test.

**Save & register**, get approval, then continue to the modeling phase.

---

## Step 3 — Modeling phase

Three documents, produced in this sub-order. Each depends on the SRS and on the
one before it.

### 3a — Use Cases & User Flows

**Goal:** how users interact with the system — actors, use cases (with
diagrams), and the step-by-step workflows for the key journeys.

**Interview — ask the user (only what the SRS didn't already answer):**
- Confirm the full list of actors (human roles + external systems).
- For each MVP feature, what's the user's goal and the main success path?
- What are the important alternate / error paths? (e.g. invalid input, no
  permission, network failure)
- Which journeys are the most critical to get right (the "happy paths")?
- Are there flows that cross multiple actors or require approvals/handoffs?

**Produce:** fill [docs/use-cases.md](../docs/use-cases.md):
- Actor list, use-case table (ID, actor, goal, priority).
- **Use-case diagram(s)** — ASCII by default; Mermaid (`graph`/`flowchart`) only
  if the chosen store renders it (see ground rule 6).
- Step-by-step **workflows** for the critical journeys (main + alternate paths).

### 3b — Data Model

**Goal:** the entities the system stores and how they relate — schema, types,
and (if OOP) classes.

**Interview — ask the user:**
- What are the core "things" the system tracks? (entities/nouns from the SRS)
- For each entity: key fields, their types, required vs. optional, defaults?
- How do entities relate? (one-to-many, many-to-many, ownership)
- What identifies each record? Any uniqueness / natural keys?
- Retention, soft-delete, audit/history needs? Any derived/computed fields?
- Preferred database paradigm if known (relational, document, graph, key-value)?

**Produce:** fill [docs/data-model.md](../docs/data-model.md):
- Entity/table definitions with field name, type, constraints, description.
- **ERD** — ASCII by default; Mermaid `erDiagram` only if the chosen store renders it (see ground rule 6).
- Class diagram(s) if the design is object-oriented.
- Enumerations and shared value types.

### 3c — Wireframes

**Goal:** low-fidelity layout of each screen, for every device the software runs on.

**Interview — ask the user:**
- Which devices/form factors must be supported? (web desktop, mobile web,
  native iOS/Android, tablet, watch, desktop app, TV, CLI…)
- What screens exist? (derive candidates from the use cases; confirm with user)
- For each screen: its purpose, the key elements, and the primary action.
- Navigation model between screens? (tabs, stack, drawer, wizard…)
- Any screens with device-specific layouts?

**Produce:** fill [docs/wireframes.md](../docs/wireframes.md):
- A screen inventory mapped to devices.
- A low-fidelity wireframe per screen (ASCII/box sketch, or link to a Figma /
  Excalidraw / image asset stored alongside the doc).
- Notes on responsive behaviour and per-device differences.

**Save & register** each modeling doc, get approval, then continue.

---

## Step 4 — Architecture

**Goal:** how the system is built — stack, languages, services, how they connect
and pass data, and the infrastructure it runs on.

**Interview — ask the user (propose options; recommend, don't dictate):**
- Any stack already mandated, or is this greenfield?
- Team's existing expertise / preferred languages & frameworks?
- Client(s): web framework? native/cross-platform mobile?
- Backend: language/framework, API style (REST/GraphQL/RPC), sync vs. async?
- Data stores (from the Data Model): which database(s) and why?
- Auth, file storage, background jobs, real-time, third-party services?
- Hosting / infrastructure: cloud provider, serverless vs. containers, CI/CD,
  environments (dev/staging/prod), region/latency needs?
- Budget / scaling ceiling that constrains infra choices?

Where the user is unsure, present 2–3 viable options with trade-offs and a
recommendation. Record the *why* for each significant choice as an ARD entry.

**Produce:**
- Fill [architecture.md](../architecture.md), section by section: System Overview
  (ASCII diagram — see ground rule 6), Services & Hosting, Code Structure,
  Data Model, Key Flows, Security, Open Architecture Questions.
- Log each significant decision as an entry in [docs/ARD.md](../docs/ARD.md)
  (decision + rationale + consequences).

**Save & register**, get approval, then continue.

---

## Step 5 — Design Doc

**Goal:** the visual system and component specs — this step **requires user
decisions** on look & feel.

**Interview — offer the user a design-system foundation to build on.**
Present these options and let them pick one, mix, or describe their own:

| Option | Feel | Good when |
|---|---|---|
| **Apple Human Interface Guidelines** | Clean, native iOS/macOS, depth & clarity | Apple-first / premium consumer apps |
| **Material Design 3** | Bold, tactile, adaptive, Android-native | Cross-platform, Google ecosystem |
| **Fluent (Microsoft)** | Professional, enterprise, productivity | Enterprise / Windows / Office-adjacent |
| **Carbon (IBM)** | Data-dense, rigorous, enterprise | Dashboards, data-heavy B2B tools |
| **Ant Design** | Comprehensive, form-heavy, business | Admin panels, internal tools |
| **Tailwind + shadcn/ui** | Utility-first, modern, highly customisable | Web apps wanting a bespoke feel fast |
| **Custom / brand-led** | Whatever the user defines | Strong existing brand or unique identity |

Then gather the specifics:
- **Brand & personality:** logo, tone (playful ↔ serious, minimal ↔ rich), references/competitors they admire.
- **Colour:** brand/primary colour, light &/or dark mode, accent & semantic
  (success/warning/error) colours. Offer a starter palette if they have none.
- **Typography:** preferred typeface(s) or the system-default from their chosen
  design system; heading/body scale; any hard rule (e.g. max weight).
- **Spacing & geometry:** density, corner radius, elevation/shadow style.
- **Components:** confirm the inventory from the wireframes; note key states/variants.
- **Motion & interaction:** animation level, feedback patterns.
- **Accessibility:** target contrast ratio, min touch target, min font size.

**Produce:**
- Fill [docs/design-doc.md](../docs/design-doc.md): visual identity, chosen
  design-system basis, screen list, component list, prototype links.
- Fill [ui_guidelines.md](../ui_guidelines.md): concrete colour tokens,
  typography scale, spacing/geometry tokens, component inventory, interaction
  patterns, accessibility rules.

**Save & register**, get approval.

---

## After kickoff

Once all seven documents are approved and saved:

1. Fill the remaining top-level context files if not already done:
   [ai.md](../ai.md) (project at a glance, navigation, hard rules) and
   [config/system.md](../config/system.md) (the AI's standing instructions).
2. Fill [coding_conventions.md](../coding_conventions.md) from the architecture choices.
3. Seed the **Task Tracker** with the first implementation tasks and list them in
   [task-queue.md](task-queue.md). Name every task per the **Task Naming &
   Ordering** convention in [notion-workflow.md](notion-workflow.md) —
   `[Phase X] Task name` for phase work, `[Epic] Epic name` + `[Epic name X]
   Task name` for epics — so an alphabetical sort gives execution order.
4. Hand off to the normal build loop: pick tasks top-to-bottom per
   [notion-workflow.md](notion-workflow.md).

The project is now fully specified and ready to build.
