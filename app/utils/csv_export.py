"""
Geração de CSV das consultas do painel.

Saída em UTF-8 com BOM (﻿) pra Excel abrir os acentos certos.
Stdlib only — sem dependência nova.
"""
import csv
import io
from typing import Iterable

from ..models import Consulta


_COLUNAS = ["data_consulta", "numero_nf", "serie", "chave_nfe", "sucesso", "tentativas", "ultimo_erro"]


def _extrair_numero_serie(chave: str) -> tuple[str, str]:
    """
    Layout da chave NFe (44 dígitos): UF(2) AAMM(4) CNPJ(14) MOD(2) SERIE(3) NUM(9) TP(1) CN(8) DV(1).
    Retorna (numero, serie) como strings sem zeros à esquerda; ("", "") se chave inválida.
    """
    if not chave or len(chave) != 44 or not chave.isdigit():
        return "", ""
    serie = str(int(chave[22:25]))
    numero = str(int(chave[25:34]))
    return numero, serie


def gerar_csv_consultas(consultas: Iterable[Consulta]) -> bytes:
    buffer = io.StringIO()
    buffer.write("﻿")  # BOM pro Excel detectar UTF-8

    writer = csv.writer(buffer, delimiter=",", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(_COLUNAS)

    for c in consultas:
        numero, serie = _extrair_numero_serie(c.chave_nfe or "")
        writer.writerow([
            c.data_consulta.strftime("%Y-%m-%d %H:%M") if c.data_consulta else "",
            numero,
            serie,
            c.chave_nfe or "",
            "Sim" if c.sucesso else "Não",
            c.tentativas if c.tentativas is not None else "",
            (c.ultimo_erro or "").replace("\n", " ").replace("\r", " "),
        ])

    return buffer.getvalue().encode("utf-8")
