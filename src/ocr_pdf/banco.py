"""Fila PostgreSQL e persistência do processamento de PDFs."""

from __future__ import annotations

import hashlib
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any


VERSAO_PIPELINE_PADRAO = "ocr-pdf-v1"
ARQUIVO_ENV_LOCAL = Path(__file__).resolve().parents[2] / ".env"


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


def _primeiro_valor(extracao: dict[str, Any], campo: str) -> str | None:
    campos = extracao.get("campos", {})
    itens = campos.get(campo, []) if isinstance(campos, dict) else []
    if not isinstance(itens, list):
        return None
    for item in itens:
        valor = item.get("valor") if isinstance(item, dict) else None
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return None


def campos_midia(extracao: dict[str, Any] | None) -> dict[str, str | None]:
    """Converte a extração para os campos confirmados de ``cadastro.midia``."""
    extracao = extracao or {}
    return {
        campo: _primeiro_valor(extracao, campo)
        for campo in (
            "nome_proprietario",
            "cpf_cnpj",
            "nome_propriedade",
            "classificacao_dominio",
            "matricula_imovel",
            "codigo_incra_sncr",
        )
    }


class BancoProcessamentoPDF:
    """Acesso transacional à fila ``cadastro.midia_processamento_pdf``."""

    def __init__(self, configuracao: ConfigBanco, worker: str | None = None):
        self.configuracao = configuracao
        self.worker = worker or socket.gethostname()

    def _conectar(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as erro:
            raise RuntimeError("Instale requirements.txt para usar o PostgreSQL.") from erro
        return psycopg.connect(self.configuracao.dsn, row_factory=dict_row)

    def reservar_proximo(self, id_midia: int | None = None) -> TrabalhoPDF | None:
        """Reserva uma pendência com ``SKIP LOCKED`` para permitir vários workers."""
        sql = """
            WITH proximo AS (
                SELECT p.id_midia
                FROM cadastro.midia_processamento_pdf AS p
                JOIN cadastro.midia AS m ON m.id = p.id_midia
                WHERE p.status = 'pendente' AND m.link IS NOT NULL AND m.link <> ''
                  AND (%s::int IS NULL OR p.id_midia = %s)
                ORDER BY p.criado_em, p.id_midia
                FOR UPDATE OF p SKIP LOCKED
                LIMIT 1
            )
            UPDATE cadastro.midia_processamento_pdf AS p
            SET status = 'processando', tentativas = p.tentativas + 1,
                reservado_em = CURRENT_TIMESTAMP, worker = %s, erro = NULL,
                atualizado_em = CURRENT_TIMESTAMP
            FROM proximo
            JOIN cadastro.midia AS m ON m.id = proximo.id_midia
            WHERE p.id_midia = proximo.id_midia
            RETURNING p.id_midia, m.link, m.nome
        """
        with self._conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(sql, (id_midia, id_midia, self.worker))
            linha = cursor.fetchone()
        return None if linha is None else TrabalhoPDF(linha["id_midia"], linha["link"], linha["nome"])

    def procurar_resultado_reutilizavel(self, trabalho: TrabalhoPDF, sha256: str, versao: str) -> int | None:
        sql = """
            SELECT id_midia FROM cadastro.midia_processamento_pdf
            WHERE id_midia <> %s AND pdf_sha256 = %s AND versao_pipeline = %s
              AND status IN ('concluido', 'reutilizado')
            ORDER BY concluido_em DESC NULLS LAST LIMIT 1
        """
        with self._conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(sql, (trabalho.id_midia, sha256, versao))
            linha = cursor.fetchone()
        return None if linha is None else linha["id_midia"]

    def marcar_reutilizado(self, trabalho: TrabalhoPDF, origem_id: int, sha256: str, versao: str) -> None:
        """Copia resultados para manter cada registro de mídia auto-suficiente."""
        sql = """
            WITH origem AS (
                SELECT m.*, p.ocr_markdown, p.extracao_json
                FROM cadastro.midia AS m
                JOIN cadastro.midia_processamento_pdf AS p ON p.id_midia = m.id
                WHERE m.id = %s AND p.status IN ('concluido', 'reutilizado')
            ), atualiza_midia AS (
                UPDATE cadastro.midia AS destino
                SET nome_proprietario = origem.nome_proprietario, cpf_cnpj = origem.cpf_cnpj,
                    nome_propriedade = origem.nome_propriedade,
                    classificacao_dominio = origem.classificacao_dominio,
                    matricula_imovel = origem.matricula_imovel,
                    codigo_incra_sncr = origem.codigo_incra_sncr,
                    confianca_media = origem.confianca_media, tipo_faixa = origem.tipo_faixa,
                    descricao = origem.descricao, data_transformacao = CURRENT_TIMESTAMP,
                    resumo = origem.resumo
                FROM origem WHERE destino.id = %s
                RETURNING origem.ocr_markdown, origem.extracao_json
            )
            UPDATE cadastro.midia_processamento_pdf AS destino
            SET status = 'reutilizado', pdf_sha256 = %s, link_processado = %s,
                resultado_origem_id = %s, ocr_markdown = atualiza_midia.ocr_markdown,
                extracao_json = atualiza_midia.extracao_json, versao_pipeline = %s,
                concluido_em = CURRENT_TIMESTAMP, atualizado_em = CURRENT_TIMESTAMP, erro = NULL
            FROM atualiza_midia WHERE destino.id_midia = %s
        """
        with self._conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(sql, (origem_id, trabalho.id_midia, sha256, trabalho.link, origem_id, versao, trabalho.id_midia))

    def concluir(
        self, trabalho: TrabalhoPDF, sha256: str, versao: str, ocr_markdown: str,
        extracao: dict[str, Any] | None, resumo: str | None, confianca_media: float | None,
    ) -> None:
        campos = campos_midia(extracao)
        sql = """
            UPDATE cadastro.midia AS m
            SET nome_proprietario = COALESCE(%(nome_proprietario)s, m.nome_proprietario),
                cpf_cnpj = COALESCE(%(cpf_cnpj)s, m.cpf_cnpj),
                nome_propriedade = COALESCE(%(nome_propriedade)s, m.nome_propriedade),
                classificacao_dominio = COALESCE(%(classificacao_dominio)s, m.classificacao_dominio),
                matricula_imovel = COALESCE(%(matricula_imovel)s, m.matricula_imovel),
                codigo_incra_sncr = COALESCE(%(codigo_incra_sncr)s, m.codigo_incra_sncr),
                confianca_media = COALESCE(%(confianca_media)s, m.confianca_media),
                resumo = COALESCE(%(resumo)s, m.resumo), data_transformacao = CURRENT_TIMESTAMP
            WHERE m.id = %(id_midia)s;
            UPDATE cadastro.midia_processamento_pdf
            SET status = 'concluido', pdf_sha256 = %(sha256)s, link_processado = %(link)s,
                resultado_origem_id = NULL, ocr_markdown = %(ocr_markdown)s,
                extracao_json = %(extracao_json)s::jsonb, versao_pipeline = %(versao)s,
                concluido_em = CURRENT_TIMESTAMP, atualizado_em = CURRENT_TIMESTAMP, erro = NULL
            WHERE id_midia = %(id_midia)s
        """
        parametros = {
            **campos, "id_midia": trabalho.id_midia, "sha256": sha256, "link": trabalho.link,
            "ocr_markdown": ocr_markdown,
            "extracao_json": json.dumps(extracao) if extracao is not None else None,
            "versao": versao, "resumo": resumo, "confianca_media": confianca_media,
        }
        with self._conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(sql, parametros)

    def falhar(self, trabalho: TrabalhoPDF, erro: Exception) -> None:
        """Depois do primeiro erro, devolve à fila; no segundo, registra falha definitiva."""
        sql = """
            UPDATE cadastro.midia_processamento_pdf
            SET status = CASE WHEN tentativas >= 2 THEN 'falha' ELSE 'pendente' END,
                erro = %s, reservado_em = NULL, atualizado_em = CURRENT_TIMESTAMP
            WHERE id_midia = %s
        """
        with self._conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(sql, (str(erro), trabalho.id_midia))
