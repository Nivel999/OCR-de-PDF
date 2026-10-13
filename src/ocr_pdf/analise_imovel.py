"""Extração estruturada e checagem de consistência de documentos de imóveis."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from typing import Any, Protocol


CAMPOS_PRIORITARIOS = (
    "nome_proprietario",
    "cpf_cnpj",
    "nome_propriedade",
    "classificacao_dominio",
    "matricula_imovel",
    "codigo_incra_sncr",
    "area_total_imovel",
)

# Papel de cada nome citado no documento -> rótulo legível. "outro" recebe a descrição livre da LLM.
# A ordem é a prioridade usada para ordenar an5_pessoas: dono e partes do imóvel primeiro, ruído no fim.
PAPEIS_PESSOA = {
    "proprietario_atual": "proprietário atual",  # definido pela análise do documento inteiro
    "proprietario": "citado como proprietário",
    "conjuge": "cônjuge",
    "adquirente": "adquirente",
    "transmitente": "transmitente",
    "proprietario_anterior": "proprietário anterior",
    "credor": "credor",
    "devedor": "devedor",
    "procurador": "procurador",
    "confrontante": "confrontante",
    "testemunha": "testemunha",
    "oficial_cartorio": "oficial de cartório",
    "outro": "outro",
}
_PRIORIDADE_PAPEL = {papel: posicao for posicao, papel in enumerate(PAPEIS_PESSOA)}

PROMPT_SISTEMA = """Você extrai dados de documentos imobiliários brasileiros.
Use exclusivamente o conteúdo da página fornecida. Não deduza, complete, corrija nem invente valores.
Quando um campo não estiver presente, devolva uma lista vazia para ele. A evidência deve ser um trecho
curto, literal e suficiente para conferir o valor no documento. Devolva somente JSON válido."""

PROMPT_EXTRACAO = """Analise a página {pagina} do arquivo `{arquivo}` e devolva exatamente este JSON:
{{
  "pessoas": [{{"nome": "", "cpf_cnpj": "", "papel": "", "descricao_papel": "", "evidencia": ""}}],
  "campos": {{
    "nome_propriedade": [{{"valor": "", "evidencia": ""}}],
    "classificacao_dominio": [{{"valor": "", "evidencia": ""}}],
    "matricula_imovel": [{{"valor": "", "evidencia": ""}}],
    "codigo_incra_sncr": [{{"valor": "", "evidencia": ""}}],
    "area_total_imovel": [{{"valor": "", "evidencia": ""}}]
  }},
  "demais_atributos_relevantes": [{{"nome": "", "valor": "", "evidencia": ""}}]
}}

Em `pessoas`, liste TODOS os nomes de pessoas físicas e jurídicas citados na página (proprietários,
cônjuges, vendedores, compradores, bancos, procuradores, confrontantes, oficiais, testemunhas etc.),
um item por pessoa e por papel. Copie o nome e o CPF/CNPJ como escritos (CPF/CNPJ vazio se não houver
na página). Em `papel`, use exatamente um destes códigos, conforme o que a página diz da pessoa:
- proprietario: citada como proprietária, titular do domínio, condômina ou coproprietária do imóvel;
- proprietario_anterior: citada como antiga/anterior proprietária;
- conjuge: cônjuge ou companheiro(a) de outra pessoa citada;
- adquirente: quem adquire o imóvel ou fração no ato (comprador, donatário, herdeiro, outorgado);
- transmitente: quem transmite o imóvel ou fração no ato (vendedor, doador, outorgante);
- credor / devedor: partes de hipoteca, alienação fiduciária, penhora ou outro ônus;
- procurador: representa outra pessoa;
- confrontante: dono de imóvel vizinho citado nas confrontações;
- oficial_cartorio: oficial, registrador, escrevente ou tabelião;
- testemunha: testemunha do ato;
- outro: qualquer outro papel; descreva-o em `descricao_papel`.

Em `demais_atributos_relevantes`, registre somente atributos relevantes que estejam explícitos, como
município/UF, CAR, CCIR, NIRF, ITR, cartório, confrontações, ônus, restrições ou fração ideal.
O campo `classificacao_dominio` deve trazer a classificação literal encontrada (por exemplo, particular,
privado ou público); não tente classificá-la se o documento não a disser. Em `area_total_imovel`,
copie a linha da área total exatamente como escrita, com rótulo, sistema de referência e unidade
(ex.: "Área (Sistema Geodésico Local): 35,2723 ha").

<pagina>
{texto}
</pagina>"""


PROMPT_PROPRIETARIOS = """Abaixo está o texto completo do arquivo `{arquivo}`, página a página. Identifique
os PROPRIETÁRIOS ATUAIS do imóvel e devolva exatamente este JSON:
{{
  "proprietarios_atuais": [{{"nome": "", "cpf_cnpj": "", "fracao": "", "ato": "", "pagina": 0, "evidencia": ""}}],
  "observacoes": ""
}}

Regras:
- Em matrícula, siga em ordem a cadeia de registros (R-1, R-2, ...) e averbações. Proprietário atual é
  quem adquiriu o imóvel ou uma fração dele no registro de transmissão mais recente e não a transmitiu
  depois. Quem vendeu, doou, integralizou ou de outra forma transmitiu deixa de ser proprietário. Inclua
  todos os coproprietários e os cônjuges que figurem como adquirentes.
- Desapropriação ou transferência de apenas parte da área não muda os proprietários do restante;
  registre-a em `observacoes`.
- Em memorial descritivo do INCRA/SIGEF, ou outro documento com o campo "Proprietário", use esse campo
  exatamente como escrito, mesmo que esteja mascarado.
- `fracao`: a fração ou parte ideal, se estiver escrita; senão, vazio. `ato`: o registro de aquisição
  (ex.: "R-13 adjudicação compulsória"). `pagina`: a página onde está esse ato. Copie nome e CPF/CNPJ
  como escritos.
- Em `observacoes`, registre o que afeta a titularidade: óbito de proprietário, matrícula encerrada ou
  transferida, ônus vigentes, leituras do OCR duvidosas em nomes ou números.
- Se não for possível determinar os proprietários atuais, devolva a lista vazia e explique em `observacoes`.

<documento>
{texto}
</documento>"""


class Backend(Protocol):
    def gerar(self, sistema: str, mensagem: str, formato_json: bool = False) -> str: ...


def _objeto_json(resposta: str) -> dict[str, Any]:
    resposta = resposta.strip()
    if resposta.startswith("```"):
        resposta = re.sub(r"^```(?:json)?\s*|\s*```$", "", resposta, flags=re.IGNORECASE)
    inicio, fim = resposta.find("{"), resposta.rfind("}")
    if inicio < 0 or fim < inicio:
        raise ValueError("A LLM não devolveu um objeto JSON.")
    valor = json.loads(resposta[inicio : fim + 1])
    if not isinstance(valor, dict):
        raise ValueError("A resposta da LLM não é um objeto JSON.")
    return valor


def _texto(valor: object) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _itens_campo(itens: object, arquivo: str, pagina: int) -> list[dict[str, object]]:
    if not isinstance(itens, list):
        return []
    normalizados = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        valor, evidencia = _texto(item.get("valor")), _texto(item.get("evidencia"))
        if valor:
            normalizados.append(
                {"valor": valor, "arquivo": arquivo, "pagina": pagina, "evidencia": evidencia}
            )
    return normalizados


def _normalizar_nome(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.casefold().split())


def _itens_pessoas(itens: object, arquivo: str, pagina: int) -> list[dict[str, object]]:
    if not isinstance(itens, list):
        return []
    pessoas = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        nome = _texto(item.get("nome"))
        if not nome:
            continue
        papel, descricao = _texto(item.get("papel")).casefold(), _texto(item.get("descricao_papel"))
        if papel not in PAPEIS_PESSOA:
            # Papel fora da lista: preserva o que a LLM escreveu como descrição.
            descricao = descricao or papel
            papel = "outro"
        pessoas.append(
            {
                "nome": nome,
                "cpf_cnpj": _texto(item.get("cpf_cnpj")) or None,
                "papel": papel,
                "descricao_papel": descricao or None,
                "arquivo": arquivo,
                "pagina": pagina,
                "evidencia": _texto(item.get("evidencia")),
            }
        )
    return pessoas


def _documento_completo(cpf_cnpj: object) -> str | None:
    """Dígitos do CPF (11) ou CNPJ (14); None se mascarado ou lido com dígitos a mais/menos."""
    digitos = re.sub(r"\D", "", cpf_cnpj) if isinstance(cpf_cnpj, str) else ""
    return digitos if len(digitos) in (11, 14) else None


def consolidar_pessoas(pessoas: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Une as ocorrências da mesma pessoa no mesmo papel, acumulando as páginas em que aparece.

    A identidade é o CPF/CNPJ completo (só dígitos), quando houver; senão, o nome normalizado (sem
    acento, caixa e espaços extras). Um nome sem CPF numa página herda o CPF que o mesmo nome tiver em
    outra, se for um só. Assim, grafias diferentes do OCR com o mesmo CPF viram uma pessoa; o primeiro
    nome é mantido e os demais vão para ``nomes_alternativos``. CPF/CNPJ e evidência vêm da primeira
    ocorrência que os tiver. Uma pessoa com dois papéis gera dois itens. O resultado sai na ordem de
    ``PAPEIS_PESSOA`` (proprietário atual primeiro) e, em cada papel, na ordem do texto.
    """
    pessoas = [p for p in pessoas if _texto(p.get("nome"))]
    documentos_por_nome: dict[str, set[str]] = {}
    for pessoa in pessoas:
        documento = _documento_completo(pessoa.get("cpf_cnpj"))
        if documento:
            documentos_por_nome.setdefault(_normalizar_nome(_texto(pessoa["nome"])), set()).add(documento)

    grupos: dict[tuple[str, str], dict[str, object]] = {}
    for pessoa in pessoas:
        nome = _texto(pessoa["nome"])
        nome_normalizado = _normalizar_nome(nome)
        documento = _documento_completo(pessoa.get("cpf_cnpj"))
        if documento is None and len(documentos_por_nome.get(nome_normalizado, ())) == 1:
            documento = next(iter(documentos_por_nome[nome_normalizado]))
        identidade = f"doc:{documento}" if documento else f"nome:{nome_normalizado}"
        papel = _texto(pessoa.get("papel")) or "outro"
        grupo = grupos.setdefault(
            (identidade, papel),
            {"nome": nome, "cpf_cnpj": None, "papel": papel, "descricao_papel": None,
             "paginas": [], "evidencia": ""},
        )
        if _normalizar_nome(grupo["nome"]) != nome_normalizado:
            alternativos = grupo.setdefault("nomes_alternativos", [])
            if all(_normalizar_nome(n) != nome_normalizado for n in alternativos):
                alternativos.append(nome)
        for chave in ("cpf_cnpj", "descricao_papel", "evidencia"):
            if not grupo[chave] and pessoa.get(chave):
                grupo[chave] = pessoa[chave]
        pagina = pessoa.get("pagina")
        if isinstance(pagina, int) and pagina not in grupo["paginas"]:
            grupo["paginas"].append(pagina)
    for grupo in grupos.values():
        grupo["paginas"].sort()
    # Ordena pela prioridade do papel; dentro do mesmo papel, mantém a ordem de aparição (sort estável).
    return sorted(grupos.values(), key=lambda grupo: _PRIORIDADE_PAPEL.get(grupo["papel"], len(_PRIORIDADE_PAPEL)))


# Linha do memorial descritivo do INCRA/SIGEF, ex.:
# "Proprietário(a): XXXXXX RUI XXXXXX                CPF:  ***.132.459**"
_LINHA_PROPRIETARIO_MEMORIAL = re.compile(
    r"^[ \t]*Propriet[áa]rio\(a\):[ \t]*(?P<nome>\S.*?)(?:[ \t]{2,}(?:CPF|CNPJ):[ \t]*(?P<documento>\S+))?[ \t]*$",
    re.MULTILINE,
)


def proprietarios_memorial_incra(arquivo: str, paginas: list[tuple[int, str]]) -> list[dict[str, object]]:
    """Lê o campo "Proprietário(a)" do memorial do INCRA/SIGEF direto do texto, sem LLM.

    O memorial já informa o proprietário atual; copiá-lo por regex evita que a LLM altere o nome
    mascarado (ex.: "XXXXXXS" virando "XXXXXS") ou se recuse a usá-lo.
    """
    proprietarios = []
    for pagina, texto in paginas:
        for achado in _LINHA_PROPRIETARIO_MEMORIAL.finditer(texto):
            proprietarios.append(
                {
                    "nome": achado["nome"].strip(),
                    "cpf_cnpj": achado["documento"],
                    "papel": "proprietario_atual",
                    "descricao_papel": "Memorial descritivo INCRA/SIGEF, campo Proprietário(a)",
                    "arquivo": arquivo,
                    "pagina": pagina,
                    "evidencia": " ".join(achado.group(0).split()),
                }
            )
    return proprietarios


def identificar_proprietarios_atuais(
    arquivo: str, paginas: list[tuple[int, str]], backend: Backend
) -> tuple[list[dict[str, object]], str, list[str]]:
    """Uma chamada com o documento inteiro: a LLM segue a cadeia de registros e diz quem é dono hoje.

    Devolve as pessoas com papel ``proprietario_atual``, as observações sobre a titularidade e alertas.
    """
    texto = "\n\n".join(
        f"--- Página {pagina} ---\n{conteudo}" for pagina, conteudo in paginas if conteudo.strip()
    )
    if not texto:
        return [], "", []
    try:
        resultado = _objeto_json(
            backend.gerar(
                PROMPT_SISTEMA, PROMPT_PROPRIETARIOS.format(arquivo=arquivo, texto=texto), formato_json=True
            )
        )
    except (ValueError, json.JSONDecodeError) as erro:
        return [], "", [f"Proprietários atuais: resposta estruturada inválida da LLM ({erro})."]

    paginas_validas = {pagina for pagina, _ in paginas}
    proprietarios = []
    itens = resultado.get("proprietarios_atuais")
    for item in itens if isinstance(itens, list) else []:
        if not isinstance(item, dict) or not _texto(item.get("nome")):
            continue
        ato, fracao = _texto(item.get("ato")), _texto(item.get("fracao"))
        detalhes = [ato] * bool(ato) + [f"fração {fracao}"] * bool(fracao)
        pagina = item.get("pagina")
        proprietarios.append(
            {
                "nome": _texto(item["nome"]),
                "cpf_cnpj": _texto(item.get("cpf_cnpj")) or None,
                "papel": "proprietario_atual",
                "descricao_papel": "; ".join(detalhes) or None,
                "arquivo": arquivo,
                # A página vem da LLM; só é aceita se existir no documento.
                "pagina": pagina if isinstance(pagina, int) and pagina in paginas_validas else None,
                "evidencia": _texto(item.get("evidencia")),
            }
        )
    return proprietarios, _texto(resultado.get("observacoes")), []


def extrair_dados_imovel(
    arquivo: str, paginas: Iterable[tuple[int, str]], backend: Backend
) -> dict[str, object]:
    """Consulta a LLM por página e, ao final, uma vez com o documento inteiro para os proprietários atuais.

    Anexa a citação determinística de arquivo/página a cada achado.
    """
    paginas = list(paginas)
    campos: dict[str, list[dict[str, object]]] = {campo: [] for campo in CAMPOS_PRIORITARIOS}
    pessoas: list[dict[str, object]] = []
    atributos: list[dict[str, object]] = []
    alertas: list[str] = []

    for pagina, texto in paginas:
        if not texto.strip():
            continue
        try:
            resposta = backend.gerar(
                PROMPT_SISTEMA,
                PROMPT_EXTRACAO.format(arquivo=arquivo, pagina=pagina, texto=texto),
                formato_json=True,
            )
            resultado = _objeto_json(resposta)
        except (ValueError, json.JSONDecodeError) as erro:
            alertas.append(f"Página {pagina}: resposta estruturada inválida da LLM ({erro}).")
            continue

        dados = resultado.get("campos", {})
        if not isinstance(dados, dict):
            alertas.append(f"Página {pagina}: a chave 'campos' não é um objeto.")
            continue
        for campo in CAMPOS_PRIORITARIOS:
            campos[campo].extend(_itens_campo(dados.get(campo), arquivo, pagina))

        pessoas.extend(_itens_pessoas(resultado.get("pessoas"), arquivo, pagina))

        itens = resultado.get("demais_atributos_relevantes", [])
        if isinstance(itens, list):
            for item in itens:
                if not isinstance(item, dict):
                    continue
                nome, valor, evidencia = (
                    _texto(item.get("nome")),
                    _texto(item.get("valor")),
                    _texto(item.get("evidencia")),
                )
                if nome and valor:
                    atributos.append(
                        {
                            "nome": nome,
                            "valor": valor,
                            "arquivo": arquivo,
                            "pagina": pagina,
                            "evidencia": evidencia,
                        }
                    )

    atuais = proprietarios_memorial_incra(arquivo, paginas)
    if atuais:
        observacoes = "Proprietário lido do campo \"Proprietário(a)\" do memorial do INCRA/SIGEF, sem LLM."
        if any("XX" in p["nome"] or "*" in (p["cpf_cnpj"] or "") for p in atuais):
            observacoes += " Nome ou CPF/CNPJ mascarado no documento."
    else:
        atuais, observacoes, alertas_atuais = identificar_proprietarios_atuais(arquivo, paginas, backend)
        alertas.extend(alertas_atuais)
    pessoas = atuais + pessoas

    # Proprietário e CPF/CNPJ (consistência entre PDFs) vêm dos proprietários atuais; se a análise do
    # documento inteiro não os identificou, usa quem as páginas citam como proprietário.
    papel_dono = "proprietario_atual" if atuais else "proprietario"
    for pessoa in pessoas:
        if pessoa["papel"] != papel_dono:
            continue
        fonte = {"arquivo": arquivo, "pagina": pessoa["pagina"], "evidencia": pessoa["evidencia"]}
        campos["nome_proprietario"].append({"valor": pessoa["nome"], **fonte})
        if pessoa["cpf_cnpj"]:
            campos["cpf_cnpj"].append({"valor": pessoa["cpf_cnpj"], **fonte})

    return {
        "arquivo": arquivo,
        "campos": campos,
        "pessoas": consolidar_pessoas(pessoas),
        "observacoes_titularidade": observacoes,
        "demais_atributos_relevantes": atributos,
        "alertas": alertas,
    }


def _chave_valor(campo: str, valor: str) -> str:
    valor = " ".join(valor.casefold().split())
    if campo == "cpf_cnpj":
        return re.sub(r"\D", "", valor)
    if campo == "classificacao_dominio":
        sinonimos = {"particular": "privado", "privada": "privado", "privada/particular": "privado"}
        return sinonimos.get(valor, valor)
    return valor


def consolidar_consistencia(extracoes: Iterable[dict[str, object]]) -> dict[str, object]:
    """Compara os valores extraídos de todos os PDFs e mantém a proveniência de cada ocorrência."""
    por_campo: dict[str, list[dict[str, object]]] = {campo: [] for campo in CAMPOS_PRIORITARIOS}
    atributos: list[dict[str, object]] = []
    alertas: list[str] = []

    for extracao in extracoes:
        campos = extracao.get("campos", {})
        if isinstance(campos, dict):
            for campo in CAMPOS_PRIORITARIOS:
                itens = campos.get(campo, [])
                if isinstance(itens, list):
                    por_campo[campo].extend(item for item in itens if isinstance(item, dict))
        itens_atributos = extracao.get("demais_atributos_relevantes", [])
        if isinstance(itens_atributos, list):
            atributos.extend(item for item in itens_atributos if isinstance(item, dict))
        itens_alertas = extracao.get("alertas", [])
        if isinstance(itens_alertas, list):
            alertas.extend(str(item) for item in itens_alertas)

    consistencia = {}
    for campo, itens in por_campo.items():
        grupos: dict[str, dict[str, object]] = {}
        for item in itens:
            valor = _texto(item.get("valor"))
            if not valor:
                continue
            chave = _chave_valor(campo, valor)
            grupo = grupos.setdefault(chave, {"valor": valor, "fontes": []})
            grupo["fontes"].append(item)

        valores = list(grupos.values())
        status = "nao_encontrado" if not valores else "consistente" if len(valores) == 1 else "divergente"
        consistencia[campo] = {"status": status, "valores": valores}

    return {
        "consistencia": consistencia,
        "demais_atributos_relevantes": atributos,
        "alertas": alertas,
    }
