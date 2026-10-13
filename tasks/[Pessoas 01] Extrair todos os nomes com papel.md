---
status: To test
assignee: davi
due:
priority: High
type: 💬 Feature request
phase:
---

# [Pessoas 01] Extrair todos os nomes com papel

Decisão de reunião: usar todos os proprietários do documento, não só o principal
(ver ARD-04).

## Feito

- A LLM lista todos os nomes de cada página, com CPF/CNPJ e papel
  (`proprietario`, `proprietario_anterior`, `conjuge`, `adquirente`, `transmitente`,
  `credor`, `devedor`, `procurador`, `confrontante`, `oficial_cartorio`, `testemunha`
  ou `outro` + `descricao_papel`).
- Nova coluna `cadastro.midia.an5_pessoas` (jsonb), criada por `sql/003_an5_pessoas.sql`.
- `an5_referencia` ganha a linha "Demais pessoas"; `nome_proprietario` e `cpf_cnpj`
  passam a sair da lista de pessoas.
- Saída temporária de análise no modo `--banco`: `saida/banco/midia-<id>/` com
  `banco.json`, `texto.txt`, `relatorio.json` (e `extracao.json`/`resumo.md` com LLM).
  Desligável com `--sem-saida-analise`; será removida após a validação.

## Testes executados (2026-10-13)

- `003_an5_pessoas.sql` aplicado no `dnit_teste` (coluna jsonb criada).
- Mídias 757–761 processadas sem LLM em 101 s: todas `concluido`, saída de análise
  gerada. `an5_pessoas` fica NULL até haver LLM.

## Como testar

1. Rodar `sql/003_an5_pessoas.sql` no banco de teste (`psql -f`).
2. Voltar mídias de matrícula para a fila (`an5_status='pendente'`, `an5_tentativas=0`).
3. `run.py --banco --lote N --llm ollama --modelo <modelo> --analise-imovel`.
4. Conferir `an5_pessoas` e `an5_referencia` contra o PDF (ou `saida/banco/midia-<id>/`).

## Próximo

- [Pessoas 02] Nome + CPF do proprietário do Memorial INCRA via API (aguardando
  a explicação de como a API funciona).
