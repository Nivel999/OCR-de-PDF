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
PAPEIS_PESSOA = {
    "proprietario": "proprietário",
    "proprietario_anterior": "proprietário anterior",
    "conjuge": "cônjuge",
    "adquirente": "adquirente",
    "transmitente": "transmitente",
    "credor": "credor",
    "devedor": "devedor",
    "procurador": "procurador",
    "confrontante": "confrontante",
    "oficial_cartorio": "oficial de cartório",
    "testemunha": "testemunha",
    "outro": "outro",
}

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


class Backend(Protocol):
    def gerar(self, sistema: str, mensagem: str) -> str: ...


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


def consolidar_pessoas(pessoas: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Une as ocorrências da mesma pessoa no mesmo papel, acumulando as páginas em que aparece.

    A identidade é o nome normalizado (sem acento, caixa e espaços extras); o CPF/CNPJ e a evidência
    vêm da primeira ocorrência que os tiver. Uma pessoa com dois papéis gera dois itens.
    """
    grupos: dict[tuple[str, str], dict[str, object]] = {}
    for pessoa in pessoas:
        nome = _texto(pessoa.get("nome"))
        if not nome:
            continue
        papel = _texto(pessoa.get("papel")) or "outro"
        grupo = grupos.setdefault(
            (_normalizar_nome(nome), papel),
            {"nome": nome, "cpf_cnpj": None, "papel": papel, "descricao_papel": None,
             "paginas": [], "evidencia": ""},
        )
        for chave in ("cpf_cnpj", "descricao_papel", "evidencia"):
            if not grupo[chave] and pessoa.get(chave):
                grupo[chave] = pessoa[chave]
        pagina = pessoa.get("pagina")
        if isinstance(pagina, int) and pagina not in grupo["paginas"]:
            grupo["paginas"].append(pagina)
    for grupo in grupos.values():
        grupo["paginas"].sort()
    return list(grupos.values())


def extrair_dados_imovel(
    arquivo: str, paginas: Iterable[tuple[int, str]], backend: Backend
) -> dict[str, object]:
    """Consulta a LLM por página e anexa a citação determinística de arquivo/página a cada achado."""
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

        # Proprietário e CPF/CNPJ saem da lista de pessoas, para a checagem de consistência entre PDFs.
        pessoas_pagina = _itens_pessoas(resultado.get("pessoas"), arquivo, pagina)
        pessoas.extend(pessoas_pagina)
        for pessoa in pessoas_pagina:
            if pessoa["papel"] != "proprietario":
                continue
            fonte = {"arquivo": arquivo, "pagina": pagina, "evidencia": pessoa["evidencia"]}
            campos["nome_proprietario"].append({"valor": pessoa["nome"], **fonte})
            if pessoa["cpf_cnpj"]:
                campos["cpf_cnpj"].append({"valor": pessoa["cpf_cnpj"], **fonte})

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

    return {
        "arquivo": arquivo,
        "campos": campos,
        "pessoas": consolidar_pessoas(pessoas),
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
