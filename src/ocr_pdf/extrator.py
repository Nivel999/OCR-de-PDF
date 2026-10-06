"""Extrai o texto de um PDF página a página, decidindo entre texto nativo e OCR."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytesseract

from .config import ConfigOCR
from .ocr import ocr_pagina
from .qualidade import avaliar_confianca_ocr


@dataclass
class Pagina:
    numero: int
    metodo: str  # "nativo" ou "ocr"
    motivo: str  # por que esse método foi escolhido
    texto: str
    confianca: float | None = None
    estrategia: str | None = None
    rotacao: int = 0
    dpi_ocr: int | None = None


@dataclass
class Documento:
    arquivo: str
    dpi_ocr: int = 300
    paginas: list[Pagina] = field(default_factory=list)
    segundos: float = 0.0

    @property
    def texto(self) -> str:
        return "\n\n".join(f"--- Página {p.numero} ---\n{p.texto}" for p in self.paginas)

    def resumo_metricas(self) -> dict:
        ocr = [p for p in self.paginas if p.metodo == "ocr"]
        confs = [p.confianca for p in ocr if p.confianca is not None]
        avaliacoes = [
            (p, avaliar_confianca_ocr(p.confianca, p.dpi_ocr or self.dpi_ocr)) for p in ocr
        ]
        faixas = {nome: 0 for nome in ("confiavel", "aceitavel", "dificil", "baixa")}
        for _, avaliacao in avaliacoes:
            faixas[avaliacao["faixa"]] += 1

        paginas_revisao = [p.numero for p, avaliacao in avaliacoes if avaliacao["revisao_recomendada"]]
        paginas_novo_ocr = [
            {
                "pagina": p.numero,
                "dpi_atual": p.dpi_ocr or self.dpi_ocr,
                "proximo_dpi_sugerido": avaliacao["proximo_dpi_sugerido"],
            }
            for p, avaliacao in avaliacoes
            if avaliacao["proximo_dpi_sugerido"] is not None
        ]
        return {
            "arquivo": self.arquivo,
            "paginas": len(self.paginas),
            "paginas_nativas": len(self.paginas) - len(ocr),
            "paginas_ocr": len(ocr),
            "dpi_ocr": self.dpi_ocr,
            "confianca_media_ocr": round(sum(confs) / len(confs), 1) if confs else None,
            "confianca_minima_ocr": min(confs) if confs else None,
            "faixas_confianca_ocr": faixas,
            "paginas_para_revisao": paginas_revisao,
            "paginas_sugeridas_para_novo_ocr": paginas_novo_ocr,
            "caracteres": sum(len(p.texto) for p in self.paginas),
            "segundos": round(self.segundos, 1),
        }

    def para_dict(self) -> dict:
        paginas = []
        for pagina in self.paginas:
            item = asdict(pagina)
            if pagina.metodo == "ocr":
                item["qualidade_ocr"] = avaliar_confianca_ocr(
                    pagina.confianca, pagina.dpi_ocr or self.dpi_ocr
                )
            paginas.append(item)
        return {"metricas": self.resumo_metricas(), "paginas": paginas}

    def atualizar_paginas(self, atualizadas: dict[int, Pagina], segundos_adicionais: float) -> None:
        """Substitui páginas por novas leituras OCR, mantendo a ordem do documento."""
        self.paginas = [atualizadas.get(p.numero, p) for p in self.paginas]
        self.segundos += segundos_adicionais


def _proporcao_lixo(texto: str) -> float:
    """Fração de caracteres "estranhos" — PDFs com fonte mal mapeada geram texto ilegível."""
    if not texto:
        return 0.0
    ruins = sum(1 for c in texto if c == "�" or (not c.isprintable() and c not in "\n\t"))
    return ruins / len(texto)


def _cobertura_imagens(pagina: pymupdf.Page) -> float:
    """Quanto da área da página é coberta por imagens (0 a 1)."""
    area_pagina = abs(pagina.rect)
    if not area_pagina:
        return 0.0
    area = 0.0
    for info in pagina.get_image_info():
        area += abs(pymupdf.Rect(info["bbox"]) & pagina.rect)
    return min(area / area_pagina, 1.0)


def decidir_metodo(pagina: pymupdf.Page, texto_nativo: str, cfg: ConfigOCR) -> tuple[str, str]:
    if cfg.forcar_ocr:
        return "ocr", "forçado por parâmetro"
    n = len(texto_nativo.strip())
    if n < cfg.min_chars_texto_nativo:
        return "ocr", f"pouco texto nativo ({n} caracteres)"
    if _proporcao_lixo(texto_nativo) > 0.2:
        return "ocr", "texto nativo ilegível (fonte mal mapeada)"
    cobertura = _cobertura_imagens(pagina)
    if cobertura > 0.6 and n < 300:
        return "ocr", f"página é basicamente imagem ({cobertura:.0%}) com pouco texto"
    return "nativo", "PDF já tem texto"


def _renderizar(pagina: pymupdf.Page, dpi: int) -> np.ndarray:
    pix = pagina.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()


def _preparar_ocr(cfg: ConfigOCR) -> None:
    pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_cmd
    if cfg.tessdata_dir:
        os.environ["TESSDATA_PREFIX"] = cfg.tessdata_dir
    # Com várias páginas em paralelo, cada Tesseract usa 1 thread (evita disputa de CPU).
    if cfg.workers > 1:
        os.environ.setdefault("OMP_THREAD_LIMIT", "1")


def _processar_ocr(
    numero: int, img: np.ndarray, motivo: str, cfg: ConfigOCR, pasta_debug: Path | None
) -> Pagina:
    res, imagens = ocr_pagina(img, cfg)
    if pasta_debug is not None:
        pasta_debug.mkdir(parents=True, exist_ok=True)
        for nome, im in imagens.items():
            cv2.imwrite(str(pasta_debug / f"p{numero:03d}_{nome}.png"), im)
    return Pagina(
        numero,
        "ocr",
        motivo,
        res.texto,
        res.confianca,
        res.estrategia,
        res.rotacao,
        dpi_ocr=cfg.dpi,
    )


def extrair_pdf(caminho: Path, cfg: ConfigOCR, pasta_debug: Path | None = None) -> Documento:
    _preparar_ocr(cfg)

    inicio = time.perf_counter()
    doc = Documento(arquivo=caminho.name, dpi_ocr=cfg.dpi)
    resultados: dict[int, Pagina] = {}

    with pymupdf.open(caminho) as pdf, ThreadPoolExecutor(max_workers=cfg.workers) as pool:
        pendentes = []
        for i, pagina in enumerate(pdf, start=1):
            texto_nativo = pagina.get_text("text", sort=True)
            metodo, motivo = decidir_metodo(pagina, texto_nativo, cfg)
            if metodo == "nativo":
                resultados[i] = Pagina(i, "nativo", motivo, texto_nativo.strip())
                continue
            # A renderização (PyMuPDF) fica na thread principal; só o OCR vai para o pool.
            img = _renderizar(pagina, cfg.dpi)
            pendentes.append(pool.submit(_processar_ocr, i, img, motivo, cfg, pasta_debug))
            # Limita quantas páginas renderizadas ficam em memória ao mesmo tempo.
            if len(pendentes) >= cfg.workers * 2:
                p = pendentes.pop(0).result()
                resultados[p.numero] = p
        for f in pendentes:
            p = f.result()
            resultados[p.numero] = p

    doc.paginas = [resultados[n] for n in sorted(resultados)]
    doc.segundos = time.perf_counter() - inicio
    return doc


def reprocessar_paginas(
    caminho: Path, cfg: ConfigOCR, numeros: list[int], pasta_debug: Path | None = None
) -> tuple[dict[int, Pagina], float]:
    """Executa OCR novamente somente nas páginas indicadas, usando o DPI de ``cfg``."""
    _preparar_ocr(cfg)
    inicio = time.perf_counter()
    atualizadas: dict[int, Pagina] = {}

    with pymupdf.open(caminho) as pdf:
        for numero in sorted(set(numeros)):
            pagina = pdf[numero - 1]
            img = _renderizar(pagina, cfg.dpi)
            atualizadas[numero] = _processar_ocr(
                numero,
                img,
                f"reprocessada em {cfg.dpi} DPI após confiança baixa",
                cfg,
                pasta_debug,
            )

    return atualizadas, time.perf_counter() - inicio
