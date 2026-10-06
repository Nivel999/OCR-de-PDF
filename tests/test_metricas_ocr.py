import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocr_pdf.qualidade import avaliar_confianca_ocr


class TestMetricasOCR(unittest.TestCase):
    def test_regua_de_confianca_e_proximo_dpi(self):
        self.assertEqual(avaliar_confianca_ocr(92, 300)["faixa"], "confiavel")
        self.assertEqual(avaliar_confianca_ocr(84, 300)["faixa"], "aceitavel")

        dificil = avaliar_confianca_ocr(74, 300)
        self.assertEqual(dificil["faixa"], "dificil")
        self.assertEqual(dificil["proximo_dpi_sugerido"], 400)

        baixa = avaliar_confianca_ocr(60, 400)
        self.assertEqual(baixa["faixa"], "baixa")
        self.assertEqual(baixa["proximo_dpi_sugerido"], 600)

    def test_fila_de_reprocessamento_respeita_400_e_600_dpi(self):
        from ocr_pdf.__main__ import _paginas_pendentes
        from ocr_pdf.extrator import Documento, Pagina

        documento = Documento(
            arquivo="exemplo.pdf",
            dpi_ocr=300,
            paginas=[
                Pagina(1, "ocr", "imagem", "texto", confianca=68, dpi_ocr=300),
                Pagina(2, "ocr", "imagem", "texto", confianca=74, dpi_ocr=400),
                Pagina(3, "ocr", "imagem", "texto", confianca=60, dpi_ocr=600),
                Pagina(4, "ocr", "imagem", "texto", confianca=93, dpi_ocr=300),
            ],
        )

        pendentes = _paginas_pendentes([(Path("exemplo.pdf"), documento, "exemplo")])

        self.assertEqual(
            [(pagina, dpi) for _, _, _, pagina, dpi in pendentes],
            [(1, 400), (2, 600)],
        )
