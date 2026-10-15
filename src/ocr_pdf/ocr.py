"""Chamada ao PaddleOCR: devolve texto reconstruído em linhas e confiança média."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from .config import ConfigOCR


@dataclass
class ResultadoOCR:
    texto: str
    confianca: float  # 0-100, média das confianças do reconhecimento ponderada pelo tamanho do texto
    rotacao: int = 0  # graus que o PaddleOCR girou a página para endireitá-la


def caminho_sem_acento(caminho: Path) -> Path:
    """Devolve um caminho só com ASCII para a mesma pasta, criando-a se preciso.

    O motor de inferência do Paddle (C++) não abre arquivos em caminhos com acento no Windows: com
    os modelos em ``C:\\Users\\Usuário\\.paddlex`` ele lê o ``inference.json`` como vazio e falha com
    ``json.exception.parse_error.101``. O nome curto 8.3 do Windows (``C:\\Users\\USURIO~2``) aponta
    para a mesma pasta sem acentos.
    """
    if str(caminho).isascii():
        return caminho
    if sys.platform != "win32":
        raise RuntimeError(f"O Paddle não lê modelos em caminhos com acento: {caminho}")
    import ctypes

    caminho.mkdir(parents=True, exist_ok=True)
    buffer = ctypes.create_unicode_buffer(1024)
    tamanho = ctypes.windll.kernel32.GetShortPathNameW(str(caminho), buffer, len(buffer))
    curto = buffer.value if 0 < tamanho < len(buffer) else ""
    if not curto.isascii() or not curto:
        raise RuntimeError(
            f"O Paddle não lê modelos em caminhos com acento ({caminho}) e o Windows não forneceu um "
            "nome curto sem acento. Defina PADDLE_PDX_CACHE_HOME com uma pasta sem acento, ex.: C:\\paddlex."
        )
    return Path(curto)


def configurar_ambiente_paddle() -> None:
    """Prepara as variáveis do Paddle antes de importá-lo (o cache é lido no import)."""
    cache = os.environ.get("PADDLE_PDX_CACHE_HOME") or str(Path.home() / ".paddlex")
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(caminho_sem_acento(Path(cache)))
    # Sem isso, cada execução consulta a internet para conferir a origem dos modelos já baixados.
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


@lru_cache(maxsize=2)
def _motor(idioma: str, detectar_rotacao: bool, threads: int):
    """Carrega o PaddleOCR uma vez por configuração (carregar os modelos leva alguns segundos)."""
    configurar_ambiente_paddle()
    try:
        from paddleocr import PaddleOCR
    except ImportError as erro:
        raise RuntimeError(
            "PaddleOCR não instalado. Ele exige Python 3.9 a 3.13: crie o .venv com essa versão "
            "e rode 'pip install -r requirements.txt'."
        ) from erro
    return PaddleOCR(
        lang=idioma,
        use_doc_orientation_classify=detectar_rotacao,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        # O oneDNN do Paddle 3.3 na CPU falha com "ConvertPirAttribute2RuntimeAttribute not support
        # [pir::ArrayAttribute<pir::DoubleAttribute>]" ao rodar a detecção de texto.
        enable_mkldnn=False,
        cpu_threads=threads,
    )


def montar_linhas(caixas: Sequence[Sequence[float]], textos: Sequence[str]) -> str:
    """Junta os trechos detectados em linhas, de cima para baixo e da esquerda para a direita.

    O PaddleOCR detecta trechos de texto, não linhas: uma linha com espaço largo no meio vira dois
    trechos. Dois trechos ficam na mesma linha quando se sobrepõem em mais da metade da altura do menor.
    Caixas no formato [x0, y0, x1, y1].
    """
    itens = sorted(
        ((tuple(map(float, caixa)), texto) for caixa, texto in zip(caixas, textos) if texto.strip()),
        key=lambda item: ((item[0][1] + item[0][3]) / 2, item[0][0]),
    )
    linhas: list[list[tuple[tuple[float, ...], str]]] = []
    for caixa, texto in itens:
        if linhas:
            topo = min(c[1] for c, _ in linhas[-1])
            base = max(c[3] for c, _ in linhas[-1])
            sobreposicao = min(caixa[3], base) - max(caixa[1], topo)
            if sobreposicao > min(caixa[3] - caixa[1], base - topo) / 2:
                linhas[-1].append((caixa, texto))
                continue
        linhas.append([(caixa, texto)])
    return "\n".join(
        " ".join(texto.strip() for _, texto in sorted(linha, key=lambda item: item[0][0])) for linha in linhas
    )


def confianca_ponderada(textos: Sequence[str], notas: Sequence[float]) -> float:
    """Média das notas (0-1) ponderada pelo tamanho de cada trecho, na escala 0-100."""
    pesos = [len(texto.strip()) for texto in textos]
    if not sum(pesos):
        return 0.0
    return round(100 * sum(float(n) * p for n, p in zip(notas, pesos)) / sum(pesos), 1)


def resultado_paddle(resultado) -> ResultadoOCR:
    """Converte um resultado de ``PaddleOCR.predict`` em ``ResultadoOCR``."""
    textos = list(resultado["rec_texts"])
    rotacao = int((resultado.get("doc_preprocessor_res") or {}).get("angle") or 0)
    return ResultadoOCR(
        montar_linhas(np.asarray(resultado["rec_boxes"]).tolist(), textos),
        confianca_ponderada(textos, list(resultado["rec_scores"])),
        rotacao,
    )


def ocr_pagina(img_rgb: np.ndarray, cfg: ConfigOCR) -> ResultadoOCR:
    """Endireita a página (se ``cfg.detectar_rotacao``) e reconhece o texto."""
    motor = _motor(cfg.idioma, cfg.detectar_rotacao, cfg.threads)
    resultados = list(motor.predict(img_rgb))
    return resultado_paddle(resultados[0]) if resultados else ResultadoOCR("", 0.0)
