# OCR de PDF + Resumo com LLM

Lê todos os PDFs de `entrada/`, extrai o texto (nativo ou via OCR com Tesseract) e,
opcionalmente, gera um resumo de cada um com uma LLM.

## Como funciona

Para **cada página** do PDF:

1. Tenta o texto nativo (PyMuPDF). Se a página tem texto de verdade, usa ele — rápido e sem erros.
2. Se a página é imagem (pouco texto, texto ilegível ou coberta por imagem), faz OCR:
   - renderiza a página a 300 DPI;
   - detecta se está girada (90°/180°/270°) e endireita;
   - aplica pré-processamento e roda o Tesseract (`por`); no modo `auto`, testa as estratégias
     em ordem até a confiança passar de 80% e fica com a melhor.

PDFs mistos (algumas páginas digitais, outras escaneadas) funcionam naturalmente.

### Estratégias de pré-processamento (`--estrategia`)

| Estratégia    | Quando usar |
|---------------|-------------|
| `cinza`       | Padrão. O Tesseract 5 (LSTM) binariza internamente e lida bem com marca d'água clara. |
| `marca_dagua` | Remove pixels coloridos (carimbos, marca vermelha/azul) e clareia tons acima de um limiar automático. |
| `otsu`        | Binarização global. Scans com fundo uniforme. |
| `adaptativo`  | Limiar local. Sombras, iluminação irregular, fotos de documento. |

Use `--debug-imagens` para ver em `saida/debug/` exatamente a imagem que foi para o OCR.

## Instalação (Windows)

```powershell
scoop install tesseract          # binário do Tesseract 5
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Os modelos de idioma ficam em `tessdata/` (`por` e `osd`; para outros idiomas, baixe o `.traineddata` correspondente). Para baixar de novo:
`https://github.com/tesseract-ocr/tessdata` (padrão) ou `tessdata_best` (mais preciso, mais lento).

## Uso

```powershell
.venv\Scripts\python run.py                         # processa entrada/ -> saida/
.venv\Scripts\python run.py --debug-imagens         # salva as imagens pré-processadas
.venv\Scripts\python run.py --estrategia marca_dagua --reprocessar
.venv\Scripts\python run.py --forcar-ocr            # ignora texto nativo (ex.: camada OCR antiga ruim)
.venv\Scripts\python run.py --monitorar 30          # vigia a pasta a cada 30s
.venv\Scripts\python run.py --llm ollama --modelo qwen2.5:7b   # gera resumos com LLM local
```

PDFs já processados são pulados (a menos que o PDF mude ou se use `--reprocessar`).

### Saída

```
saida/
  textos/<nome>.txt        texto extraído, com marcadores "--- Página N ---"
  relatorios/<nome>.json   por página: método, motivo, confiança do OCR, estratégia, rotação
  resumos/<nome>.md        resumo (se --llm for usado)
  debug/<nome>/            imagens pré-processadas (se --debug-imagens)
```

O relatório JSON inclui a confiança do OCR por página e uma orientação pronta para interface
em `qualidade_ocr`. As métricas agregadas também listam páginas que exigem revisão e as que
devem ser reprocessadas em um DPI maior.

| Confiança | Faixa no relatório | Interpretação | Próxima ação |
|------------|--------------------|---------------|--------------|
| 90% ou mais | `confiavel` | Scan bem reconhecido. | Nenhuma ação necessária. |
| 80% a 89,9% | `aceitavel` | Texto utilizável, mas dados críticos podem ter erros. | Revisar nomes, datas e valores. |
| 70% a 79,9% | `dificil` | Leitura difícil. | Reprocessar a página em 400 DPI; se ela já estiver em 400 DPI, usar 600 DPI. |
| Abaixo de 70% | `baixa` | OCR pouco confiável. | Reprocessar em 400/600 DPI; em 600 DPI, revisar manualmente ou melhorar o scan. |

O DPI sugerido aparece apenas como recomendação no relatório; o comando atual ainda processa
o PDF inteiro com o DPI escolhido em `--dpi`. Ao terminar um processamento interativo, o
programa lista as páginas abaixo de 80% e pergunta se deve reprocessá-las: primeiro em 400 DPI
e, se continuarem abaixo da régua, em 600 DPI. Se ainda falharem em 600 DPI, exibe um alerta para
revisão manual da página no PDF original. Em execução não interativa, ele não pergunta nem
reprocessa automaticamente.

## Resumos com LLM (`--llm`)

- `ollama` — LLM local (alvo do projeto). Instale o [Ollama](https://ollama.com), `ollama pull qwen2.5:7b`.
  Textos maiores que `--tamanho-bloco` (padrão 12000 caracteres) são resumidos em partes e depois combinados,
  para caber no contexto de modelos 7B.
- `anthropic` — Claude via API, para comparar qualidade (`pip install anthropic` e `ANTHROPIC_API_KEY`).
- `nenhum` — padrão; só extrai o texto.
