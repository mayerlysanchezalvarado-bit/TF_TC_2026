# -*- coding: utf-8 -*-
"""
lexer.py
--------
Analizador léxico del DSL de GASO AAA.

Gramática léxica soportada (una sentencia por línea):

    COMPRA <PRODUCTO> <NUM_INT> <NUM_DECIMAL>
    VENTA  <PRODUCTO> <NUM_INT> <NUM_DECIMAL>

Tokens reconocidos
-------------------
    PALABRA_RESERVADA   COMPRA | VENTA
    PRODUCTO             ^PROD-[A-Z]{3}-\\d{3}$
    NUM_INT               ^\\d+$
    NUM_DECIMAL           ^\\d+\\.\\d{2}$
    FECHA (opcional)      ^\\d{2}/\\d{2}/\\d{4}$   (se usa cuando el Excel trae fecha)

El lexer divide la entrada en lexemas (split por espacios), valida cada
lexema contra su expresión regular / autómata correspondiente, y produce
una lista de objetos Token con toda la metadata necesaria para que el
front-end pinte la tabla de "Lexemas y tokens".
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from afd import validar_producto, AFD_NUM_INT, AFD_NUM_DECIMAL, AFD_FECHA, AFD_COMPRA, AFD_VENTA


# ---------------------------------------------------------------------------
# Expresiones regulares oficiales del DSL (las mismas que se muestran en HTML)
# ---------------------------------------------------------------------------

RE_PALABRA_RESERVADA = re.compile(r"^(COMPRA|VENTA)$")
RE_PRODUCTO = re.compile(r"^PROD-[A-Z]{3}-\d{3}$")
RE_NUM_INT = re.compile(r"^\d+$")
RE_NUM_DECIMAL = re.compile(r"^\d+\.\d{2}$")
RE_FECHA = re.compile(r"^\d{2}/\d{2}/\d{4}$")

TOKEN_REGEX_TABLE = [
    {"token": "PALABRA_RESERVADA", "regex": "^(COMPRA|VENTA)$", "ejemplo": "COMPRA"},
    {"token": "PRODUCTO", "regex": r"^PROD-[A-Z]{3}-\d{3}$", "ejemplo": "PROD-AUD-001"},
    {"token": "NUM_INT", "regex": r"^\d+$", "ejemplo": "50"},
    {"token": "NUM_DECIMAL", "regex": r"^\d+\.\d{2}$", "ejemplo": "25.50"},
    {"token": "FECHA", "regex": r"^\d{2}/\d{2}/\d{4}$", "ejemplo": "15/05/2024"},
]


class LexicalError(Exception):
    def __init__(self, lexema: str, posicion: int, linea: str):
        self.lexema = lexema
        self.posicion = posicion
        self.linea = linea
        super().__init__(
            f"Error léxico: el lexema '{lexema}' (posición {posicion}) "
            f"no coincide con ningún token válido en la línea: '{linea}'"
        )


@dataclass
class Token:
    lexema: str
    tipo: str                 # PALABRA_RESERVADA | PRODUCTO | NUM_INT | NUM_DECIMAL | FECHA
    posicion: int              # posición (índice) dentro de la sentencia
    automata_traza: Optional[dict] = None   # traza del AFD usado para reconocerlo

    def to_dict(self):
        return {
            "lexema": self.lexema,
            "tipo": self.tipo,
            "posicion": self.posicion,
            "automata_traza": self.automata_traza,
        }


def clasificar_lexema(lexema: str, posicion: int) -> Token:
    """Intenta clasificar un lexema individual contra cada token definido,
    en orden de prioridad (palabra reservada > producto > decimal > entero > fecha)."""

    if RE_PALABRA_RESERVADA.match(lexema):
        afd = AFD_COMPRA if lexema == "COMPRA" else AFD_VENTA
        traza = afd.simular(lexema)
        return Token(lexema, "PALABRA_RESERVADA", posicion, traza)

    if RE_PRODUCTO.match(lexema):
        traza = validar_producto(lexema)
        return Token(lexema, "PRODUCTO", posicion, traza)

    if RE_NUM_DECIMAL.match(lexema):
        traza = AFD_NUM_DECIMAL.simular(lexema)
        return Token(lexema, "NUM_DECIMAL", posicion, traza)

    if RE_NUM_INT.match(lexema):
        traza = AFD_NUM_INT.simular(lexema)
        return Token(lexema, "NUM_INT", posicion, traza)

    if RE_FECHA.match(lexema):
        traza = AFD_FECHA.simular(lexema)
        return Token(lexema, "FECHA", posicion, traza)

    raise LexicalError(lexema, posicion, lexema)


def tokenize(sentencia: str) -> List[Token]:
    """
    Convierte una sentencia DSL completa (ej: "COMPRA PROD-AUD-001 50 25.50")
    en una lista de Tokens. Lanza LexicalError si algún lexema no es válido.
    """
    sentencia = sentencia.strip()
    if not sentencia:
        return []

    lexemas = sentencia.split()
    tokens = []
    for i, lex in enumerate(lexemas):
        try:
            tok = clasificar_lexema(lex, i)
        except LexicalError as e:
            e.linea = sentencia
            raise
        tokens.append(tok)
    return tokens


def tokenize_programa(codigo_dsl: str) -> List[dict]:
    """
    Tokeniza un programa DSL completo (múltiples líneas).
    Devuelve una lista de resultados por línea:
        [{ "linea": int, "texto": str, "tokens": [...], "error": str|None }, ...]
    Las líneas vacías o que empiezan con # (comentario) se ignoran del análisis
    pero se conservan para mostrar el código fuente completo.
    """
    resultados = []
    for num_linea, texto in enumerate(codigo_dsl.splitlines(), start=1):
        texto_limpio = texto.strip()
        if not texto_limpio or texto_limpio.startswith("#"):
            resultados.append({"linea": num_linea, "texto": texto, "tokens": [],
                                "error": None, "es_comentario_o_vacia": True})
            continue
        try:
            tokens = tokenize(texto_limpio)
            resultados.append({
                "linea": num_linea, "texto": texto,
                "tokens": [t.to_dict() for t in tokens],
                "error": None, "es_comentario_o_vacia": False,
            })
        except LexicalError as e:
            resultados.append({
                "linea": num_linea, "texto": texto, "tokens": [],
                "error": str(e), "es_comentario_o_vacia": False,
            })
    return resultados


def extraer_lexemas_unicos(codigo_dsl: str) -> List[dict]:
    """Devuelve la lista de lexemas únicos encontrados en todo el programa,
    junto a su tipo de token -- para la seccion 'Lexemas identificados'."""
    vistos = {}
    for resultado in tokenize_programa(codigo_dsl):
        for t in resultado["tokens"]:
            key = (t["lexema"], t["tipo"])
            if key not in vistos:
                vistos[key] = t
    return list(vistos.values())
