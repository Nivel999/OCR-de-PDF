"""Processa uma pasta de PDFs: extrai texto (nativo ou OCR) e, opcionalmente, gera resumos.

Uso:  python -m ocr_pdf [opções]      (rode com src/ no PYTHONPATH, ou use run.py na raiz)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
import urllib.request
from dataclasses import replace
from pathlib import Path

from .analise_imovel import consolidar_consistencia, extrair_dados_imovel
from .banco import BancoProcessamentoPDF, ConfigBanco, VERSAO_PIPELINE_PADRAO, calcular_sha256
from .config import RAIZ_PROJETO, ConfigOCR
from .extrator import Documento, extrair_pdf, reprocessar_paginas
from .preprocessamento import ESTRATEGIAS
from .qualidade import avaliar_confianca_ocr
from .resumo import criar_backend, resumir


def _baixar_pdf(link: str, destino: Path) -> None:
    """Baixa o PDF da URL cadastrada sem manter cópia permanente no worker."""
    requisicao = urllib.request.Request(link, headers={"User-Agent": "ocr-pdf-worker/1.0"})
    with urllib.request.urlopen(requisicao, timeout=300) as resposta, destino.open("wb") as arquivo:
        shutil.copyfileobj(resposta, arquivo)


def processar_banco(args: argparse.Namespace, cfg: ConfigOCR) -> int:
    """Consome a fila PostgreSQL e grava o resultado nas duas tabelas cadastradas."""
    banco = BancoProcessamentoPDF(ConfigBanco.do_ambiente(), args.worker)
    backend = criar_backend(args.llm, args.modelo)
    processados = 0

    for _ in range(args.lote):
        trabalho = banco.reservar_proximo(args.id_midia)
        if trabalho is None:
            break
        print(f"\n> mídia {trabalho.id_midia}: {trabalho.link}")
        try:
            with tempfile.TemporaryDirectory(prefix="ocr-pdf-") as diretorio:
                pdf = Path(diretorio) / "documento.pdf"
                _baixar_pdf(trabalho.link, pdf)
                sha256 = calcular_sha256(pdf)
                origem_id = banco.procurar_resultado_reutilizavel(
                    trabalho, sha256, args.versao_pipeline
                )
                if origem_id is not None:
                    banco.marcar_reutilizado(trabalho, origem_id, sha256, args.versao_pipeline)
                    print(f"  resultado reaproveitado da mídia {origem_id}")
                    processados += 1
                    continue

                doc = extrair_pdf(pdf, cfg)
                resumo = resumir(doc.texto, backend, args.tamanho_bloco) if backend is not None else None
                extracao = None
                if args.analise_imovel:
                    extracao = extrair_dados_imovel(
                        trabalho.nome or f"midia-{trabalho.id_midia}.pdf",
                        ((pagina.numero, pagina.texto) for pagina in doc.paginas),
                        backend,
                    )
                metricas = doc.resumo_metricas()
                banco.concluir(
                    trabalho, sha256, args.versao_pipeline, doc.texto, extracao, resumo,
                    metricas["confianca_media_ocr"],
                )
                print("  processamento concluído")
                processados += 1
        except Exception as erro:
            banco.falhar(trabalho, erro)
            print(f"  ERRO: {erro}")
    return processados


def ja_processado(pdf: Path, saida_txt: Path) -> bool:
    return saida_txt.exists() and saida_txt.stat().st_mtime >= pdf.stat().st_mtime


def _paginas_pendentes(trabalhos: list[tuple[Path, Documento, str]]) -> list[tuple[Path, Documento, str, int, int]]:
    """Retorna PDFs/páginas que precisam de uma nova tentativa com DPI maior."""
    pendentes = []
    for pdf, doc, nome in trabalhos:
        for pagina in doc.paginas:
            if pagina.metodo != "ocr":
                continue
            dpi_atual = pagina.dpi_ocr or doc.dpi_ocr
            avaliacao = avaliar_confianca_ocr(pagina.confianca, dpi_atual)
            proximo_dpi = avaliacao["proximo_dpi_sugerido"]
            if proximo_dpi is not None:
                pendentes.append((pdf, doc, nome, pagina.numero, proximo_dpi))
    return pendentes


def _reprocessar_paginas_pendentes(
    trabalhos: list[tuple[Path, Documento, str]], cfg: ConfigOCR, pasta_debug: Path
) -> None:
    """Pergunta e reprocessa em 400/600 DPI apenas as páginas abaixo da régua de qualidade."""
    if not trabalhos:
        return
    if not sys.stdin.isatty():
        print("Modo não interativo: páginas com baixa confiança não serão reprocessadas automaticamente.")
    else:
        while pendentes := _paginas_pendentes(trabalhos):
            print("\nPáginas que precisam de uma nova tentativa de OCR:")
            for pdf, _, _, numero, dpi in pendentes:
                print(f"  - {pdf.name}, página {numero}: reprocessar em {dpi} DPI")

            resposta = input("Deseja reprocessar essas páginas? [s/N] ").strip().lower()
            if resposta not in {"s", "sim", "y", "yes"}:
                break

            grupos: dict[tuple[Path, int], list[tuple[Documento, str, int]]] = {}
            for pdf, doc, nome, numero, dpi in pendentes:
                grupos.setdefault((pdf, dpi), []).append((doc, nome, numero))

            for (pdf, dpi), itens in grupos.items():
                doc = itens[0][0]
                nome = itens[0][1]
                numeros = [numero for _, _, numero in itens]
                print(f"  Reprocessando {pdf.name}, páginas {numeros}, em {dpi} DPI...")
                novas_paginas, segundos = reprocessar_paginas(
                    pdf,
                    replace(cfg, dpi=dpi),
                    numeros,
                    pasta_debug / nome if cfg.debug_imagens else None,
                )
                doc.atualizar_paginas(novas_paginas, segundos)

    for pdf, doc, _, in trabalhos:
        for pagina in doc.paginas:
            if pagina.metodo != "ocr":
                continue
            dpi_atual = pagina.dpi_ocr or doc.dpi_ocr
            avaliacao = avaliar_confianca_ocr(pagina.confianca, dpi_atual)
            if dpi_atual >= 600 and avaliacao["faixa"] in {"dificil", "baixa"}:
                print(
                    f"ATENÇÃO: {pdf.name}, página {pagina.numero} continua com {pagina.confianca:.0f}% "
                    "mesmo em 600 DPI. Revise esta página no PDF original."
                )


def processar_pasta(args: argparse.Namespace, cfg: ConfigOCR) -> int:
    entrada, saida = Path(args.entrada), Path(args.saida)
    pastas = {n: saida / n for n in ("textos", "relatorios", "resumos", "extracoes", "debug")}
    for n in ("textos", "relatorios"):
        pastas[n].mkdir(parents=True, exist_ok=True)

    backend = criar_backend(args.llm, args.modelo)
    pdfs = sorted(p for p in entrada.rglob("*") if p.suffix.lower() == ".pdf")
    processados = 0
    trabalhos: list[tuple[Path, Documento, str]] = []
    extracoes = []

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

        for p in doc.paginas:
            info = f"conf {p.confianca:.0f}% [{p.estrategia}]" if p.metodo == "ocr" else ""
            if p.rotacao:
                info += f" rotacionada {p.rotacao}°"
            print(f"  pág {p.numero:>3}: {p.metodo:<6} {len(p.texto):>6} chars  {info}  ({p.motivo})")
        trabalhos.append((pdf, doc, nome))
        processados += 1

    _reprocessar_paginas_pendentes(trabalhos, cfg, pastas["debug"])

    for _, doc, nome in trabalhos:
        txt = pastas["textos"] / f"{nome}.txt"
        txt.write_text(doc.texto, encoding="utf-8")
        (pastas["relatorios"] / f"{nome}.json").write_text(
            json.dumps(doc.para_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
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
        if args.analise_imovel:
            pastas["extracoes"].mkdir(parents=True, exist_ok=True)
            try:
                extracao = extrair_dados_imovel(
                    doc.arquivo, ((pagina.numero, pagina.texto) for pagina in doc.paginas), backend
                )
                (pastas["extracoes"] / f"{nome}.json").write_text(
                    json.dumps(extracao, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                extracoes.append(extracao)
                print("  dados do imóvel extraídos")
            except Exception as e:
                print(f"  ERRO na extração de dados do imóvel: {e}")

    if args.analise_imovel and extracoes:
        (saida / "consistencia_imovel.json").write_text(
            json.dumps(consolidar_consistencia(extracoes), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  consistência dos imóveis -> {saida / 'consistencia_imovel.json'}")

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
    ap.add_argument("--analise-imovel", action="store_true",
                    help="extrai dados imobiliários estruturados e compara consistência entre PDFs (exige --llm)")
    ap.add_argument("--modelo", help="modelo da LLM (ex.: qwen2.5:7b no Ollama)")
    ap.add_argument("--tamanho-bloco", type=int, default=12000,
                    help="máx. de caracteres por chamada à LLM (textos maiores são divididos)")
    ap.add_argument("--monitorar", type=int, metavar="SEGUNDOS",
                    help="fica vigiando a pasta de entrada, verificando a cada N segundos")
    ap.add_argument("--banco", action="store_true",
                    help="consome cadastro.midia_processamento_pdf em vez de usar entrada/ e saida/")
    ap.add_argument("--lote", type=int, default=1,
                    help="quantidade máxima de PDFs da fila a processar por execução (padrão: 1)")
    ap.add_argument("--id-midia", type=int,
                    help="processa somente este id_midia pendente; recomendado para testes")
    ap.add_argument("--worker", help="identificação deste worker no banco (padrão: nome do computador)")
    ap.add_argument("--versao-pipeline", default=VERSAO_PIPELINE_PADRAO,
                    help="versão usada para decidir se um PDF idêntico pode ser reaproveitado")
    args = ap.parse_args(argv)
    if args.analise_imovel and args.llm == "nenhum":
        ap.error("--analise-imovel exige selecionar uma LLM com --llm ollama ou --llm anthropic")
    if args.lote < 1:
        ap.error("--lote deve ser maior ou igual a 1")

    cfg = ConfigOCR(idioma=args.idioma, dpi=600 if args.banco else args.dpi, estrategia=args.estrategia, psm=args.psm,
                    forcar_ocr=args.forcar_ocr, debug_imagens=args.debug_imagens)
    if args.workers:
        cfg.workers = args.workers

    if args.banco:
        if not args.monitorar:
            try:
                n = processar_banco(args, cfg)
            except RuntimeError as erro:
                ap.error(str(erro))
            print(f"\n{n} PDF(s) processado(s) pelo banco.")
            return
        print(f"Monitorando a fila do banco a cada {args.monitorar}s (Ctrl+C para sair)...")
        try:
            while True:
                try:
                    processar_banco(args, cfg)
                except RuntimeError as erro:
                    ap.error(str(erro))
                time.sleep(args.monitorar)
        except KeyboardInterrupt:
            sys.exit(0)

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
