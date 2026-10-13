import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocr_pdf.analise_imovel import (
    consolidar_consistencia, consolidar_pessoas, extrair_dados_imovel, identificar_proprietarios_atuais,
    proprietarios_memorial_incra,
)


class BackendFalso:
    """Responde por página; na chamada do documento inteiro devolve ``proprietarios_atuais``."""

    def __init__(self, proprietarios_atuais=None, observacoes=""):
        self.proprietarios_atuais = proprietarios_atuais or []
        self.observacoes = observacoes
        self.documentos: list[str] = []

    def gerar(self, sistema: str, mensagem: str, formato_json: bool = False) -> str:
        assert formato_json, "a extração deve pedir JSON forçado"
        if "PROPRIETÁRIOS ATUAIS" in mensagem:
            self.documentos.append(mensagem)
            return json.dumps(
                {"proprietarios_atuais": self.proprietarios_atuais, "observacoes": self.observacoes}
            )
        return json.dumps(
            {
                "pessoas": [
                    {"nome": "Maria da Silva", "cpf_cnpj": "123.456.789-00", "papel": "proprietario",
                     "evidencia": "Proprietária: Maria da Silva, CPF 123.456.789-00"},
                    {"nome": "José da Silva", "cpf_cnpj": "", "papel": "Conjuge",
                     "evidencia": "casada com José da Silva"},
                    {"nome": "Banco Rural S.A.", "papel": "credor", "evidencia": "em favor do Banco Rural S.A."},
                    {"nome": "Ana Lima", "papel": "inventariante", "evidencia": "inventariante Ana Lima"},
                    {"nome": "", "papel": "testemunha"},
                ],
                "campos": {
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

    def test_extrai_todas_as_pessoas_com_papel(self):
        extracao = extrair_dados_imovel("matricula.pdf", [(1, "texto"), (3, "texto")], BackendFalso())

        pessoas = {pessoa["nome"]: pessoa for pessoa in extracao["pessoas"]}
        self.assertEqual(set(pessoas), {"Maria da Silva", "José da Silva", "Banco Rural S.A.", "Ana Lima"})
        self.assertEqual(pessoas["Maria da Silva"]["paginas"], [1, 3])
        self.assertEqual(pessoas["Maria da Silva"]["cpf_cnpj"], "123.456.789-00")
        self.assertEqual(pessoas["José da Silva"]["papel"], "conjuge")
        self.assertIsNone(pessoas["José da Silva"]["cpf_cnpj"])
        self.assertEqual(pessoas["Banco Rural S.A."]["papel"], "credor")
        # Papel fora da lista vira "outro", preservando o que a LLM escreveu.
        self.assertEqual(pessoas["Ana Lima"]["papel"], "outro")
        self.assertEqual(pessoas["Ana Lima"]["descricao_papel"], "inventariante")

    def test_proprietario_e_cpf_vem_da_lista_de_pessoas(self):
        extracao = extrair_dados_imovel("matricula.pdf", [(2, "texto")], BackendFalso())

        self.assertEqual([i["valor"] for i in extracao["campos"]["nome_proprietario"]], ["Maria da Silva"])
        self.assertEqual([i["valor"] for i in extracao["campos"]["cpf_cnpj"]], ["123.456.789-00"])

    def test_proprietarios_atuais_substituem_os_citados(self):
        backend = BackendFalso(
            [{"nome": "Pedro Alves Lima", "cpf_cnpj": "222.333.444-55", "fracao": "1/2",
              "ato": "R-13 adjudicação compulsória", "pagina": 2, "evidencia": "ADQUIRENTE: PEDRO ALVES LIMA"},
             {"nome": "Nome com página inventada", "pagina": 99}],
            observacoes="Ana Costa Lima faleceu em 01/01/2020.",
        )
        extracao = extrair_dados_imovel("matricula.pdf", [(1, "página um"), (2, "página dois")], backend)

        self.assertEqual(len(backend.documentos), 1)
        self.assertIn("--- Página 1 ---\npágina um", backend.documentos[0])
        self.assertIn("--- Página 2 ---\npágina dois", backend.documentos[0])
        self.assertEqual(
            [i["valor"] for i in extracao["campos"]["nome_proprietario"]],
            ["Pedro Alves Lima", "Nome com página inventada"],
        )
        self.assertEqual([i["valor"] for i in extracao["campos"]["cpf_cnpj"]], ["222.333.444-55"])
        pessoas = {(p["nome"], p["papel"]): p for p in extracao["pessoas"]}
        atual = pessoas[("Pedro Alves Lima", "proprietario_atual")]
        self.assertEqual(atual["descricao_papel"], "R-13 adjudicação compulsória; fração 1/2")
        self.assertEqual(atual["paginas"], [2])
        self.assertEqual(pessoas[("Nome com página inventada", "proprietario_atual")]["paginas"], [])
        # O citado como proprietário continua na lista, mas não é mais o proprietário do documento.
        self.assertIn(("Maria da Silva", "proprietario"), pessoas)
        self.assertEqual(extracao["observacoes_titularidade"], "Ana Costa Lima faleceu em 01/01/2020.")

    def test_resposta_invalida_dos_proprietarios_atuais_gera_alerta(self):
        class BackendQuebrado(BackendFalso):
            def gerar(self, sistema, mensagem, formato_json=False):
                if "PROPRIETÁRIOS ATUAIS" in mensagem:
                    return "não sei"
                return super().gerar(sistema, mensagem, formato_json)

        atuais, observacoes, alertas = identificar_proprietarios_atuais("m.pdf", [(1, "texto")], BackendQuebrado())
        self.assertEqual((atuais, observacoes), ([], ""))
        self.assertIn("Proprietários atuais", alertas[0])

    def test_memorial_incra_le_proprietario_sem_llm(self):
        pagina = (
            "Denominação: SÍTIO EXEMPLO                                              Natureza da Área: Particular\n"
            "Proprietário(a): XXXXXXA EMPRESA EXEMPLO XXXXXX                    CNPJ: **.*12.345/0001**\n"
            "Matrícula do imóvel: 1559"
        )
        backend = BackendFalso()
        extracao = extrair_dados_imovel("incra.pdf", [(1, pagina)], backend)

        self.assertEqual(backend.documentos, [])  # a chamada do documento inteiro não acontece
        atual = next(p for p in extracao["pessoas"] if p["papel"] == "proprietario_atual")
        self.assertEqual(
            (atual["nome"], atual["cpf_cnpj"], atual["paginas"]),
            ("XXXXXXA EMPRESA EXEMPLO XXXXXX", "**.*12.345/0001**", [1]),
        )
        self.assertEqual(
            [i["valor"] for i in extracao["campos"]["nome_proprietario"]], ["XXXXXXA EMPRESA EXEMPLO XXXXXX"]
        )
        self.assertIn("mascarado", extracao["observacoes_titularidade"])

    def test_memorial_incra_com_cpf_e_sem_documento(self):
        paginas = [
            (1, "Proprietário(a): XXXXXX JOSE XXXXXX                                       CPF:  ***.456.789**"),
            (2, "Proprietário(a): MARIA DA SILVA"),
            (3, "PROPRIETÁRIO: JOÃO PEREIRA, CPF nº 333-444-555-66"),  # matrícula: não é o campo do memorial
        ]
        achados = [(p["nome"], p["cpf_cnpj"], p["pagina"]) for p in proprietarios_memorial_incra("x.pdf", paginas)]
        self.assertEqual(achados, [("XXXXXX JOSE XXXXXX", "***.456.789**", 1), ("MARIA DA SILVA", None, 2)])

    def test_une_grafias_diferentes_pelo_cpf(self):
        pessoas = consolidar_pessoas([
            {"nome": "PAULO SOUZA", "papel": "adquirente", "pagina": 2, "cpf_cnpj": "444,555.666-77"},
            {"nome": "PAULO SÓUZE", "papel": "adquirente", "pagina": 1, "cpf_cnpj": "444.555.666-77"},
            {"nome": "Paulo Souza", "papel": "adquirente", "pagina": 5},  # sem CPF: herda pelo nome
            {"nome": "Paulo Souza", "papel": "conjuge", "pagina": 3},  # outro papel: item separado
        ])

        adquirente = next(p for p in pessoas if p["papel"] == "adquirente")
        self.assertEqual(len(pessoas), 2)
        self.assertEqual(adquirente["nome"], "PAULO SOUZA")
        self.assertEqual(adquirente["nomes_alternativos"], ["PAULO SÓUZE"])
        self.assertEqual(adquirente["paginas"], [1, 2, 5])
        self.assertEqual(adquirente["cpf_cnpj"], "444,555.666-77")

    def test_cpf_mascarado_ou_incompleto_nao_une(self):
        pessoas = consolidar_pessoas([
            {"nome": "LUCIA", "papel": "adquirente", "pagina": 1, "cpf_cnpj": "555.666.7778-88"},  # 12 dígitos
            {"nome": "LUCIA MARA", "papel": "adquirente", "pagina": 2, "cpf_cnpj": "555.666.777-88"},
            {"nome": "XXXX JOSE", "papel": "proprietario", "pagina": 1, "cpf_cnpj": "***.456.789**"},
            {"nome": "OUTRO JOSE", "papel": "proprietario", "pagina": 1, "cpf_cnpj": "***.456.789**"},
        ])
        self.assertEqual(len(pessoas), 4)
        self.assertNotIn("nomes_alternativos", pessoas[0])

    def test_pessoas_ordenadas_por_prioridade_do_papel(self):
        pessoas = consolidar_pessoas([
            {"nome": "Oficial", "papel": "oficial_cartorio", "pagina": 1},
            {"nome": "Vizinho", "papel": "confrontante", "pagina": 1},
            {"nome": "Banco", "papel": "credor", "pagina": 2},
            {"nome": "Esposa", "papel": "conjuge", "pagina": 3},
            {"nome": "Dono B", "papel": "proprietario_atual", "pagina": 4},
            {"nome": "Inventariante", "papel": "outro", "pagina": 1},
            {"nome": "Dono A", "papel": "proprietario_atual", "pagina": 2},
        ])
        self.assertEqual(
            [p["nome"] for p in pessoas],
            ["Dono B", "Dono A", "Esposa", "Banco", "Vizinho", "Oficial", "Inventariante"],
        )

    def test_consolida_mesma_pessoa_ignorando_acento_e_caixa(self):
        pessoas = consolidar_pessoas([
            {"nome": "JOSÉ DA SILVA", "papel": "transmitente", "pagina": 4, "cpf_cnpj": None, "evidencia": ""},
            {"nome": "Jose  da Silva", "papel": "transmitente", "pagina": 2, "cpf_cnpj": "111.222.333-44",
             "evidencia": "vendedor Jose da Silva"},
            {"nome": "José da Silva", "papel": "adquirente", "pagina": 1, "cpf_cnpj": None, "evidencia": ""},
        ])

        self.assertEqual(len(pessoas), 2)
        transmitente = next(p for p in pessoas if p["papel"] == "transmitente")
        self.assertEqual(transmitente["nome"], "JOSÉ DA SILVA")
        self.assertEqual(transmitente["paginas"], [2, 4])
        self.assertEqual(transmitente["cpf_cnpj"], "111.222.333-44")
        self.assertEqual(transmitente["evidencia"], "vendedor Jose da Silva")
