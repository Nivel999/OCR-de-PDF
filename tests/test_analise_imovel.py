import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocr_pdf.analise_imovel import consolidar_consistencia, extrair_dados_imovel


class BackendFalso:
    def gerar(self, sistema: str, mensagem: str) -> str:
        return json.dumps(
            {
                "campos": {
                    "nome_proprietario": [{"valor": "Maria da Silva", "evidencia": "Proprietária: Maria da Silva"}],
                    "cpf_cnpj": [{"valor": "123.456.789-00", "evidencia": "CPF 123.456.789-00"}],
                    "nome_propriedade": [],
                    "classificacao_dominio": [],
                    "matricula_imovel": [{"valor": "12.345", "evidencia": "Matrícula 12.345"}],
                    "codigo_incra_sncr": [],
                },
                "demais_atributos_relevantes": [{"nome": "Área", "valor": "50 ha", "evidencia": "Área total: 50 ha"}],
            }
        )


class TestAnaliseImovel(unittest.TestCase):
    def test_extracao_anexa_arquivo_e_pagina(self):
        extracao = extrair_dados_imovel("matricula.pdf", [(3, "texto da página")], BackendFalso())

        proprietario = extracao["campos"]["nome_proprietario"][0]
        self.assertEqual(proprietario["arquivo"], "matricula.pdf")
        self.assertEqual(proprietario["pagina"], 3)
        self.assertEqual(extracao["demais_atributos_relevantes"][0]["pagina"], 3)

    def test_consistencia_mostra_todas_as_fontes_e_divergencias(self):
        primeira = extrair_dados_imovel("a.pdf", [(1, "texto")], BackendFalso())
        segunda = extrair_dados_imovel("b.pdf", [(2, "texto")], BackendFalso())
        segunda["campos"]["matricula_imovel"][0]["valor"] = "99.999"

        consolidado = consolidar_consistencia([primeira, segunda])

        self.assertEqual(consolidado["consistencia"]["nome_proprietario"]["status"], "consistente")
        self.assertEqual(consolidado["consistencia"]["matricula_imovel"]["status"], "divergente")
        self.assertEqual(len(consolidado["consistencia"]["matricula_imovel"]["valores"]), 2)
