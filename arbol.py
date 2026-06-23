
"""
arbol.py
--------
Estructura de árbol sintáctico genérica, usada por parser.py para
representar la derivación de cada sentencia DSL según la Gramática
Libre de Contexto:

    S          -> Operacion
    Operacion  -> COMPRA Producto Cantidad Precio
    Operacion  -> VENTA  Producto Cantidad Precio
    Producto   -> PRODUCTO
    Cantidad   -> NUM_INT
    Precio     -> NUM_DECIMAL

Cada nodo guarda su símbolo gramatical (terminal o no-terminal) y,
si es una hoja, el lexema real que reconoció. `to_dict()` produce
una estructura serializable a JSON apta para dibujarse en el navegador
(SVG generado en JS) o para imprimirse como árbol ASCII en consola/HTML.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NodoArbol:
    simbolo: str                      
    es_terminal: bool = False
    hijos: List["NodoArbol"] = field(default_factory=list)

    def agregar(self, hijo: "NodoArbol"):
        self.hijos.append(hijo)
        return hijo

    def to_dict(self):
        return {
            "simbolo": self.simbolo,
            "es_terminal": self.es_terminal,
            "hijos": [h.to_dict() for h in self.hijos],
        }

    def to_ascii(self, prefijo: str = "", es_ultimo: bool = True) -> str:
        """Representación tipo árbol de directorios (└──/├──) para mostrar
        en un bloque <pre> como respaldo textual del árbol gráfico."""
        conector = "└── " if es_ultimo else "├── "
        linea = prefijo + (conector if prefijo else "") + self.simbolo
        lineas = [linea]
        nuevo_prefijo = prefijo + ("    " if es_ultimo else "│   ")
        for i, hijo in enumerate(self.hijos):
            es_ultimo_hijo = (i == len(self.hijos) - 1)
            lineas.append(hijo.to_ascii(nuevo_prefijo, es_ultimo_hijo))
        return "\n".join(lineas)

    def altura(self) -> int:
        if not self.hijos:
            return 1
        return 1 + max(h.altura() for h in self.hijos)

    def contar_nodos(self) -> int:
        return 1 + sum(h.contar_nodos() for h in self.hijos)
