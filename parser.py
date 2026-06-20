# -*- coding: utf-8 -*-
"""
parser.py
---------
Analizador sintáctico descendente recursivo (recursive-descent parser)
para el DSL de GASO AAA. Construye el árbol sintáctico siguiendo
exactamente la Gramática Libre de Contexto:

    G = (V, Σ, P, S)

    V = { S, Operacion, Producto, Cantidad, Precio }
    Σ = { COMPRA, VENTA, PRODUCTO, NUM_INT, NUM_DECIMAL }
    S = S

    P:
      1) S          -> Operacion
      2) Operacion  -> COMPRA Producto Cantidad Precio
      3) Operacion  -> VENTA  Producto Cantidad Precio
      4) Producto   -> PRODUCTO
      5) Cantidad   -> NUM_INT
      6) Precio     -> NUM_DECIMAL

El parser consume la lista de Tokens producida por lexer.py y, si la
secuencia es válida, retorna un NodoArbol (raíz = 'S'). Si la secuencia
no calza con la gramática (token inesperado, token faltante, token
sobrante) lanza un SyntaxErrorDSL con un mensaje claro indicando
qué se esperaba y qué se encontró -- pensado para mostrarse tal cual
en la interfaz web.
"""

from typing import List
from lexer import Token
from arbol import NodoArbol


class SyntaxErrorDSL(Exception):
    def __init__(self, mensaje: str, posicion: int = -1):
        self.mensaje = mensaje
        self.posicion = posicion
        super().__init__(mensaje)


class Parser:
    """Parser descendente recursivo de un solo nivel de profundidad real
    (la gramática del DSL es intencionalmente simple), pero implementado
    de forma genérica para que sea fácil de extender a más sentencias."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    # -- utilidades de navegación -------------------------------------------------
    def actual(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def avanzar(self) -> Token:
        tok = self.actual()
        self.pos += 1
        return tok

    def esperar(self, tipo_esperado: str) -> Token:
        tok = self.actual()
        if tok is None:
            raise SyntaxErrorDSL(
                f"Se esperaba un token de tipo '{tipo_esperado}' pero la sentencia terminó antes de tiempo.",
                self.pos,
            )
        if tok.tipo != tipo_esperado:
            raise SyntaxErrorDSL(
                f"Se esperaba un token de tipo '{tipo_esperado}' pero se encontró "
                f"'{tok.lexema}' (tipo {tok.tipo}) en la posición {tok.posicion}.",
                self.pos,
            )
        return self.avanzar()

    def esperar_palabra_reservada(self, palabra: str) -> Token:
        tok = self.actual()
        if tok is None or tok.tipo != "PALABRA_RESERVADA" or tok.lexema != palabra:
            encontrado = f"'{tok.lexema}'" if tok else "fin de la sentencia"
            raise SyntaxErrorDSL(
                f"Se esperaba la palabra reservada '{palabra}' pero se encontró {encontrado}.",
                self.pos,
            )
        return self.avanzar()

    # -- producciones ---------------------------------------------------------------
    def parse(self) -> NodoArbol:
        """S -> Operacion"""
        nodo_s = NodoArbol("S")
        nodo_operacion = self.operacion()
        nodo_s.agregar(nodo_operacion)

        if self.actual() is not None:
            sobrante = self.actual()
            raise SyntaxErrorDSL(
                f"Token sobrante e inesperado: '{sobrante.lexema}' después de completar la sentencia. "
                f"Cada sentencia debe tener exactamente 4 lexemas: PALABRA_RESERVADA PRODUCTO NUM_INT NUM_DECIMAL.",
                self.pos,
            )
        return nodo_s

    def operacion(self) -> NodoArbol:
        """Operacion -> COMPRA Producto Cantidad Precio
           Operacion -> VENTA  Producto Cantidad Precio"""
        tok = self.actual()
        if tok is None or tok.tipo != "PALABRA_RESERVADA":
            encontrado = f"'{tok.lexema}' (tipo {tok.tipo})" if tok else "una sentencia vacía"
            raise SyntaxErrorDSL(
                f"Toda sentencia debe iniciar con la palabra reservada COMPRA o VENTA. "
                f"Se encontró {encontrado}.",
                self.pos,
            )

        if tok.lexema == "COMPRA":
            op_token = self.esperar_palabra_reservada("COMPRA")
        elif tok.lexema == "VENTA":
            op_token = self.esperar_palabra_reservada("VENTA")
        else:
            raise SyntaxErrorDSL(f"Palabra reservada desconocida: '{tok.lexema}'.", self.pos)

        nodo_operacion = NodoArbol("Operacion")
        nodo_operacion.agregar(NodoArbol(op_token.lexema, es_terminal=True))
        nodo_operacion.agregar(self.producto())
        nodo_operacion.agregar(self.cantidad())
        nodo_operacion.agregar(self.precio())

        nodo_operacion._tipo_operacion = op_token.lexema  # metadato interno
        return nodo_operacion

    def producto(self) -> NodoArbol:
        """Producto -> PRODUCTO"""
        tok = self.esperar("PRODUCTO")
        nodo = NodoArbol("Producto")
        nodo.agregar(NodoArbol(tok.lexema, es_terminal=True))
        return nodo

    def cantidad(self) -> NodoArbol:
        """Cantidad -> NUM_INT"""
        tok = self.esperar("NUM_INT")
        nodo = NodoArbol("Cantidad")
        nodo.agregar(NodoArbol(tok.lexema, es_terminal=True))
        return nodo

    def precio(self) -> NodoArbol:
        """Precio -> NUM_DECIMAL"""
        tok = self.esperar("NUM_DECIMAL")
        nodo = NodoArbol("Precio")
        nodo.agregar(NodoArbol(tok.lexema, es_terminal=True))
        return nodo


def parsear_tokens(tokens: List[Token]) -> NodoArbol:
    """Punto de entrada simple: recibe tokens, devuelve el árbol (raíz S)."""
    parser = Parser(tokens)
    return parser.parse()


GRAMATICA_DSL = {
    "variables": ["S", "Operacion", "Producto", "Cantidad", "Precio"],
    "terminales": ["COMPRA", "VENTA", "PRODUCTO", "NUM_INT", "NUM_DECIMAL"],
    "simbolo_inicial": "S",
    "producciones": [
        "S → Operacion",
        "Operacion → COMPRA Producto Cantidad Precio",
        "Operacion → VENTA Producto Cantidad Precio",
        "Producto → PRODUCTO",
        "Cantidad → NUM_INT",
        "Precio → NUM_DECIMAL",
    ],
}
