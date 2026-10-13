import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocr_pdf.__main__ import _gravar_saida_analise


class TestSaidaAnalise(unittest.TestCase):
    def test_grava_copia_do_banco_por_midia(self):
        with tempfile.TemporaryDirectory() as diretorio:
            pasta = Path(diretorio) / "banco"
            banco = {"an5_status": "concluido", "an5_pessoas": '[{"nome": "Maria", "papel": "proprietario"}]'}
            _gravar_saida_analise(pasta, 757, banco, extracao={"pessoas": []}, resumo="Resumo.")

            destino = pasta / "midia-757"
            gravado = json.loads((destino / "banco.json").read_text(encoding="utf-8"))
            self.assertEqual(gravado["an5_pessoas"], [{"nome": "Maria", "papel": "proprietario"}])
            self.assertTrue((destino / "extracao.json").is_file())
            self.assertEqual((destino / "resumo.md").read_text(encoding="utf-8"), "Resumo.")
            self.assertFalse((destino / "texto.txt").exists())

    def test_sem_pasta_nao_grava_nada(self):
        _gravar_saida_analise(None, 1, {"an5_status": "concluido"})  # não deve lançar


if __name__ == "__main__":
    unittest.main()
