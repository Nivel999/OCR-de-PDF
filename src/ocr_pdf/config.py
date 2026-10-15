"""Configuração central do pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[2]


@dataclass
class ConfigOCR:
    # Idioma do PaddleOCR ("pt" usa o modelo latino, que cobre o português com acentos).
    idioma: str = "pt"
    dpi: int = 300
    # Detecta páginas escaneadas de lado/de cabeça para baixo antes do OCR.
    detectar_rotacao: bool = True
    forcar_ocr: bool = False
    # Página com menos caracteres nativos que isso é tratada como digitalizada.
    min_chars_texto_nativo: int = 50
    # Threads de CPU do Paddle. As páginas vão uma por vez; o paralelismo fica dentro do Paddle.
    threads: int = os.cpu_count() or 4
    debug_imagens: bool = False
