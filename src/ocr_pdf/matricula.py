"""Separação da matrícula de imóvel em abertura e atos (R-n / AV-n), sem LLM.

A matrícula é uma cadeia: a abertura (identificação do imóvel e proprietários iniciais) seguida de
registros (R-1, R-2, ...) e averbações (AV-3, ...) numerados em uma única sequência. Separar os atos
deixa cada chamada da LLM com o texto de um ato só e permite calcular os proprietários atuais em
código, aplicando as transmissões em ordem.

O texto vem do OCR e chega com ruído nos marcadores ("R—-1-1.559s-", "AV=2=-1,523:", "A V.17/105."),
por isso o marcador é procurado com uma regex tolerante e só é aceito quando o número da matrícula
que o acompanha confere com o desta matrícula e a numeração forma uma sequência crescente.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field


# Início de ato no começo da linha: tipo (R ou AV), número do ato e número da matrícula, com os
# separadores que o OCR costuma trocar (-, =, —, ., /). "R$", "BR-280" e "nº 3/R=222" não casam.
# Nos números, o OCR troca "1" por "l"/"I" e "0" por "O" (o PaddleOCR leu "R-l-l.559:").
_MARCADOR_ATO = re.compile(
    r"^[^\w\n]{0,3}(?P<tipo>R|A[ \t]?[Vv])[ \t]*[-=—–.]*[ \t]*(?P<numero>[\dlIO]{1,3})"
    r"[ \t]*[-=—–/.]+[ \t]*(?P<matricula>[\dlIO](?:[\d.,lIO]*[\dlIO])?)",
    re.MULTILINE,
)
_LETRA_PARA_ALGARISMO = str.maketrans("lIO", "110")
_NUMERO_MATRICULA = re.compile(r"Matr[íi]cula\s*N[º°o]\s*[.:]?\s*(\d(?:[\d.,]*\d)?)", re.IGNORECASE)
# Rótulo da abertura em maiúsculas seguido de dois-pontos no começo da linha ("PROPRIETÁRIOS:-",
# "TITULO AQUISITIVO:"). O OCR troca letras ("PRCPRIBTÁRIO:-"), então o nome é comparado por semelhança.
_ROTULO_ABERTURA = re.compile(r"^[^\w\n]*(?P<rotulo>[A-ZÀ-Ü][A-ZÀ-Ü() ]{3,30}?)\s*:", re.MULTILINE)
_ENCERRAMENTO = re.compile(r"encerrad[ao]\s+a\s+presente\s+matr[íi]cula|ENCERRAMENTO", re.IGNORECASE)
_TRANSFERIDA_PARA = re.compile(r"transferid[ao]\s+para\s+a\s+matr[íi]cula\s*n?[º°o]?\s*(\d(?:[\d.,]*\d)?)", re.IGNORECASE)

# CNPJ antes do CPF: os 11 primeiros dígitos de um CNPJ formatado também parecem um CPF.
_CNPJ = re.compile(r"(?<!\d)\d{2}[ .]{0,2}\d{3}[ .]{0,2}\d{3}[ ./]{0,2}\d{4}[ .\-]{0,2}\d{2}(?!\d)")
_CPF = re.compile(r"(?<!\d)\d{3}[ .\-]{0,2}\d{3}[ .\-]{0,2}\d{3}[ .\-/]{0,2}\d{2}(?!\d)")


@dataclass
class Ato:
    tipo: str  # "R" (registro) ou "AV" (averbação)
    numero: int
    pagina_inicial: int
    pagina_final: int
    texto: str
    documentos: list[dict[str, object]] = field(default_factory=list)

    @property
    def rotulo(self) -> str:
        return f"{self.tipo}-{self.numero}"


@dataclass
class Matricula:
    numero: str | None
    abertura: str
    proprietarios_abertura: str
    atos: list[Ato]
    atos_ausentes: list[int]
    documentos_abertura: list[dict[str, object]] = field(default_factory=list)
    encerrada: bool = False
    transferida_para: str | None = None
    alertas: list[str] = field(default_factory=list)


def _digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def _numero_lido(texto: str) -> str:
    """Dígitos de um número do marcador, desfazendo as trocas de letra do OCR."""
    return _digitos(texto.translate(_LETRA_PARA_ALGARISMO))


def _distancia_edicao(a: str, b: str) -> int:
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (ca != cb)))
        anterior = atual
    return anterior[-1]


def _mesma_matricula(lido: str, esperado: str) -> bool:
    """Aceita um dígito trocado, sobrando ou faltando (ex.: "1056" lido no lugar de "105")."""
    return _distancia_edicao(lido, esperado) <= 1


def _maior_subsequencia_crescente(numeros: list[int]) -> list[int]:
    """Índices da maior subsequência estritamente crescente (descarta números lidos errado)."""
    if not numeros:
        return []
    tamanho = [1] * len(numeros)
    anterior = [-1] * len(numeros)
    for i in range(len(numeros)):
        for j in range(i):
            if numeros[j] < numeros[i] and tamanho[j] + 1 > tamanho[i]:
                tamanho[i], anterior[i] = tamanho[j] + 1, j
    # Em empate, prefere a sequência que termina antes: o fim tende a ser o ato mais recente legível.
    fim = max(range(len(numeros)), key=lambda i: (tamanho[i], -i))
    indices = []
    while fim != -1:
        indices.append(fim)
        fim = anterior[fim]
    return indices[::-1]


def validar_cpf(digitos: str) -> bool:
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    for posicao in (9, 10):
        soma = sum(int(d) * peso for d, peso in zip(digitos[:posicao], range(posicao + 1, 1, -1)))
        if (soma * 10 % 11) % 10 != int(digitos[posicao]):
            return False
    return True


def validar_cnpj(digitos: str) -> bool:
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False
    for posicao in (12, 13):
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][13 - posicao:]
        resto = sum(int(d) * p for d, p in zip(digitos[:posicao], pesos)) % 11
        if (0 if resto < 2 else 11 - resto) != int(digitos[posicao]):
            return False
    return True


def documentos_no_texto(texto: str) -> list[dict[str, object]]:
    """CPFs e CNPJs escritos no texto, na ordem, com o dígito verificador conferido.

    ``valido = False`` indica leitura errada do OCR ou outro número (identidade, protocolo) com o
    mesmo formato; esses não devem ser gravados como CPF/CNPJ.
    """
    achados: list[tuple[int, dict[str, object]]] = []
    ocupado: list[tuple[int, int]] = []
    for tipo, regex, validar in (("cnpj", _CNPJ, validar_cnpj), ("cpf", _CPF, validar_cpf)):
        for achado in regex.finditer(texto):
            if any(inicio < achado.end() and achado.start() < fim for inicio, fim in ocupado):
                continue
            digitos = _digitos(achado.group(0))
            ocupado.append(achado.span())
            achados.append((achado.start(), {
                "tipo": tipo, "numero": digitos, "valido": validar(digitos), "trecho": achado.group(0),
            }))
    return [documento for _, documento in sorted(achados, key=lambda item: item[0])]


def _numero_da_matricula(paginas: list[tuple[int, str]], candidatos: list[str]) -> str | None:
    # O número que mais acompanha os marcadores de ato é mais confiável que o cabeçalho, que é uma
    # leitura só e pode estar borrada.
    if candidatos:
        return Counter(candidatos).most_common(1)[0][0]
    for _, texto in paginas:
        achado = _NUMERO_MATRICULA.search(texto)
        if achado:
            return _digitos(achado.group(1))
    return None


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def _proprietarios_da_abertura(abertura: str) -> str:
    rotulos = list(_ROTULO_ABERTURA.finditer(abertura))
    for indice, rotulo in enumerate(rotulos):
        nome = re.sub(r"[^A-Z]", "", _sem_acento(rotulo["rotulo"]))
        if min(_distancia_edicao(nome, alvo) for alvo in ("PROPRIETARIO", "PROPRIETARIOS")) <= 3:
            fim = rotulos[indice + 1].start() if indice + 1 < len(rotulos) else len(abertura)
            return " ".join(abertura[rotulo.end(): fim].lstrip(":-– ").split())
    return ""


def _recuperar_numeros(candidatos: list, aceitos: list[int]) -> list[tuple[int, int]]:
    """Recupera marcadores descartados cujo número tem um dígito a mais (ex.: "AV=23" no lugar de AV-3).

    Devolve (índice do candidato, número corrigido) quando tirar um dígito faz o número caber
    entre o ato aceito anterior e o seguinte.
    """
    usados = {int(_numero_lido(candidatos[i][1]["numero"])) for i in aceitos}
    recuperados = []
    for indice, (_, achado) in enumerate(candidatos):
        if indice in aceitos:
            continue
        anterior = max((int(_numero_lido(candidatos[i][1]["numero"])) for i in aceitos if i < indice), default=0)
        seguinte = min((int(_numero_lido(candidatos[i][1]["numero"])) for i in aceitos if i > indice), default=10**4)
        lido = _numero_lido(achado["numero"])
        for posicao in range(len(lido)):
            variante = lido[:posicao] + lido[posicao + 1:]
            if variante and anterior < int(variante) < seguinte and int(variante) not in usados:
                recuperados.append((indice, int(variante)))
                usados.add(int(variante))
                break
    return recuperados


def separar_atos(paginas: list[tuple[int, str]]) -> Matricula:
    """Divide o texto da matrícula (página, texto) em abertura e atos, na ordem do documento."""
    candidatos = [
        (pagina, achado)
        for pagina, texto in paginas
        for achado in _MARCADOR_ATO.finditer(texto)
    ]
    numero = _numero_da_matricula(paginas, [_numero_lido(a["matricula"]) for _, a in candidatos])
    if numero:
        candidatos = [(p, a) for p, a in candidatos if _mesma_matricula(_numero_lido(a["matricula"]), numero)]
    indices = _maior_subsequencia_crescente([int(_numero_lido(a["numero"])) for _, a in candidatos])
    numero_ato = {i: int(_numero_lido(candidatos[i][1]["numero"])) for i in indices}
    corrigidos = _recuperar_numeros(candidatos, indices)
    numero_ato.update(corrigidos)
    aceitos = [(candidatos[i][0], candidatos[i][1], numero_ato[i]) for i in sorted(numero_ato)]

    texto_por_pagina = dict(paginas)
    ordem_paginas = [pagina for pagina, _ in paginas]

    def trecho(pagina_ini: int, pos_ini: int, pagina_fim: int, pos_fim: int | None) -> str:
        partes = []
        for pagina in ordem_paginas[ordem_paginas.index(pagina_ini): ordem_paginas.index(pagina_fim) + 1]:
            texto = texto_por_pagina[pagina]
            inicio = pos_ini if pagina == pagina_ini else 0
            fim = pos_fim if pagina == pagina_fim else None
            partes.append(texto[inicio:fim])
        return "\n".join(parte.strip() for parte in partes if parte.strip())

    ultima_pagina = ordem_paginas[-1] if ordem_paginas else 0
    atos = []
    for indice, (pagina, achado, numero_lido) in enumerate(aceitos):
        if indice + 1 < len(aceitos):
            pagina_fim, proximo, _ = aceitos[indice + 1]
            texto = trecho(pagina, achado.start(), pagina_fim, proximo.start())
            # O próximo ato começar no topo de uma página não estende este até lá.
            if not texto_por_pagina[pagina_fim][: proximo.start()].strip():
                pagina_fim = ordem_paginas[ordem_paginas.index(pagina_fim) - 1]
        else:
            pagina_fim = ultima_pagina
            texto = trecho(pagina, achado.start(), pagina_fim, None)
        tipo = "AV" if achado["tipo"].upper().replace(" ", "").replace("\t", "") == "AV" else "R"
        atos.append(Ato(tipo, numero_lido, pagina, pagina_fim, texto, documentos_no_texto(texto)))

    if aceitos:
        primeira_pagina, primeiro, _ = aceitos[0]
        abertura = trecho(ordem_paginas[0], 0, primeira_pagina, primeiro.start())
    else:
        abertura = "\n".join(texto.strip() for _, texto in paginas)

    numeros = {ato.numero for ato in atos}
    ausentes = [n for n in range(1, max(numeros) + 1) if n not in numeros] if numeros else []
    proprietarios = _proprietarios_da_abertura(abertura)
    matricula = Matricula(
        numero=numero,
        abertura=abertura,
        proprietarios_abertura=proprietarios,
        atos=atos,
        atos_ausentes=ausentes,
        documentos_abertura=documentos_no_texto(proprietarios),
    )
    for indice, corrigido in corrigidos:
        lido = candidatos[indice][1].group(0).strip()
        matricula.alertas.append(f"Marcador \"{lido}\" lido como ato {corrigido} (número do OCR com dígito a mais).")
    for ato in reversed(atos):
        if _ENCERRAMENTO.search(ato.texto):
            matricula.encerrada = True
            destino = _TRANSFERIDA_PARA.search(ato.texto)
            matricula.transferida_para = _digitos(destino.group(1)) if destino else None
            matricula.alertas.append(f"Matrícula encerrada no {ato.rotulo}.")
            break
    if not numero:
        matricula.alertas.append("Número da matrícula não encontrado.")
    if not atos:
        matricula.alertas.append("Nenhum ato (R-n/AV-n) encontrado.")
    if ausentes:
        lista = ", ".join(str(n) for n in ausentes)
        matricula.alertas.append(f"Atos não encontrados no texto (OCR ilegível?): {lista}.")
    if not matricula.proprietarios_abertura:
        matricula.alertas.append("Proprietários da abertura não encontrados.")
    return matricula
