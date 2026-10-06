"""Geração de resumo com LLM.

Backends:
  - "ollama":    LLM local (ex.: um modelo 7B) servido pelo Ollama. É o alvo do projeto final.
  - "anthropic": Claude via API, para testes/comparação de qualidade.

Modelos 7B têm contexto curto, então textos longos são resumidos em blocos
(map) e depois os resumos parciais são combinados (reduce).
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Protocol

PROMPT_SISTEMA = (
    "Você é um assistente que resume documentos em português do Brasil. "
    "O texto foi extraído de um PDF, possivelmente por OCR, e pode conter erros de "
    "reconhecimento, quebras de linha estranhas ou restos de marca d'água — ignore esses ruídos. "
    "Seja fiel ao conteúdo: não invente informações que não estão no texto."
)

PROMPT_BLOCO = (
    "Resuma o trecho abaixo (parte {i} de {n} de um documento). Liste os fatos principais, "
    "nomes, datas, valores e números de documentos que aparecerem.\n\n<trecho>\n{texto}\n</trecho>"
)

PROMPT_FINAL = (
    "Escreva um resumo do documento abaixo em Markdown, com:\n"
    "1. **Tipo de documento** (uma linha)\n"
    "2. **Resumo** (um parágrafo curto)\n"
    "3. **Pontos principais** (lista)\n"
    "4. **Dados importantes**: nomes, datas, valores, números de processo/contrato, se houver\n\n"
    "<documento>\n{texto}\n</documento>"
)


class Backend(Protocol):
    def gerar(self, sistema: str, mensagem: str) -> str: ...


class BackendOllama:
    def __init__(self, modelo: str, url: str | None = None, num_ctx: int = 8192):
        self.modelo = modelo
        self.url = (url or os.environ.get("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.num_ctx = num_ctx

    def gerar(self, sistema: str, mensagem: str) -> str:
        corpo = {
            "model": self.modelo,
            "stream": False,
            "options": {"num_ctx": self.num_ctx, "temperature": 0.2},
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": mensagem},
            ],
        }
        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(corpo).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read())["message"]["content"].strip()


class BackendAnthropic:
    def __init__(self, modelo: str = "claude-opus-5-5"):
        import anthropic  # opcional: só é necessário para este backend

        self.cliente = anthropic.Anthropic()
        self.modelo = modelo

    def gerar(self, sistema: str, mensagem: str) -> str:
        resposta = self.cliente.beta.messages.create(
            model=self.modelo,
            max_tokens=16000,
            system=sistema,
            messages=[{"role": "user", "content": mensagem}],
            output_config={"effort": "low"},
            # Se a requisição for recusada pelos filtros, o servidor tenta outro modelo.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resposta.stop_reason == "refusal":
            raise RuntimeError("O modelo recusou gerar o resumo deste documento.")
        return "".join(b.text for b in resposta.content if b.type == "text").strip()


def criar_backend(nome: str, modelo: str | None) -> Backend | None:
    if nome == "nenhum":
        return None
    if nome == "ollama":
        return BackendOllama(modelo or "qwen2.5:7b")
    if nome == "anthropic":
        return BackendAnthropic(modelo or "claude-opus-5-5")
    raise ValueError(f"Backend de LLM desconhecido: {nome}")


def dividir_em_blocos(texto: str, tamanho: int) -> list[str]:
    """Divide em blocos de até `tamanho` caracteres, quebrando preferencialmente entre parágrafos."""
    if len(texto) <= tamanho:
        return [texto]
    blocos, atual = [], ""
    for paragrafo in texto.split("\n\n"):
        while len(paragrafo) > tamanho:  # parágrafo gigante: corta no meio
            if atual:
                blocos.append(atual)
                atual = ""
            blocos.append(paragrafo[:tamanho])
            paragrafo = paragrafo[tamanho:]
        if atual and len(atual) + len(paragrafo) + 2 > tamanho:
            blocos.append(atual)
            atual = paragrafo
        else:
            atual = f"{atual}\n\n{paragrafo}" if atual else paragrafo
    if atual:
        blocos.append(atual)
    return blocos


def resumir(texto: str, backend: Backend, tamanho_bloco: int = 12000, _nivel: int = 0) -> str:
    blocos = dividir_em_blocos(texto, tamanho_bloco)
    if len(blocos) > 1:
        parciais = [
            backend.gerar(PROMPT_SISTEMA, PROMPT_BLOCO.format(i=i, n=len(blocos), texto=b))
            for i, b in enumerate(blocos, start=1)
        ]
        texto = "\n\n".join(parciais)
        # Se mesmo os resumos parciais forem longos demais, resume de novo.
        if len(texto) > tamanho_bloco and _nivel < 3:
            return resumir(texto, backend, tamanho_bloco, _nivel + 1)
    return backend.gerar(PROMPT_SISTEMA, PROMPT_FINAL.format(texto=texto))
