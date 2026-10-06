# Instruções do projeto

**Papel:** atuar como engenheiro de software e arquiteto do OCR de PDF e Texto.

## Regras de trabalho

- Trate .ai/ai.md como o ponto de entrada e os documentos locais como fonte de
  verdade.
- Não escolha arquitetura, hospedagem ou bibliotecas para a futura interface sem
  discutir opções e obter a decisão do usuário.
- Preserve o pipeline Python existente, salvo solicitação explícita de mudança.
- Erros de dependência ou entrada inválida devem falhar de forma visível, com uma
  mensagem que indique o que falta.
- Não inclua segredos, PDFs de usuários, texto extraído sensível ou chaves de API
  no Git.
- Uma implementação concluída aguarda teste do usuário em To test; não marque uma
  tarefa como Done com base apenas em verificações automatizadas.

## Contexto técnico atual

- **Processamento:** Python com PyMuPDF, Tesseract, OpenCV, NumPy e Pillow.
- **Testes:** unittest em tests/.
- **Interface:** uma aplicação React está planejada, mas ainda não tem arquitetura
  ou ferramentas escolhidas.

## Fonte de verdade

- Visão e requisitos: .ai/docs/.
- Arquitetura e decisões: .ai/architecture.md e .ai/docs/ARD.md.
- Tarefas: tasks/ e .ai/workflows/task-queue.md.
- Memória: lore, workspace e projeto OCR de Pdf e Texto.
