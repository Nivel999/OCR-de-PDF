"""Atalho: python run.py [opções]  (equivale a python -m ocr_pdf com src/ no caminho)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from ocr_pdf.__main__ import main  # noqa: E402

main()
