# OCR de PDF, resumo e análise documental de imóveis

Lê todos os PDFs de `entrada/`, extrai o texto (nativo ou via OCR com Tesseract) e,
opcionalmente, gera resumos e uma análise estruturada de documentação imobiliária com LLM.

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
.venv\Scripts\python run.py --llm ollama --modelo qwen2.5:7b --analise-imovel  # análise imobiliária
```

PDFs já processados são pulados (a menos que o PDF mude ou se use `--reprocessar`).

### Saída

```
saida/
  textos/<nome>.txt        texto extraído, com marcadores "--- Página N ---"
  relatorios/<nome>.json   por página: método, motivo, confiança do OCR, estratégia, rotação
  resumos/<nome>.md        resumo (se --llm for usado)
  extracoes/<nome>.json    dados imobiliários com evidência de página (se --analise-imovel)
  consistencia_imovel.json comparação dos dados entre todos os PDFs (se --analise-imovel)
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

O relatório sempre registra o DPI utilizado e a próxima ação recomendada. Ao terminar um
processamento interativo, o programa lista as páginas abaixo de 80% e pergunta se deve
reprocessá-las: primeiro em 400 DPI e, se continuarem abaixo da régua, em 600 DPI. Somente as
páginas indicadas são refeitas. Se ainda falharem em 600 DPI, o programa exibe um alerta para
revisão manual no PDF original. Em execução não interativa, ele não pergunta nem reprocessa
automaticamente; as recomendações continuam no JSON.

## Resumos com LLM (`--llm`)

- `ollama` — LLM local (alvo do projeto). Instale o [Ollama](https://ollama.com), `ollama pull qwen2.5:7b`.
  Textos maiores que `--tamanho-bloco` (padrão 12000 caracteres) são resumidos em partes e depois combinados,
  para caber no contexto de modelos 7B.
- `anthropic` — Claude via API, para comparar qualidade (`pip install anthropic` e `ANTHROPIC_API_KEY`).
- `nenhum` — padrão; só extrai o texto.

## Análise de dados do imóvel (`--analise-imovel`)

`--analise-imovel` exige uma LLM (`--llm ollama` ou `--llm anthropic`). O modo analisa cada
página individualmente e gera uma
extração estruturada dos campos prioritários: nome do proprietário, CPF/CNPJ, nome da
propriedade, classificação do domínio, matrícula e código INCRA/SNCR. Também registra atributos
explícitos relevantes, como área, localização, CAR, CCIR, NIRF, ITR, cartório, confrontações,
ônus e restrições.

Cada valor salvo tem `arquivo`, `pagina` e um trecho de `evidencia`; o arquivo e a página são
anexados pelo programa, não deduzidos pelo modelo. Ao fim do lote,
`consistencia_imovel.json` agrupa os valores encontrados e marca cada campo como:

- `consistente`: os arquivos que possuem o campo concordam;
- `divergente`: foram encontrados valores diferentes — use as fontes listadas para conferir;
- `nao_encontrado`: nenhum PDF trouxe o campo de forma explícita.

Exemplo de uma evidência produzida em `extracoes/<nome>.json`:

```json
{
  "valor": "12.345",
  "arquivo": "matricula.pdf",
  "pagina": 2,
  "evidencia": "Matrícula nº 12.345"
}
```

O modelo é instruído a não inferir dados ausentes. Se a resposta não estiver no formato esperado,
o arquivo de extração registra um alerta para a página em vez de transformar uma suposição em dado.

Prefira `--llm ollama` para manter os PDFs e seus dados pessoais processados localmente. Ao usar
`--llm anthropic`, o texto extraído — incluindo eventuais CPF/CNPJ — é enviado à API escolhida.

## Worker PostgreSQL

O modo `--banco` transforma a aplicação em um worker: busca em `cadastro.midia` uma
mídia com `an5_status = 'pendente'`, baixa o PDF de `link`, processa localmente e grava
o resultado nas colunas `an5_*` da própria `cadastro.midia`. Crie as colunas com
`sql/001_processamento_pdf.sql` (idempotente, não apaga dados). A URL de conexão não é
versionada; defina-a na sessão do PowerShell antes de executar:

```powershell
$env:OCR_PDF_DATABASE_URL = 'postgresql://USUARIO:SENHA@HOST:5432/BANCO'
.venv\Scripts\python run.py --banco --lote 1 --llm ollama --modelo qwen2.5:7b --analise-imovel
```

Só entram no processamento as mídias marcadas explicitamente como `pendente`.
O tipo do documento vem de `cadastro.midia.tipo_documento` (domínio
`dominio.tipo_documento`): **12 = Memorial Descritivo do INCRA** e **13 = Matrícula**
passam pelo pipeline (páginas com texto nativo são lidas direto, as escaneadas vão para
OCR). `sql/002_enfileirar_documentos.sql` mostra quantas mídias de cada tipo existem e
as enfileira. O worker só aceita os tipos de `--tipo-documento` (padrão 12 e 13), mesmo
que outra mídia esteja pendente.

| Coluna | Conteúdo |
|---|---|
| `an5_matricula`, `an5_nome_imovel` | Primeiro valor extraído pela LLM (`--analise-imovel`). |
| `an5_area_total_imovel` | Área total exatamente como escrita, ex.: `Área (Sistema Geodésico Local): 35,2723 ha`. |
| `an5_confianca_media` | Confiança média do OCR (0–100); vazio se o PDF só tem texto nativo. |
| `an5_descricao` | Explicação da confiança (faixas, páginas para revisão) ou a mensagem de erro. |
| `an5_referencia` | Todos os valores extraídos, com a página de origem, e o resumo da LLM. |
| `an5_status` | `pendente`, `processando`, `concluido`, `reutilizado` ou `falha`. |
| `an5_tentativas` | Quantas vezes o processamento foi iniciado. |
| `an5_data_transformacao` | Data/hora do último processamento. |
| `an5_pdf_sha256` | Hash do PDF; um PDF idêntico já concluído tem o resultado copiado (`reutilizado`). |

Use `--monitorar 30` para manter o worker ativo, verificando a cada 30 segundos.
O worker usa OCR em 600 DPI e reserva trabalho com segurança para permitir múltiplas
instâncias. Após o primeiro erro a mídia volta para `pendente`; no segundo fica em
`falha`. Para tentar de novo, volte `an5_status` para `pendente` e `an5_tentativas` para 0. Se o worker for interrompido no meio, a mídia fica em `processando` e
também precisa voltar para `pendente` manualmente.

Antes de instalar uma LLM, é possível validar somente o OCR em uma mídia de teste:

```powershell
.venv\Scripts\python run.py --banco --id-midia 123
```

Sem LLM, só são gravados confiança, descrição, hash, status e data; os campos do
imóvel ficam vazios.
