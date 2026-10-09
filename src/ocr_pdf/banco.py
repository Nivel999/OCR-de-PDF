"""Fila e persistência do processamento de PDFs nas colunas ``an5_*`` de ``cadastro.midia``."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ARQUIVO_ENV_LOCAL = Path(__file__).resolve().parents[2] / ".env"
STATUS_COM_RESULTADO = ["concluido", "reutilizado"]

# Valores de cadastro.midia.tipo_documento (FK dominio.tipo_documento).
TIPO_DOCUMENTO_MEMORIAL_INCRA = 12  # pode ganhar extração própria no futuro
TIPO_DOCUMENTO_MATRICULA = 13
TIPOS_DOCUMENTO_OCR = [TIPO_DOCUMENTO_MEMORIAL_INCRA, TIPO_DOCUMENTO_MATRICULA]

# Campo da extração (analise_imovel.CAMPOS_PRIORITARIOS) -> coluna em cadastro.midia.
COLUNAS_EXTRACAO = {
    "matricula_imovel": "an5_matricula",
    "nome_propriedade": "an5_nome_imovel",
    "area_total_imovel": "an5_area_total_imovel",
}

ROTULOS_REFERENCIA = {
    "nome_proprietario": "Proprietário",
    "cpf_cnpj": "CPF/CNPJ",
    "nome_propriedade": "Imóvel",
    "classificacao_dominio": "Domínio",
    "matricula_imovel": "Matrícula",
    "codigo_incra_sncr": "Código INCRA/SNCR",
    "area_total_imovel": "Área total",
}


def _carregar_env_local() -> None:
    """Carrega pares simples de ``.env`` sem sobrescrever o ambiente do processo."""
    if not ARQUIVO_ENV_LOCAL.is_file():
        return
    for linha in ARQUIVO_ENV_LOCAL.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", maxsplit=1)
        chave, valor = chave.strip(), valor.strip().strip("\"'")
        if chave:
            os.environ.setdefault(chave, valor)


@dataclass(frozen=True)
class ConfigBanco:
    dsn: str

    @classmethod
    def do_ambiente(cls) -> "ConfigBanco":
        _carregar_env_local()
        dsn = os.environ.get("OCR_PDF_DATABASE_URL")
        if not dsn:
            raise RuntimeError(
                "Defina OCR_PDF_DATABASE_URL com a string de conexão PostgreSQL antes de usar --banco."
            )
        return cls(dsn)


@dataclass(frozen=True)
class TrabalhoPDF:
    id_midia: int
    link: str
    nome: str | None


def calcular_sha256(caminho: Path) -> str:
    """Calcula o hash do arquivo em blocos, sem carregá-lo inteiro na memória."""
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        while bloco := arquivo.read(1024 * 1024):
            digest.update(bloco)
    return digest.hexdigest()


def _itens(extracao: dict[str, Any], campo: str) -> list[dict[str, Any]]:
    campos = extracao.get("campos", {})
    itens = campos.get(campo, []) if isinstance(campos, dict) else []
    if not isinstance(itens, list):
        return []
    return [
        item for item in itens
        if isinstance(item, dict) and isinstance(item.get("valor"), str) and item["valor"].strip()
    ]


def campos_midia(extracao: dict[str, Any] | None) -> dict[str, str | None]:
    """Converte a extração para as colunas ``an5_*`` de ``cadastro.midia`` (primeiro valor, como escrito)."""
    extracao = extracao or {}
    resultado = {}
    for campo, coluna in COLUNAS_EXTRACAO.items():
        itens = _itens(extracao, campo)
        resultado[coluna] = itens[0]["valor"].strip() if itens else None
    return resultado


def descrever_confianca(metricas: dict[str, Any]) -> str:
    """Texto curto explicando a confiança gravada em ``an5_confianca_media``."""
    total, ocr = metricas.get("paginas", 0), metricas.get("paginas_ocr", 0)
    if not ocr or metricas.get("confianca_media_ocr") is None:
        return f"Texto nativo em {total} página(s); OCR não foi necessário."
    faixas = metricas.get("faixas_confianca_ocr") or {}
    texto = (
        f"Confiança média {metricas['confianca_media_ocr']:.1f}% "
        f"(mínima {metricas['confianca_minima_ocr']:.1f}%) em {ocr} de {total} página(s) com OCR. "
        "Faixas: " + ", ".join(f"{nome} {qtd}" for nome, qtd in faixas.items()) + "."
    )
    revisao = metricas.get("paginas_para_revisao") or []
    if revisao:
        texto += " Revisão recomendada nas páginas " + ", ".join(map(str, revisao)) + "."
    return texto


def montar_referencia(extracao: dict[str, Any] | None, resumo: str | None) -> str | None:
    """Resumo legível dos dados extraídos (com a página de origem) e do resumo da LLM."""
    extracao = extracao or {}
    linhas = []
    for campo, rotulo in ROTULOS_REFERENCIA.items():
        valores = [
            item["valor"].strip() + (f" (p. {item['pagina']})" if item.get("pagina") else "")
            for item in _itens(extracao, campo)
        ]
        if valores:
            linhas.append(f"{rotulo}: " + "; ".join(valores))
    if resumo and resumo.strip():
        linhas.append(f"Resumo: {resumo.strip()}")
    return "\n".join(linhas) or None


class BancoProcessamentoPDF:
    """Acesso transacional às mídias marcadas por ``an5_status`` em ``cadastro.midia``."""

    def __init__(self, configuracao: ConfigBanco):
        self.configuracao = configuracao

    def _conectar(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as erro:
            raise RuntimeError("Instale requirements.txt para usar o PostgreSQL.") from erro
        return psycopg.connect(self.configuracao.dsn, row_factory=dict_row)

    def reservar_proximo(
        self, id_midia: int | None = None, tipos_documento: list[int] | None = None,
    ) -> TrabalhoPDF | None:
        """Reserva uma mídia pendente com ``SKIP LOCKED`` para permitir vários workers.

        Só considera os ``tipo_documento`` informados (padrão: INCRA e matrícula), mesmo que
        outra mídia tenha sido marcada como pendente.
        """
        sql = """
            UPDATE cadastro.midia AS m
            SET an5_status = 'processando', an5_tentativas = m.an5_tentativas + 1
            WHERE m.id = (
                SELECT id FROM cadastro.midia
                WHERE an5_status = 'pendente' AND link IS NOT NULL AND link <> ''
                  AND tipo_documento = ANY(%s)
                  AND (%s::int IS NULL OR id = %s)
                ORDER BY id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING m.id, m.link, m.nome
        """
        tipos = list(tipos_documento or TIPOS_DOCUMENTO_OCR)
        with self._conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(sql, (tipos, id_midia, id_midia))
            linha = cursor.fetchone()
        return None if linha is None else TrabalhoPDF(linha["id"], linha["link"], linha["nome"])

    def procurar_resultado_reutilizavel(self, trabalho: TrabalhoPDF, sha256: str) -> int | None:
        sql = """
            SELECT id FROM cadastro.midia
            WHERE id <> %s AND an5_pdf_sha256 = %s AND an5_status = ANY(%s)
            ORDER BY an5_data_transformacao DESC NULLS LAST LIMIT 1
        """
        with self._conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(sql, (trabalho.id_midia, sha256, STATUS_COM_RESULTADO))
            linha = cursor.fetchone()
        return None if linha is None else linha["id"]

    def marcar_reutilizado(self, trabalho: TrabalhoPDF, origem_id: int, sha256: str) -> None:
        """Copia o resultado de um PDF idêntico para manter cada mídia auto-suficiente."""
        sql = """
            UPDATE cadastro.midia AS destino
            SET an5_matricula = origem.an5_matricula,
                an5_nome_imovel = origem.an5_nome_imovel,
                an5_area_total_imovel = origem.an5_area_total_imovel,
                an5_confianca_media = origem.an5_confianca_media,
                an5_descricao = 'Resultado reaproveitado da mídia ' || origem.id
                    || ' (PDF idêntico). ' || COALESCE(origem.an5_descricao, ''),
                an5_referencia = origem.an5_referencia,
                an5_status = 'reutilizado', an5_pdf_sha256 = %s,
                an5_data_transformacao = CURRENT_TIMESTAMP
            FROM cadastro.midia AS origem
            WHERE origem.id = %s AND destino.id = %s AND origem.an5_status = ANY(%s)
        """
        with self._conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(sql, (sha256, origem_id, trabalho.id_midia, STATUS_COM_RESULTADO))

    def concluir(
        self, trabalho: TrabalhoPDF, sha256: str, extracao: dict[str, Any] | None,
        referencia: str | None, confianca_media: float | None, descricao: str,
    ) -> None:
        sql = """
            UPDATE cadastro.midia AS m
            SET an5_matricula = COALESCE(%(an5_matricula)s, m.an5_matricula),
                an5_nome_imovel = COALESCE(%(an5_nome_imovel)s, m.an5_nome_imovel),
                an5_area_total_imovel = COALESCE(%(an5_area_total_imovel)s, m.an5_area_total_imovel),
                an5_confianca_media = %(confianca_media)s, an5_descricao = %(descricao)s,
                an5_referencia = %(referencia)s, an5_status = 'concluido',
                an5_pdf_sha256 = %(sha256)s, an5_data_transformacao = CURRENT_TIMESTAMP
            WHERE m.id = %(id_midia)s
        """
        parametros = {
            **campos_midia(extracao), "id_midia": trabalho.id_midia, "sha256": sha256,
            "confianca_media": confianca_media, "descricao": descricao, "referencia": referencia,
        }
        with self._conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(sql, parametros)

    def falhar(self, trabalho: TrabalhoPDF, erro: Exception) -> None:
        """Depois do primeiro erro, devolve à fila; no segundo, registra falha definitiva."""
        sql = """
            UPDATE cadastro.midia
            SET an5_status = CASE WHEN an5_tentativas >= 2 THEN 'falha' ELSE 'pendente' END,
                an5_descricao = %s, an5_data_transformacao = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        with self._conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(sql, (f"Erro no processamento: {erro}", trabalho.id_midia))
