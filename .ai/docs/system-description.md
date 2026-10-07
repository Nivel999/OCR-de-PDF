# Descrição do Sistema

<!--
  The wide-angle picture of the product, written to be readable by a non-engineer.
  This is the FIRST document produced in the project-kickoff workflow — everything
  else builds on it. Local summary; link the authoritative copy at the top.
  See workflows/project-kickoff.md → Step 1 for the interview questions.
-->

**Projeto:** OCR de PDF e Texto
**Versão:** 0.1 — Em revisão
**Data:** 2026-10-07
**Status:** Em revisão

---

## Overview

O OCR de PDF e Texto é um serviço local, executado por linha de comando em uma única máquina, que processa documentos PDF armazenados em um banco de dados. Ele baixa um lote de arquivos, extrai o texto nativo quando disponível ou aplica OCR às páginas que forem imagens, avalia a confiabilidade da leitura e usa um LLM local para gerar um resumo e extrair as informações necessárias.

Os resultados do processamento — incluindo o texto em Markdown, relatórios em JSON, o resumo e a referência ao arquivo e à página de origem de cada informação — retornam ao banco de dados. Não haverá interface gráfica, pastas locais de entrada e saída como meio principal de operação, nem intervenção humana durante o processamento.

---

## Problem & Value

- **Problema que resolve:** funcionários precisam ler manualmente todas as páginas de PDFs para localizar dados relevantes. Parte dos documentos é escaneada e não permite selecionar texto.
- **Quem tem esse problema:** funcionários de uma empresa de topografia que trabalham com documentação em PDF.
- **Como é tratado hoje:** leitura e conferência manual de cada documento.
- **Valor entregue:** transforma PDFs digitais e escaneados em texto utilizável, identifica a qualidade da leitura e produz uma análise rastreável, reduzindo o esforço de revisão manual.

---

## Users & Actors

| Ator | Descrição | Nível técnico | Escala aproximada |
|---|---|---:|---:|
| PostgreSQL | Fornece os PDFs pendentes e recebe o resultado do processamento. | Sistema externo | — |
| Serviço de processamento | Executa o fluxo autônomo: busca PDFs, extrai texto, registra qualidade e grava os resultados. | Sistema interno | Uma máquina |
| LLM local de 7B | Lê o conteúdo produzido e aplica o prompt existente para resumir e extrair informações. | Sistema interno | Um modelo local compartilhado |

<!-- Include external systems that act on the product as actors too. -->

---

## Goals & Success

**Objetivos do produto:**
1. Buscar PDFs pendentes diretamente no banco de dados e processá-los de forma autônoma, sem intervenção humana.
2. Converter texto nativo e imagens de documentos em conteúdo textual estruturado, preservando relatórios de qualidade em JSON e o texto em Markdown.
3. Usar um LLM local para resumir o conteúdo e extrair as informações definidas no prompt, sempre indicando o arquivo e a página de origem.
4. Gravar os resultados e as informações de rastreabilidade no banco de dados.
5. Proteger documentos e dados sensíveis, mantendo OCR e LLM no ambiente local.

**Sucesso será medido por:** cada processamento produzir um relatório JSON com a confiança de OCR por página; esse relatório será o parâmetro para determinar se a leitura foi bem-sucedida e se requer novo processamento ou revisão.

---

## Scope

- **Primeira versão:** um processo por linha de comando que obtém uma quantidade de PDFs do banco de dados, executa uma única passagem de OCR em 600 DPI e a geração de conteúdo, envia o texto, relatórios JSON, resumo e metadados de origem ao banco, e opera com LLM local.
- **Fora do escopo atual:** interface gráfica ou web, envio de conteúdo a APIs de LLM externas e entrada/saída por pastas como fluxo operacional principal.
- **Visão de longo prazo:** ainda não definida.

---

## Context & Constraints

- **Ambiente:** uma máquina Windows executará o serviço de forma autônoma.
- **Privacidade:** os documentos contêm dados sensíveis; OCR e LLM devem operar localmente. O LLM local poderá ter aproximadamente 12B parâmetros.
- **Processamento de OCR:** todos os PDFs serão processados uma única vez em 600 DPI. Não haverá seleção de DPI nem reprocessamento automático em 300 ou 400 DPI.
- **Custo:** o orçamento deve ser o menor possível; não há orçamento definido.
- **Integração obrigatória:** PostgreSQL que armazena PDFs e receberá os resultados, acessado por parâmetros convencionais de servidor, porta, usuário, credenciais e banco de dados.
- **Origem e destino dos dados:** a tabela de origem é `midia` e guarda uma URL para cada PDF. O serviço baixa uma quantidade configurável de arquivos e grava Markdown, JSON, resumo, status, CPF, nome do proprietário e demais dados extraídos pelo LLM em novas colunas da própria tabela.
- **PDFs duplicados:** registros distintos de `midia` podem apontar para PDFs idênticos. O serviço calculará o hash SHA-256 dos bytes originais baixados. Quando encontrar um resultado concluído para o mesmo hash e a mesma versão de processamento, copiará os resultados para as colunas do registro atual, sem repetir OCR ou LLM. Cada registro continuará com seus próprios dados completos para consulta direta pelos funcionários.
- **Rastreabilidade de duplicidade:** `pdf_sha256` será gravado para comprovar identidade byte a byte. Colunas técnicas de status, tentativas, erro, data e versão do processamento permitirão auditar o reaproveitamento e solicitar novo processamento quando o PDF ou a configuração do pipeline mudar.
- **Execução e falhas:** o gatilho do PostgreSQL deve apenas criar ou notificar um trabalho; o serviço CLI externo e contínuo no Windows executará OCR e LLM. Cada trabalho terá status no banco. Em caso de erro, haverá uma única nova tentativa automática; se ela falhar, o status será `falhou`.
- **Notificação:** o serviço será acordado pelo PostgreSQL e também verificará periodicamente trabalhos pendentes como mecanismo de segurança.
- **Reserva de trabalho:** a reserva de um trabalho pendente será atômica, para impedir que o mesmo PDF seja processado em duplicidade.
- **Atomicidade de resultados:** se qualquer etapa falhar, os resultados parciais não serão confirmados no banco. O trabalho será abortado e executado mais uma vez; se falhar novamente, o status será atualizado para `falhou`, com o erro registrado.
- **Consulta de falhas:** uma pessoa poderá consultar o registro posteriormente. Quando houver falha definitiva, verá que o arquivo não foi processado, a URL do PDF e o motivo do erro; não haverá resumo ou extração incompleta apresentada como conclusão.
- **Reprocessamento por alteração:** um PDF já processado deverá ser processado novamente quando for alterado ou substituído.
- **Detecção de alteração:** a inserção de um PDF ou a atualização da coluna que armazena o arquivo criará um novo trabalho. O sistema que alimenta o banco não deve atualizar essa coluna quando o conteúdo do PDF não tiver mudado.
- **Base existente:** o pipeline Python atual de OCR, avaliação de confiança e geração de conteúdo é preservado como ponto de partida.
- **Premissas:** já existe um prompt para o LLM extrair as informações necessárias; o acionamento desejado é por gatilho no PostgreSQL.

---

## Open Questions

| # | Questão | Responsável | Estado |
|---|---|---|---|
| 1 | Quais serão os nomes e tipos exatos das colunas de URL, Markdown, JSON, resumo, CPF, proprietário, `pdf_sha256`, status, erro e metadados na tabela `midia` do PostgreSQL? | Equipe do projeto | Aberta |
| 2 | Como o serviço recuperará um trabalho que permaneceu em `processando` após uma queda ou interrupção? | Equipe do projeto | Aberta |
| 3 | Quais campos exatos o prompt atual precisa extrair e qual formato o PostgreSQL espera para eles? | Equipe do projeto | A validar no prompt |
| 4 | Qual meta de desempenho será definida após a primeira execução mensurável? | Equipe do projeto | Adiada |
