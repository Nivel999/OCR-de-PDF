import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocr_pdf import ocr
from ocr_pdf.config import ConfigOCR


class TestMontarLinhas(unittest.TestCase):
    def test_junta_trechos_da_mesma_linha_em_ordem(self):
        caixas = [[300, 12, 500, 38], [10, 10, 200, 40], [10, 60, 400, 90]]
        textos = ["Data: 10/03/1980", "Matrícula Nº 9.876", "R-1-9.876: Compra e venda"]
        self.assertEqual(
            ocr.montar_linhas(caixas, textos),
            "Matrícula Nº 9.876 Data: 10/03/1980\nR-1-9.876: Compra e venda",
        )

    def test_linhas_proximas_nao_se_misturam(self):
        # Sobreposição de 10px em linhas de 30px fica abaixo da metade: são linhas diferentes.
        caixas = [[10, 10, 300, 40], [10, 30, 300, 60]]
        self.assertEqual(ocr.montar_linhas(caixas, ["primeira", "segunda"]), "primeira\nsegunda")

    def test_ignora_trechos_vazios(self):
        self.assertEqual(ocr.montar_linhas([[0, 0, 10, 10], [20, 0, 30, 10]], ["  ", "texto"]), "texto")


class TestResultadoPaddle(unittest.TestCase):
    def test_converte_resultado_com_rotacao(self):
        resultado = {
            "rec_texts": ["abcd", "ef"],
            "rec_scores": [1.0, 0.7],
            "rec_boxes": np.array([[10, 10, 100, 40], [10, 60, 100, 90]]),
            "doc_preprocessor_res": {"angle": 90},
        }
        convertido = ocr.resultado_paddle(resultado)
        self.assertEqual(convertido.texto, "abcd\nef")
        self.assertEqual(convertido.confianca, 90.0)  # (1.0*4 + 0.7*2) / 6
        self.assertEqual(convertido.rotacao, 90)

    def test_sem_texto_e_sem_rotacao(self):
        convertido = ocr.resultado_paddle({"rec_texts": [], "rec_scores": [], "rec_boxes": np.zeros((0, 4))})
        self.assertEqual((convertido.texto, convertido.confianca, convertido.rotacao), ("", 0.0, 0))

    def test_ocr_pagina_usa_motor_da_configuracao(self):
        motor = mock.Mock()
        motor.predict.return_value = iter([{"rec_texts": ["ok"], "rec_scores": [0.95], "rec_boxes": [[0, 0, 5, 5]]}])
        cfg = ConfigOCR(idioma="pt", detectar_rotacao=False, threads=2)
        with mock.patch.object(ocr, "_motor", return_value=motor) as fabrica:
            resultado = ocr.ocr_pagina(np.zeros((5, 5, 3), dtype=np.uint8), cfg)
        fabrica.assert_called_once_with("pt", False, 2)
        self.assertEqual((resultado.texto, resultado.confianca), ("ok", 95.0))


class TestCaminhoSemAcento(unittest.TestCase):
    def test_caminho_ascii_fica_igual(self):
        self.assertEqual(ocr.caminho_sem_acento(Path("C:/paddlex")), Path("C:/paddlex"))

    @unittest.skipUnless(sys.platform == "win32", "nome curto 8.3 só existe no Windows")
    def test_caminho_com_acento_vira_nome_curto(self):
        with tempfile.TemporaryDirectory() as base:
            pasta = Path(base) / "Usuário" / ".paddlex"
            curto = ocr.caminho_sem_acento(pasta)
            self.assertTrue(str(curto).isascii())
            self.assertTrue(pasta.is_dir())
            self.assertTrue(os.path.samefile(curto, pasta))

    def test_configura_cache_sem_acento(self):
        with mock.patch.dict(os.environ, {"PADDLE_PDX_CACHE_HOME": "C:/paddlex"}, clear=False):
            os.environ.pop("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", None)
            ocr.configurar_ambiente_paddle()
            self.assertEqual(os.environ["PADDLE_PDX_CACHE_HOME"], str(Path("C:/paddlex")))
            self.assertEqual(os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"], "True")


if __name__ == "__main__":
    unittest.main()
