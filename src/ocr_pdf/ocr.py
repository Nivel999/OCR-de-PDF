"""Chamada ao Tesseract: devolve texto reconstruído e confiança média."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pytesseract

from .config import ConfigOCR
from .preprocessamento import ESTRATEGIAS, rotacionar


@dataclass
class ResultadoOCR:
    texto: str
    confianca: float  # 0-100, média ponderada pelo tamanho das palavras
    estrategia: str
    rotacao: int = 0


def _config_tesseract(cfg: ConfigOCR) -> str:
    # tessdata vai por TESSDATA_PREFIX (ver extrator.py): --tessdata-dir quebra com espaços no caminho.
    return f"--oem 1 --psm {cfg.psm}"


def ocr_imagem(img: np.ndarray, cfg: ConfigOCR, estrategia: str) -> ResultadoOCR:
    """Roda o Tesseract uma vez e reconstrói o texto (linhas/parágrafos) a partir do image_to_data."""
    dados = pytesseract.image_to_data(
        img, lang=cfg.idioma, config=_config_tesseract(cfg), output_type=pytesseract.Output.DICT
    )

    linhas: dict[tuple[int, int, int], list[str]] = {}
    soma_conf, soma_peso = 0.0, 0
    for i, palavra in enumerate(dados["text"]):
        palavra = palavra.strip()
        conf = float(dados["conf"][i])
        if not palavra or conf < 0:
            continue
        chave = (dados["block_num"][i], dados["par_num"][i], dados["line_num"][i])
        linhas.setdefault(chave, []).append(palavra)
        soma_conf += conf * len(palavra)
        soma_peso += len(palavra)

    # Reconstrói: palavras -> linhas; linha em branco entre parágrafos/blocos.
    partes: list[str] = []
    paragrafo_anterior = None
    for (bloco, par, _), palavras in sorted(linhas.items()):
        if paragrafo_anterior is not None and (bloco, par) != paragrafo_anterior:
            partes.append("")
        partes.append(" ".join(palavras))
        paragrafo_anterior = (bloco, par)

    confianca = soma_conf / soma_peso if soma_peso else 0.0
    return ResultadoOCR("\n".join(partes), round(confianca, 1), estrategia)


def detectar_rotacao(img: np.ndarray, confianca_minima: float = 2.0) -> int:
    """Usa o OSD do Tesseract para descobrir se a página está de lado/de cabeça para baixo.

    Retorna os graus (sentido horário) para endireitar a página, ou 0 se não tiver certeza.
    """
    try:
        saida = pytesseract.image_to_osd(img, config="--psm 0")
    except pytesseract.TesseractError:
        return 0  # pouca informação na página para o OSD decidir
    graus = re.search(r"Rotate: (\d+)", saida)
    conf = re.search(r"Orientation confidence: ([\d.]+)", saida)
    if not graus or not conf or float(conf.group(1)) < confianca_minima:
        return 0
    return int(graus.group(1))


def ocr_pagina(img_rgb: np.ndarray, cfg: ConfigOCR) -> tuple[ResultadoOCR, dict[str, np.ndarray]]:
    """Endireita a página, aplica as estratégias de pré-processamento e devolve o melhor resultado.

    Também devolve as imagens processadas (para salvar em modo debug).
    """
    graus = detectar_rotacao(img_rgb) if cfg.detectar_rotacao else 0
    img_rgb = rotacionar(img_rgb, graus)

    nomes = cfg.estrategias_auto if cfg.estrategia == "auto" else [cfg.estrategia]
    imagens: dict[str, np.ndarray] = {}
    melhor: ResultadoOCR | None = None

    for nome in nomes:
        img = ESTRATEGIAS[nome](img_rgb)
        imagens[nome] = img
        res = ocr_imagem(img, cfg, nome)
        if melhor is None or res.confianca > melhor.confianca:
            melhor = res
        if melhor.confianca >= cfg.confianca_alvo:
            break

    assert melhor is not None
    melhor.rotacao = graus
    return melhor, imagens
