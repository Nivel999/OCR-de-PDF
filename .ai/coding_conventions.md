# Convenções de código

## Python

- Use Python moderno com anotações de tipo e from __future__ import annotations
  quando necessário para manter consistência com o código existente.
- Mantenha o código de processamento em src/ocr_pdf/; o ponto de entrada é
  run.py e o módulo ocr_pdf.__main__.
- Prefira funções pequenas, nomes em português já consolidados no domínio OCR e
  pathlib.Path para caminhos.
- Erros de dependência ou entrada inválida devem informar claramente o que falta;
  não silencie falhas de OCR ou de processamento.
- Dependências Python devem ser registradas em requirements.txt.

## Testes

- Use unittest em tests/.
- Todo comportamento novo no pipeline deve trazer teste unitário ou justificar
  por que não é testável automaticamente.
- Execute python -m unittest discover -s tests antes de entregar mudanças no
  backend.

## Interface web futura

- Não introduza React, TypeScript, bundler, gerenciador de pacotes ou biblioteca
  de componentes antes da decisão de arquitetura registrada.
- Quando a implementação da UI começar, registre as convenções específicas neste
  arquivo.

## Git e segurança

- Use branches feat/, fix/, chore/ ou docs/ e commits convencionais.
- Não versione arquivos .env, chaves, PDFs de entrada, saídas processadas ou
  dados pessoais extraídos.
