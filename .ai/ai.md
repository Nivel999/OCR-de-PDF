# OCR de PDF e Texto — AI Context Index

Este arquivo é o ponto de entrada para agentes que trabalham neste repositório.
Leia-o primeiro e, em seguida, consulte o documento específico indicado abaixo.

## Projeto em resumo

**Sistema:** processamento local de PDFs que extrai texto nativo ou por OCR,
classifica a qualidade de cada página e pode gerar resumos e análise documental de
imóveis. Uma interface web em React está planejada para acompanhar uploads,
progresso e a qualidade de leitura por página.

**Usuários principais:** pessoas que precisam digitalizar, revisar ou analisar
documentos PDF, especialmente documentação imobiliária.

**Stack atual:** Python, PyMuPDF, Tesseract, OpenCV, NumPy e Pillow. A arquitetura
da interface React e sua integração com o processamento ainda serão definidos no
kickoff.

**Fonte de verdade:** Markdown versionado neste repositório. Os documentos de
produto ficam em .ai/docs/, o índice em docs/documents-hub.md e as tarefas em
tasks/.

**Memória do projeto:** lore — workspace e projeto OCR de Pdf e Texto. A conexão
é configurada por máquina, fora deste repositório; veja
[workflows/project-memory.md](workflows/project-memory.md).

## Mapa de navegação

| Assunto | Arquivo |
|---|---|
| Início guiado do projeto | [workflows/project-kickoff.md](workflows/project-kickoff.md) |
| Visão do sistema | [docs/system-description.md](docs/system-description.md) |
| Requisitos | [docs/SRS.md](docs/SRS.md) |
| Casos de uso e fluxos | [docs/use-cases.md](docs/use-cases.md) |
| Modelo de dados | [docs/data-model.md](docs/data-model.md) |
| Wireframes | [docs/wireframes.md](docs/wireframes.md) |
| Arquitetura e decisões | [architecture.md](architecture.md) e [docs/ARD.md](docs/ARD.md) |
| Diretrizes de interface | [ui_guidelines.md](ui_guidelines.md) e [docs/design-doc.md](docs/design-doc.md) |
| Convenções de código | [coding_conventions.md](coding_conventions.md) |
| Tarefas e documentos locais | [workflows/notion-workflow.md](workflows/notion-workflow.md) |
| Fila de tarefas | [workflows/task-queue.md](workflows/task-queue.md) |

## Decisões registradas

- Documentação e tarefas usam Markdown local e são versionadas no repositório.
- O motor OCR Python existente é preservado como base funcional.
- A interface React é uma direção de produto confirmada; stack detalhada,
  hospedagem e integração serão decididas no kickoff.
- Execuções autônomas não estão habilitadas.

## Regras obrigatórias

1. Não invente requisitos, arquitetura, stack ou decisões de produto: registre
   dúvidas e obtenha confirmação do usuário.
2. architecture.md e docs/ARD.md são a fonte de verdade para decisões
   estruturais; atualize-os quando uma decisão mudar.
3. Antes de alterar código, leia coding_conventions.md; antes de alterar a UI,
   leia também ui_guidelines.md.
4. Toda tarefa implementada vai para To test; apenas o usuário pode confirmá-la
   como Done.
5. Meça antes de afirmar desempenho, tamanho, causa ou melhoria.
