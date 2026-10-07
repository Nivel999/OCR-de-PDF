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

## Decisões confirmadas

- `midia` é a única tabela de persistência prevista para esta integração. Os resultados do OCR e do LLM serão gravados como novas colunas no próprio registro de mídia.
- Registros com IDs diferentes podem conter o mesmo PDF. O serviço calcula SHA-256 sobre os bytes originais do arquivo baixado; hashes iguais comprovam, para fins práticos, que os arquivos são idênticos byte a byte.
- Quando já existir processamento concluído com o mesmo `pdf_sha256` e a mesma versão de processamento, o serviço copia o resultado para as colunas do novo registro. Isso preserva consulta direta por ID, sem repetir OCR e LLM.
- O reaproveitamento é uma otimização interna: cada registro de `midia` mantém seus próprios Markdown, JSON, resumo, campos extraídos, status e metadados.

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
