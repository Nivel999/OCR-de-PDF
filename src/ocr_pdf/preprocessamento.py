"""Estratégias de pré-processamento de imagem antes do OCR.

Ideia geral para marca d'água: o texto do documento costuma ser escuro e sem cor,
enquanto marcas d'água são claras (cinza-claro) e/ou coloridas. Então:
  1. pixels com saturação alta (coloridos) viram branco;
  2. pixels claros (acima de um limiar) viram branco;
  3. o que sobra (texto escuro) é mantido em tons de cinza.
"""

from __future__ import annotations

from typing import Callable

import cv2
import numpy as np


def para_cinza(img_rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)


def estrategia_cinza(img_rgb: np.ndarray) -> np.ndarray:
    """Só converte para tons de cinza. Melhor para PDFs limpos e de boa qualidade."""
    return para_cinza(img_rgb)


def estrategia_otsu(img_rgb: np.ndarray) -> np.ndarray:
    """Binarização global com limiar automático (Otsu). Bom para scans com fundo uniforme."""
    cinza = cv2.GaussianBlur(para_cinza(img_rgb), (3, 3), 0)
    _, bin_ = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return bin_


def estrategia_adaptativo(img_rgb: np.ndarray) -> np.ndarray:
    """Limiar adaptativo local. Bom para iluminação irregular, sombras e fotos de documento."""
    cinza = cv2.medianBlur(para_cinza(img_rgb), 3)
    return cv2.adaptiveThreshold(
        cinza, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )


def remover_cores(img_rgb: np.ndarray, sat_min: int = 70, val_min: int = 60) -> np.ndarray:
    """Transforma em branco os pixels coloridos (marca d'água vermelha, azul, carimbos...)."""
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    colorido = (hsv[:, :, 1] > sat_min) & (hsv[:, :, 2] > val_min)
    saida = img_rgb.copy()
    saida[colorido] = 255
    return saida


def estrategia_marca_dagua(img_rgb: np.ndarray) -> np.ndarray:
    """Remove marca d'água colorida e cinza-clara, preservando o texto escuro.

    Não binariza: só "clareia" para branco o que está acima do limiar. O texto continua
    em tons de cinza (bordas suaves), que é o que o LSTM do Tesseract reconhece melhor.
    """
    cinza = para_cinza(remover_cores(img_rgb))

    # Limiar entre o texto (escuro) e a marca d'água (clara). Otsu é calculado só sobre
    # os pixels que não são fundo branco, assim separa melhor texto x marca d'água.
    nao_fundo = cinza[cinza < 240]
    if nao_fundo.size > 1000:
        limiar, _ = cv2.threshold(
            nao_fundo.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        limiar = float(np.clip(limiar, 110, 200))
    else:
        limiar = 160.0

    saida = cinza.copy()
    saida[cinza > limiar] = 255
    return saida


ESTRATEGIAS: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "cinza": estrategia_cinza,
    "otsu": estrategia_otsu,
    "adaptativo": estrategia_adaptativo,
    "marca_dagua": estrategia_marca_dagua,
}


def rotacionar(img: np.ndarray, graus: int) -> np.ndarray:
    """Rotaciona no sentido horário em múltiplos de 90 graus."""
    graus %= 360
    if graus == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if graus == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    if graus == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img
