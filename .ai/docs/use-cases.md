# Use Cases & User Flows

<!--
  How users interact with the system: actors, use cases (with diagrams), and the
  step-by-step workflows for the key journeys. First document of the modeling
  phase (Step 3a). Depends on the SRS. Local summary; link the source at the top.
  See workflows/project-kickoff.md → Step 3a for the interview questions.
-->

> **Primary source:** {{LINK to authoritative copy}}
>
> Always consult the source for the authoritative version; this file is a quick-reference summary.
>
> **Local Markdown mode:** if the project stores docs in-repo (Step 0 of project-kickoff.md), THIS file is the source of truth — delete the "Primary source" line above rather than pointing it at itself.

**Project:** {{PROJECT_NAME}}
**Version:** {{0.1 — Draft}}
**Date:** {{YYYY-MM-DD}}
**Status:** {{Draft / Under review}}

---

## Actors

| Actor | Type | Description |
|---|---|---|
| {{name}} | {{human / external system}} | {{role and what they do}} |

---

## Use Cases

| UC | Actor | Goal | Related FR | Priority |
|---|---|---|---|---|
| UC-01 | {{actor}} | {{what they want to accomplish}} | {{FR-0X}} | MVP |
| UC-02 | {{actor}} | {{goal}} | {{FR-0X}} | Post-MVP |

---

## Use-Case Diagram

<!-- Keep diagrams as TEXT so they version cleanly. ASCII is the default — it
     renders everywhere. Swap in Mermaid only if the authoritative store renders
     it (see ground rule 6 in workflows/project-kickoff.md). -->

```
  {{Actor}}
     │
     ├──▶ UC-01: {{goal}}
     └──▶ UC-02: {{goal}}
```

---

## User Flows

<!-- One subsection per critical journey. Main path + the alternate/error paths. -->

### {{Flow name}} (UC-0X)

**Trigger:** {{what starts it}}
**Actor:** {{who}}
**Precondition:** {{state before}}

**Main path:**
1. {{step}}
2. {{step}}

**Alternate / error paths:**
- {{condition}} → {{what happens}}

**Postcondition:** {{state after success}}

---

## Open Questions

| # | Question | Owner | Status |
|---|---|---|---|
| 1 | {{unresolved flow question}} | {{who}} | Open |
