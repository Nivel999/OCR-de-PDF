"""Interpretação da confiança do OCR para relatórios e futuras interfaces."""

from __future__ import annotations


def avaliar_confianca_ocr(confianca: float | None, dpi: int) -> dict:
    """Traduz a confiança do Tesseract em uma orientação consumível pelo relatório/UI."""
    confianca = round(confianca or 0.0, 1)
    proximo_dpi = 400 if dpi < 400 else 600 if dpi < 600 else None

    if confianca >= 90:
        return {
            "faixa": "confiavel",
            "descricao": "Leitura confiável; o scan foi bem reconhecido.",
            "revisao_recomendada": False,
            "proximo_dpi_sugerido": None,
            "acao_recomendada": "Nenhuma ação necessária.",
        }
    if confianca >= 80:
        return {
            "faixa": "aceitavel",
            "descricao": "Leitura utilizável; revise nomes, datas, valores e outros dados críticos.",
            "revisao_recomendada": True,
            "proximo_dpi_sugerido": None,
            "acao_recomendada": "Revisar os dados importantes antes de usar o texto.",
        }

    if confianca >= 70:
        descricao = "Leitura difícil; o OCR pode conter erros relevantes."
    else:
        descricao = "Leitura pouco confiável; o OCR provavelmente contém erros."

    if proximo_dpi is not None:
        acao = f"Reprocessar esta página em {proximo_dpi} DPI e comparar o resultado."
    else:
        acao = "A página já foi processada em 600 DPI; faça revisão manual ou melhore o scan original."

    return {
        "faixa": "dificil" if confianca >= 70 else "baixa",
        "descricao": descricao,
        "revisao_recomendada": True,
        "proximo_dpi_sugerido": proximo_dpi,
        "acao_recomendada": acao,
    }
