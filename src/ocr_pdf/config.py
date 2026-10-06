"""Configuração central do pipeline e descoberta do Tesseract."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[2]


def localizar_tesseract() -> str:
    """Procura o executável do Tesseract: variável de ambiente, PATH e locais comuns no Windows."""
    candidatos = [
        os.environ.get("TESSERACT_CMD"),
        shutil.which("tesseract"),
        str(Path.home() / "scoop" / "shims" / "tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidatos:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError(
        "Tesseract não encontrado. Instale (ex.: 'scoop install tesseract') "
        "ou defina a variável TESSERACT_CMD com o caminho do tesseract.exe."
    )


def localizar_tessdata() -> str | None:
    """Prefere a pasta tessdata/ do projeto (tem os idiomas baixados).

    Só cai para TESSDATA_PREFIX se a pasta do projeto não tiver modelos. A ordem importa:
    o scoop define TESSDATA_PREFIX apontando para uma pasta própria, sem o 'por'.
    """
    local = RAIZ_PROJETO / "tessdata"
    if any(local.glob("*.traineddata")):
        return str(local)
    return os.environ.get("TESSDATA_PREFIX")


@dataclass
class ConfigOCR:
    idioma: str = "por"
    dpi: int = 300
    # "auto" testa as estratégias na ordem abaixo até alguma atingir confianca_alvo,
    # e fica com a de maior confiança.
    estrategia: str = "auto"
    estrategias_auto: list[str] = field(
        default_factory=lambda: ["cinza", "marca_dagua", "otsu", "adaptativo"]
    )
    # Confiança média (0-100) considerada "boa o bastante" para parar de testar estratégias.
    confianca_alvo: float = 80.0
    # Detecta páginas escaneadas de lado/de cabeça para baixo (OSD) antes do OCR.
    detectar_rotacao: bool = True
    psm: int = 3
    forcar_ocr: bool = False
    # Página com menos caracteres nativos que isso é tratada como digitalizada.
    min_chars_texto_nativo: int = 50
    workers: int = max(1, (os.cpu_count() or 2) // 2)
    debug_imagens: bool = False
    tesseract_cmd: str = field(default_factory=localizar_tesseract)
    tessdata_dir: str | None = field(default_factory=localizar_tessdata)
