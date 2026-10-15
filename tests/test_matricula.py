import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocr_pdf.matricula import documentos_no_texto, separar_atos, validar_cnpj, validar_cpf

# Dados fictícios. CPF 111.444.777-35 e CNPJ 11.222.333/0001-81 são números de teste válidos.
PAGINA_1 = """Visualização disponibilizada pelo RI Digital
Matrícula Nº. 9.876.- Data: 10 de março de 1980.-
IDENTIFICAÇÃO DO IMÓVEL: O terreno contendo a área de 10.000 m2, com frente
na Rodovia BR-280, Km 10, confrontando com terras de Pedro Confrontante.
PRCPRIBTÁRIO:-MARIA FICTICIA, solteira, CPF nº 111-444-777-35, residente
nesta cidade.
TITULO AQUISITIVO: Transcrição nº 1.234, livro 3, nesta comarca.
R—-1-9.876s-Por Escritura Pública de Compra e Venda, MARIA FICTICIA vendeu
o imóvel a JOAO TESTE, CPF nº 123.456.789-00, pelo valor de R$ 1.000,00.
AV=2=-9,876: Procedo a esta averbação para constar a construção de uma casa.
"""
PAGINA_2 = """CONTINUAÇÃO DA MATRÍCULA Nº 9.876
AV=23-9.876: Procedo a esta averbação do casamento de JOAO TESTE, já
qualificado no R=1=-9,876 acima, com ANA TESTE.
A V.4/98760. Guaramirim, 2 de maio de 2001. Hipoteca em favor de
BANCO FICTICIO S.A., CNPJ 11.222.333/0001-81.
nº 3/R=222.149, protocolo do Av.11. sem número de matrícula.
R-6-9876: Nos termos da escritura, JOAO TESTE vendeu a fração de 1/2.
"""
PAGINA_3 = """AV.7/9.876. 09 de fevereiro de 2026. TRANSFERÊNCIA/ENCERRAMENTO: o imóvel
foi transferido para a matrícula nº 45.559, motivo pelo qual fica encerrada
a presente matrícula.
"""


class TestSepararAtos(unittest.TestCase):
    def setUp(self):
        self.matricula = separar_atos([(1, PAGINA_1), (2, PAGINA_2), (3, PAGINA_3)])

    def test_numero_e_sequencia_de_atos(self):
        self.assertEqual(self.matricula.numero, "9876")
        self.assertEqual(
            [ato.rotulo for ato in self.matricula.atos],
            ["R-1", "AV-2", "AV-3", "AV-4", "R-6", "AV-7"],
        )
        self.assertEqual(self.matricula.atos_ausentes, [5])

    def test_descarta_falsos_marcadores(self):
        # "R$", "BR-280", "nº 3/R=222", "Av.11." sem matrícula e a citação "R=1=-9,876 acima" não viram atos.
        textos = " ".join(ato.texto for ato in self.matricula.atos)
        self.assertIn("qualificado no R=1=-9,876 acima", self.matricula.atos[2].texto)
        self.assertIn("BR-280", self.matricula.abertura)
        self.assertEqual(textos.count("R—-1-9.876s"), 1)

    def test_corrige_numero_com_digito_a_mais_e_avisa(self):
        self.assertEqual(self.matricula.atos[2].numero, 3)
        self.assertTrue(any("AV=23-9.876" in alerta for alerta in self.matricula.alertas))

    def test_aceita_matricula_lida_com_um_digito_a_mais(self):
        self.assertEqual(self.matricula.atos[3].rotulo, "AV-4")  # "A V.4/98760"

    def test_paginas_e_texto_de_cada_ato(self):
        av3 = self.matricula.atos[2]
        self.assertEqual((av3.pagina_inicial, av3.pagina_final), (2, 2))
        r1 = self.matricula.atos[0]
        self.assertTrue(r1.texto.startswith("R—-1-9.876s-Por Escritura"))
        self.assertNotIn("AV=2", r1.texto)
        # O AV-2 vai até o cabeçalho de continuação da página 2, antes do AV-3.
        self.assertEqual(self.matricula.atos[1].pagina_final, 2)
        self.assertNotIn("AV=23", self.matricula.atos[1].texto)
        self.assertEqual(self.matricula.atos[-1].pagina_inicial, 3)

    def test_abertura_e_proprietarios_iniciais(self):
        self.assertIn("IDENTIFICAÇÃO DO IMÓVEL", self.matricula.abertura)
        self.assertNotIn("Compra e Venda", self.matricula.abertura)
        self.assertTrue(self.matricula.proprietarios_abertura.startswith("MARIA FICTICIA, solteira"))
        self.assertNotIn("Transcrição", self.matricula.proprietarios_abertura)
        self.assertEqual(
            [(d["numero"], d["valido"]) for d in self.matricula.documentos_abertura],
            [("11144477735", True)],
        )

    def test_documentos_por_ato(self):
        r1, av4 = self.matricula.atos[0], self.matricula.atos[3]
        self.assertEqual([(d["tipo"], d["valido"]) for d in r1.documentos], [("cpf", False)])
        self.assertEqual([(d["tipo"], d["numero"], d["valido"]) for d in av4.documentos],
                         [("cnpj", "11222333000181", True)])

    def test_encerramento_e_destino(self):
        self.assertTrue(self.matricula.encerrada)
        self.assertEqual(self.matricula.transferida_para, "45559")
        self.assertIn("Matrícula encerrada no AV-7.", self.matricula.alertas)

    def test_sem_atos(self):
        matricula = separar_atos([(1, "Texto qualquer sem registros.")])
        self.assertEqual(matricula.atos, [])
        self.assertIsNone(matricula.numero)
        self.assertIn("Nenhum ato (R-n/AV-n) encontrado.", matricula.alertas)


class TestDocumentos(unittest.TestCase):
    def test_validacao_digito_verificador(self):
        self.assertTrue(validar_cpf("11144477735"))
        self.assertFalse(validar_cpf("11144477736"))
        self.assertFalse(validar_cpf("11111111111"))
        self.assertTrue(validar_cnpj("11222333000181"))
        self.assertFalse(validar_cnpj("11222333000182"))

    def test_formatos_do_ocr(self):
        documentos = documentos_no_texto("CPF nº 111-444-777-35%, CIC 111.444. 777-35 e CNPJ 11.222.333/0001-81")
        self.assertEqual([d["tipo"] for d in documentos], ["cpf", "cpf", "cnpj"])
        self.assertTrue(all(d["valido"] for d in documentos))

    def test_cpf_mascarado_nao_e_documento(self):
        self.assertEqual(documentos_no_texto("CPF: ***.456.789**"), [])


if __name__ == "__main__":
    unittest.main()
