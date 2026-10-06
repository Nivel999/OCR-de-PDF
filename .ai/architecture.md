# Architecture

<!--
  Describe HOW the system is built. This file + docs/ARD.md are the in-repo source
  of truth for structure. Keep prose tight; prefer diagrams and tables. Link the
  authoritative source (e.g. a Notion ARD page) at the top.
-->

> **Full detail:** {{LINK to authoritative architecture doc}} and [docs/ARD.md](docs/ARD.md).

## System Overview

<!-- A high-level diagram of the main components and the data flow between them. -->

```
{{ASCII_DIAGRAM — components and how data flows between them}}
```

{{One paragraph: the single most important architectural fact someone must know.}}

---

## Services & Hosting

| Service | Platform | Responsibility |
|---|---|---|
| {{service}} | {{platform}} | {{what it does}} |

---

## Code Structure

<!-- The folder layout and the rule that governs it (feature-first, layered, monorepo, …). -->

```
{{DIRECTORY_TREE with one-line annotations}}
```

{{One paragraph: the organising principle — e.g. "feature-first with data/domain/presentation layers".}}

---

## Data Model

<!-- Tables/collections and what they hold. Link to the full ERD/schema. -->

| Entity | Description |
|---|---|
| {{entity}} | {{what it stores}} |

---

## Key Flows

<!-- The 1–3 flows that matter most (e.g. ingestion, evaluation, auth). One subsection each. -->

### {{Flow name}}

{{Steps / sequence.}}

---

## Security

<!-- Access control model, secret handling, anything an assistant must respect. -->

- {{rule}}

---

## Open Architecture Questions

<!-- Track unresolved decisions so they aren't silently invented. -->

1. {{question}}
