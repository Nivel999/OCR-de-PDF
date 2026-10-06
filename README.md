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

O campo `confianca` dos relatórios ajuda a achar páginas problemáticas: abaixo de ~70% vale olhar.

## Resumos com LLM (`--llm`)

- `ollama` — LLM local (alvo do projeto). Instale o [Ollama](https://ollama.com), `ollama pull qwen2.5:7b`.
  Textos maiores que `--tamanho-bloco` (padrão 12000 caracteres) são resumidos em partes e depois combinados,
  para caber no contexto de modelos 7B.
- `anthropic` — Claude via API, para comparar qualidade (`pip install anthropic` e `ANTHROPIC_API_KEY`).
- `nenhum` — padrão; só extrai o texto.
