# ARD — Architecture Decision Records

<!--
  A running log of decisions and WHY they were made. This is the local summary;
  link the authoritative source at the top. Add a new ARD entry per decision —
  never silently rewrite history; supersede with a new entry instead.
-->

> **Primary source:** {{LINK to authoritative ARD}}
>
> Always consult the source for the authoritative version; this file is a quick-reference summary.
>
> **Local Markdown mode:** if the project stores docs in-repo (Step 0 of project-kickoff.md), THIS file is the source of truth — delete the "Primary source" line above rather than pointing it at itself.

**Project:** {{PROJECT_NAME}}
**Version:** {{0.1 — Draft}}
**Date:** {{YYYY-MM-DD}}
**Status:** {{Draft / Under review / Accepted}}

---

## Decision Summary

| ARD | Topic | Decision |
|---|---|---|
| ARD-01 | Persistência e PDFs duplicados | Usar apenas `midia`, gravar resultados em cada registro e reaproveitar processamento por SHA-256. |
| ARD-02 | {{topic}} | {{decision}} |

---

## ARD-01 — {{Title}}

{{What was decided.}}

**Rationale:** {{Why — the trade-offs and what was rejected.}}

**Consequences:** {{What this forces or enables downstream.}}

---

## ARD-02 — {{Title}}

{{...}}

---

## Decisão aprovada — Resultados duplicados por registro de mídia

Os dados extraídos pelo OCR e pelo LLM serão persistidos como novas colunas da tabela `midia`. Cada registro terá seus próprios resultados completos, mesmo quando o PDF for idêntico ao de outro registro.

Antes de processar, o serviço calculará SHA-256 sobre os bytes originais do PDF. Se houver resultado concluído com o mesmo hash e a mesma versão de processamento, o serviço copiará os resultados para o novo registro em vez de repetir OCR e LLM. O hash será gravado em `pdf_sha256` para comprovar identidade byte a byte e detectar alterações posteriores do arquivo.

**Rationale:** funcionários consultarão o banco diretamente pelo registro de `midia`; duplicar os campos de resultado simplifica essas consultas e evita referências ou junções adicionais. O hash reduz custo e tempo sem alterar essa experiência de consulta.

**Consequências:** o worker precisa comparar `pdf_sha256` e versão do processamento antes de executar OCR/LLM, tratar PDFs idênticos recebidos simultaneamente sem processá-los em paralelo e copiar os resultados de forma atômica. Os nomes, tipos e conjunto completo de colunas ainda serão definidos no modelo de dados.

---

## Open Decisions

1. {{unresolved decision}}

---

## ARD-02 — Fila de processamento de PDF separada da mídia

**Decisão:** manter os registros e os campos de consulta em `cadastro.midia` e
usar `cadastro.midia_processamento_pdf` para orquestrar o processamento. A tabela
de processamento possui uma linha por mídia, status, tentativas, reserva do worker,
erro, SHA-256, versão do pipeline, Markdown OCR, extração JSON e referência à
origem quando o resultado for reutilizado.

**Racional:** `midia` já contém dados de produção e é a tabela que os funcionários
consultam. Separar estado operacional e artefatos grandes evita sobrecarregá-la e
permite reserva atômica de trabalho sem perder resultados consultáveis no registro
de mídia.

**Consequência:** o worker deve atualizar as duas tabelas na mesma transação e não
deve processar simultaneamente a mesma linha da fila.
