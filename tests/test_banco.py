import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocr_pdf.banco import (
    ConfigBanco, calcular_sha256, campos_midia, descrever_confianca, montar_referencia,
)

EXTRACAO = {
    "campos": {
        "nome_proprietario": [{"valor": "Maria da Silva", "pagina": 1}],
        "nome_propriedade": [{"valor": "Fazenda Boa Vista", "pagina": 2}],
        "matricula_imovel": [{"valor": "  12.345 ", "pagina": 2}, {"valor": "99.999", "pagina": 4}],
        "area_total_imovel": [{"valor": "", "pagina": 3}],
    }
}


class TestBanco(unittest.TestCase):
    def test_calcula_sha256_do_arquivo(self):
        with tempfile.TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "arquivo.pdf"
            caminho.write_bytes(b"conteudo de teste")
            self.assertEqual(calcular_sha256(caminho), hashlib.sha256(b"conteudo de teste").hexdigest())

    def test_area_fica_exatamente_como_escrita(self):
        texto = "Área (Sistema Geodésico Local): 35,2723 ha"
        extracao = {"campos": {"area_total_imovel": [{"valor": texto, "pagina": 1}]}}
        self.assertEqual(campos_midia(extracao)["an5_area_total_imovel"], texto)

    def test_mapeia_extracao_para_colunas_an5(self):
        self.assertEqual(
            campos_midia(EXTRACAO),
            {"an5_matricula": "12.345", "an5_nome_imovel": "Fazenda Boa Vista", "an5_area_total_imovel": None},
        )
        self.assertEqual(set(campos_midia(None).values()), {None})

    def test_referencia_lista_valores_com_pagina_e_resumo(self):
        referencia = montar_referencia(EXTRACAO, "Matrícula de imóvel rural.")
        self.assertIn("Proprietário: Maria da Silva (p. 1)", referencia)
        self.assertIn("Matrícula: 12.345 (p. 2); 99.999 (p. 4)", referencia)
        self.assertNotIn("Área total", referencia)
        self.assertTrue(referencia.endswith("Resumo: Matrícula de imóvel rural."))
        self.assertIsNone(montar_referencia(None, None))

    def test_descreve_confianca_com_ocr_e_nativo(self):
        metricas = {
            "paginas": 3, "paginas_ocr": 2, "confianca_media_ocr": 81.5, "confianca_minima_ocr": 70.0,
            "faixas_confianca_ocr": {"confiavel": 1, "aceitavel": 1, "dificil": 0, "baixa": 0},
            "paginas_para_revisao": [3],
        }
        descricao = descrever_confianca(metricas)
        self.assertIn("Confiança média 81.5% (mínima 70.0%) em 2 de 3 página(s)", descricao)
        self.assertIn("páginas 3.", descricao)
        nativo = descrever_confianca({"paginas": 2, "paginas_ocr": 0, "confianca_media_ocr": None})
        self.assertEqual(nativo, "Texto nativo em 2 página(s); OCR não foi necessário.")

    def test_configuracao_aceita_variavel_de_ambiente(self):
        anterior = os.environ.get("OCR_PDF_DATABASE_URL")
        os.environ["OCR_PDF_DATABASE_URL"] = "postgresql://usuario:senha@localhost:5432/banco"
        try:
            self.assertEqual(ConfigBanco.do_ambiente().dsn, os.environ["OCR_PDF_DATABASE_URL"])
        finally:
            if anterior is None:
                os.environ.pop("OCR_PDF_DATABASE_URL", None)
            else:
                os.environ["OCR_PDF_DATABASE_URL"] = anterior
