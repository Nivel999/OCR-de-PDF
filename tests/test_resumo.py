import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocr_pdf.resumo import MODELO_OLLAMA_PADRAO, BackendOllama, criar_backend


def _resposta(conteudo: str):
    corpo = json.dumps({"message": {"content": conteudo}}).encode("utf-8")
    resposta = mock.MagicMock()
    resposta.__enter__.return_value = io.BytesIO(corpo)
    return resposta


class TestBackendOllama(unittest.TestCase):
    def test_desliga_raciocinio_e_remove_bloco_think(self):
        with mock.patch("urllib.request.urlopen", return_value=_resposta("<think>hmm</think>\n{\"a\": 1}")) as urlopen:
            texto = BackendOllama("qwen3:8b", url="http://ollama:11434", num_ctx=16384).gerar("sistema", "mensagem")

        self.assertEqual(texto, '{"a": 1}')
        requisicao = urlopen.call_args.args[0]
        corpo = json.loads(requisicao.data)
        self.assertEqual(requisicao.full_url, "http://ollama:11434/api/chat")
        self.assertIs(corpo["think"], False)
        self.assertEqual(corpo["options"]["num_ctx"], 16384)

    def test_sem_opcao_de_raciocinio_quando_none(self):
        with mock.patch("urllib.request.urlopen", return_value=_resposta("ok")) as urlopen:
            BackendOllama("qwen2.5:7b", pensar=None).gerar("s", "m")
        self.assertNotIn("think", json.loads(urlopen.call_args.args[0].data))

    def test_modelo_e_contexto_padrao(self):
        backend = criar_backend("ollama", None, 8192)
        self.assertEqual((backend.modelo, backend.num_ctx), (MODELO_OLLAMA_PADRAO, 8192))
        self.assertIsNone(criar_backend("nenhum", None))


if __name__ == "__main__":
    unittest.main()
