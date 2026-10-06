"""Processa uma pasta de PDFs: extrai texto (nativo ou OCR) e, opcionalmente, gera resumos.

Uso:  python -m ocr_pdf [opções]      (rode com src/ no PYTHONPATH, ou use run.py na raiz)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .config import RAIZ_PROJETO, ConfigOCR
from .extrator import extrair_pdf
from .preprocessamento import ESTRATEGIAS
from .resumo import criar_backend, resumir


def ja_processado(pdf: Path, saida_txt: Path) -> bool:
    return saida_txt.exists() and saida_txt.stat().st_mtime >= pdf.stat().st_mtime


def processar_pasta(args: argparse.Namespace, cfg: ConfigOCR) -> int:
    entrada, saida = Path(args.entrada), Path(args.saida)
    pastas = {n: saida / n for n in ("textos", "relatorios", "resumos", "debug")}
    for n in ("textos", "relatorios"):
        pastas[n].mkdir(parents=True, exist_ok=True)

    backend = criar_backend(args.llm, args.modelo)
    pdfs = sorted(p for p in entrada.rglob("*") if p.suffix.lower() == ".pdf")
    processados = 0

    for pdf in pdfs:
        nome = pdf.relative_to(entrada).with_suffix("").as_posix().replace("/", "__")
        txt = pastas["textos"] / f"{nome}.txt"
        if not args.reprocessar and ja_processado(pdf, txt):
            continue

        print(f"\n> {pdf.relative_to(entrada)}")
        try:
            doc = extrair_pdf(pdf, cfg, pastas["debug"] / nome if cfg.debug_imagens else None)
        except Exception as e:  # um PDF corrompido não deve parar o lote todo
            print(f"  ERRO ao ler: {e}")
            continue

        txt.write_text(doc.texto, encoding="utf-8")
        (pastas["relatorios"] / f"{nome}.json").write_text(
            json.dumps(doc.para_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for p in doc.paginas:
            info = f"conf {p.confianca:.0f}% [{p.estrategia}]" if p.metodo == "ocr" else ""
            if p.rotacao:
                info += f" rotacionada {p.rotacao}°"
            print(f"  pág {p.numero:>3}: {p.metodo:<6} {len(p.texto):>6} chars  {info}  ({p.motivo})")
        m = doc.resumo_metricas()
        print(f"  total: {m['paginas']} págs ({m['paginas_ocr']} OCR), {m['segundos']}s -> {txt}")

        if backend is not None:
            pastas["resumos"].mkdir(parents=True, exist_ok=True)
            try:
                resumo = resumir(doc.texto, backend, args.tamanho_bloco)
                (pastas["resumos"] / f"{nome}.md").write_text(resumo, encoding="utf-8")
                print("  resumo gerado")
            except Exception as e:
                print(f"  ERRO no resumo: {e}")
        processados += 1

    return processados


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="ocr_pdf", description=__doc__.splitlines()[0])
    ap.add_argument("--entrada", default=str(RAIZ_PROJETO / "entrada"), help="pasta com os PDFs")
    ap.add_argument("--saida", default=str(RAIZ_PROJETO / "saida"), help="pasta de resultados")
    ap.add_argument("--idioma", default="por", help="idioma(s) do Tesseract, ex.: por ou por+eng")
    ap.add_argument("--dpi", type=int, default=300, help="resolução para renderizar páginas (300 é o ideal)")
    ap.add_argument("--estrategia", default="auto", choices=["auto", *ESTRATEGIAS],
                    help="pré-processamento; 'auto' testa várias e escolhe a melhor")
    ap.add_argument("--psm", type=int, default=3, help="modo de segmentação de página do Tesseract")
    ap.add_argument("--forcar-ocr", action="store_true", help="faz OCR mesmo em páginas com texto nativo")
    ap.add_argument("--workers", type=int, help="páginas processadas em paralelo")
    ap.add_argument("--debug-imagens", action="store_true",
                    help="salva as imagens pré-processadas em saida/debug/")
    ap.add_argument("--reprocessar", action="store_true", help="refaz PDFs que já têm saída")
    ap.add_argument("--llm", default="nenhum", choices=["nenhum", "ollama", "anthropic"],
                    help="backend para gerar resumos")
    ap.add_argument("--modelo", help="modelo da LLM (ex.: qwen2.5:7b no Ollama)")
    ap.add_argument("--tamanho-bloco", type=int, default=12000,
                    help="máx. de caracteres por chamada à LLM (textos maiores são divididos)")
    ap.add_argument("--monitorar", type=int, metavar="SEGUNDOS",
                    help="fica vigiando a pasta de entrada, verificando a cada N segundos")
    args = ap.parse_args(argv)

    cfg = ConfigOCR(idioma=args.idioma, dpi=args.dpi, estrategia=args.estrategia, psm=args.psm,
                    forcar_ocr=args.forcar_ocr, debug_imagens=args.debug_imagens)
    if args.workers:
        cfg.workers = args.workers

    if not args.monitorar:
        n = processar_pasta(args, cfg)
        print(f"\n{n} PDF(s) processado(s).")
        return

    print(f"Monitorando {args.entrada} a cada {args.monitorar}s (Ctrl+C para sair)...")
    try:
        while True:
            processar_pasta(args, cfg)
            time.sleep(args.monitorar)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
