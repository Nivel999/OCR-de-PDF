import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocr_pdf.banco import ConfigBanco, calcular_sha256, campos_midia


class TestBanco(unittest.TestCase):
    def test_calcula_sha256_do_arquivo(self):
        with tempfile.TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "arquivo.pdf"
            caminho.write_bytes(b"conteudo de teste")
            self.assertEqual(calcular_sha256(caminho), hashlib.sha256(b"conteudo de teste").hexdigest())

    def test_mapeia_campos_confirmados_de_midia(self):
        campos = campos_midia({"campos": {"nome_proprietario": [{"valor": "Maria da Silva"}]}})
        self.assertEqual(campos["nome_proprietario"], "Maria da Silva")
        self.assertIsNone(campos["cpf_cnpj"])

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
