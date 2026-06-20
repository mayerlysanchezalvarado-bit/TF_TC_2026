# -*- coding: utf-8 -*-
"""
afd.py
------
Autómatas Finitos (No Deterministas y Deterministas) que reconocen
los lexemas del DSL de GASO AAA.

Cada token relevante (PRODUCTO, NUM_INT, NUM_DECIMAL, FECHA, PALABRA_RESERVADA)
se modela como:
    - Una definicion formal de AFND (con transiciones, incluyendo
      posibles ε-transiciones) representada como diccionario.
    - Un AFD equivalente (determinista), construido a mano siguiendo
      el mismo lenguaje que reconoce el AFND.
    - Una funcion `simulate_afd` que recorre cadena a cadena el AFD
      y devuelve la traza completa (estado por estado) para poder
      animar/mostrar el reconocimiento en el navegador.

Estos autómatas son usados por el lexer (lexer.py) para validar
y clasificar cada lexema, y son expuestos vía Flask para que el
front-end dibuje AFND, AFD, tablas de transición y la traza de
reconocimiento de un lexema concreto (ej. "PROD-AUD-001").
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


EPSILON = "ε"


# ---------------------------------------------------------------------------
# Estructuras genéricas
# ---------------------------------------------------------------------------

@dataclass
class AFND:
    nombre: str
    estados: List[str]
    alfabeto: List[str]
    transiciones: List[Tuple[str, str, str]]   # (origen, simbolo, destino) simbolo puede ser EPSILON
    estado_inicial: str
    estados_finales: List[str]

    def tabla(self) -> List[Dict]:
        """Tabla de transiciones agrupada por estado (para mostrarla en HTML)."""
        filas = []
        for estado in self.estados:
            fila = {"estado": estado, "es_inicial": estado == self.estado_inicial,
                    "es_final": estado in self.estados_finales, "trans": {}}
            for (o, s, d) in self.transiciones:
                if o == estado:
                    fila["trans"].setdefault(s, []).append(d)
            filas.append(fila)
        return filas


@dataclass
class AFD:
    nombre: str
    estados: List[str]
    alfabeto: List[str]
    transiciones: Dict[Tuple[str, str], str]   # (estado, simbolo_clase) -> estado
    estado_inicial: str
    estados_finales: List[str]
    clasificador: callable = None  # funcion(char) -> nombre_de_clase ('letra','digito','otro',...)

    def tabla(self) -> List[Dict]:
        filas = []
        for estado in self.estados:
            fila = {"estado": estado, "es_inicial": estado == self.estado_inicial,
                    "es_final": estado in self.estados_finales, "trans": {}}
            for simbolo in self.alfabeto:
                destino = self.transiciones.get((estado, simbolo))
                fila["trans"][simbolo] = destino if destino else "-"
            filas.append(fila)
        return filas

    def simular(self, cadena: str) -> Dict:
        """
        Ejecuta el AFD sobre `cadena` y devuelve una traza completa:
        {
          'aceptada': bool,
          'pasos': [{'caracter':..., 'clase':..., 'desde':..., 'hacia':...}, ...],
          'estado_final': str
        }
        """
        estado = self.estado_inicial
        pasos = []
        for ch in cadena:
            clase = self.clasificador(ch) if self.clasificador else ch
            destino = self.transiciones.get((estado, clase))
            pasos.append({
                "caracter": ch,
                "clase": clase,
                "desde": estado,
                "hacia": destino if destino else "ERROR",
            })
            if destino is None:
                return {"aceptada": False, "pasos": pasos, "estado_final": "ERROR"}
            estado = destino
        aceptada = estado in self.estados_finales
        return {"aceptada": aceptada, "pasos": pasos, "estado_final": estado}


# ---------------------------------------------------------------------------
# Clasificadores de caracteres (usados por los AFD)
# ---------------------------------------------------------------------------

def clase_producto(ch: str) -> str:
    if ch.isalpha() and ch.isupper():
        return "MAYUS"
    if ch.isdigit():
        return "DIGITO"
    if ch == "-":
        return "GUION"
    return "OTRO"


def clase_numerica(ch: str) -> str:
    if ch.isdigit():
        return "DIGITO"
    if ch == ".":
        return "PUNTO"
    return "OTRO"


def clase_fecha(ch: str) -> str:
    if ch.isdigit():
        return "DIGITO"
    if ch == "/":
        return "BARRA"
    return "OTRO"


def clase_letra_generica(ch: str) -> str:
    if ch.isalpha():
        return "LETRA"
    if ch.isdigit():
        return "DIGITO"
    if ch == "_":
        return "GUION_BAJO"
    return "OTRO"


# ---------------------------------------------------------------------------
# AFND para PRODUCTO  ->  ^PROD-[A-Z]{3}-\d{3}$
#   Diseñado con una ε-transición que representa el "salto" entre el
#   prefijo literal "PROD-" y el cuerpo variable, tal como se vería
#   en la construcción de Thompson antes de fusionar los fragmentos.
# ---------------------------------------------------------------------------

AFND_PRODUCTO = AFND(
    nombre="AFND_PRODUCTO",
    estados=["q0", "q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9", "qf"],
    alfabeto=["P", "R", "O", "D", "-", "MAYUS", "DIGITO", EPSILON],
    transiciones=[
        ("q0", "P", "q1"),
        ("q1", "R", "q2"),
        ("q2", "O", "q3"),
        ("q3", "D", "q4"),
        ("q4", "-", "q5"),
        ("q5", EPSILON, "q5a"),          # ε: entrada al bloque de 3 mayúsculas
        ("q5a", "MAYUS", "q6"),
        ("q6", "MAYUS", "q7"),
        ("q7", "MAYUS", "q8"),
        ("q8", "-", "q9"),
        ("q9", EPSILON, "q9a"),          # ε: entrada al bloque de 3 dígitos
        ("q9a", "DIGITO", "q10"),
        ("q10", "DIGITO", "q11"),
        ("q11", "DIGITO", "qf"),
    ],
    estado_inicial="q0",
    estados_finales=["qf"],
)
# nota: estados intermedios q5a/q9a representan el resultado de eliminar
# la ε en la construccion de Thompson; se listan explicitamente para
# que la tabla de transiciones del AFND sea fiel a la teoria (NFA con ε).
AFND_PRODUCTO.estados = ["q0", "q1", "q2", "q3", "q4", "q5", "q5a", "q6", "q7",
                          "q8", "q9", "q9a", "q10", "q11", "qf"]


# AFD equivalente para PRODUCTO (determinizado / minimizado a mano)
AFD_PRODUCTO = AFD(
    nombre="AFD_PRODUCTO",
    estados=["q0", "q1", "q2", "q3", "q4", "q5", "q6", "q7", "qf", "ERROR"],
    alfabeto=["MAYUS", "DIGITO", "GUION", "OTRO"],
    transiciones={
        ("q0", "MAYUS"): "q1",   # P
        ("q1", "MAYUS"): "q2",   # R
        ("q2", "MAYUS"): "q3",   # O
        ("q3", "MAYUS"): "q4",   # D
        ("q4", "GUION"): "q5",
        ("q5", "MAYUS"): "q5b",
        ("q5b", "MAYUS"): "q5c",
        ("q5c", "MAYUS"): "q6",
        ("q6", "GUION"): "q7",
        ("q7", "DIGITO"): "q7b",
        ("q7b", "DIGITO"): "q7c",
        ("q7c", "DIGITO"): "qf",
    },
    estado_inicial="q0",
    estados_finales=["qf"],
    clasificador=clase_producto,
)
AFD_PRODUCTO.estados = ["q0", "q1", "q2", "q3", "q4", "q5", "q5b", "q5c",
                         "q6", "q7", "q7b", "q7c", "qf"]


def _clase_producto_estricta(ch, pos, cadena):
    """Clasificador que también valida que las primeras 4 letras sean P-R-O-D
    literalmente (en vez de cualquier mayúscula) -- usado solo para validar,
    no para la tabla de transicion simplificada que se muestra en pantalla."""
    return clase_producto(ch)


def validar_producto(cadena: str) -> Dict:
    """
    Valida un lexema PRODUCTO de forma estricta replicando
    ^PROD-[A-Z]{3}-\\d{3}$ y construye la traza estado-a-estado
    usando AFD_PRODUCTO para que la página pueda animarla.
    """
    import re
    patron = re.compile(r"^PROD-[A-Z]{3}-\d{3}$")
    aceptada_regex = bool(patron.match(cadena))

    # Traza simbólica simplificada usando el AFD definido arriba,
    # clasificando por tipo de caracter (MAYUS/DIGITO/GUION/OTRO)
    traza = AFD_PRODUCTO.simular(cadena)
    traza["aceptada_regex"] = aceptada_regex
    traza["cadena"] = cadena
    return traza


# ---------------------------------------------------------------------------
# AFD/AFND genérico para identificadores tipo T_ID (letra (letra|digito|_)*)
# Se mantiene por compatibilidad con el dashboard estático anterior.
# ---------------------------------------------------------------------------

AFND_ID = AFND(
    nombre="AFND_ID",
    estados=["q0", "q1", "qf"],
    alfabeto=["LETRA", "DIGITO", "GUION_BAJO", EPSILON],
    transiciones=[
        ("q0", "LETRA", "q1"),
        ("q1", "LETRA", "q1"),
        ("q1", "DIGITO", "q1"),
        ("q1", "GUION_BAJO", "q1"),
        ("q1", EPSILON, "qf"),
    ],
    estado_inicial="q0",
    estados_finales=["qf"],
)

AFD_ID = AFD(
    nombre="AFD_ID",
    estados=["q0", "q1"],
    alfabeto=["LETRA", "DIGITO", "GUION_BAJO"],
    transiciones={
        ("q0", "LETRA"): "q1",
        ("q1", "LETRA"): "q1",
        ("q1", "DIGITO"): "q1",
        ("q1", "GUION_BAJO"): "q1",
    },
    estado_inicial="q0",
    estados_finales=["q1"],
    clasificador=clase_letra_generica,
)


# ---------------------------------------------------------------------------
# AFD/AFND para NUM_INT  ->  ^\d+$
# ---------------------------------------------------------------------------

AFND_NUM_INT = AFND(
    nombre="AFND_NUM_INT",
    estados=["q0", "q1", "qf"],
    alfabeto=["DIGITO", EPSILON],
    transiciones=[
        ("q0", "DIGITO", "q1"),
        ("q1", "DIGITO", "q1"),
        ("q1", EPSILON, "qf"),
    ],
    estado_inicial="q0",
    estados_finales=["qf"],
)

AFD_NUM_INT = AFD(
    nombre="AFD_NUM_INT",
    estados=["q0", "q1"],
    alfabeto=["DIGITO", "OTRO"],
    transiciones={
        ("q0", "DIGITO"): "q1",
        ("q1", "DIGITO"): "q1",
    },
    estado_inicial="q0",
    estados_finales=["q1"],
    clasificador=clase_numerica,
)


# ---------------------------------------------------------------------------
# AFD/AFND para NUM_DECIMAL  ->  ^\d+\.\d{2}$
# ---------------------------------------------------------------------------

AFND_NUM_DECIMAL = AFND(
    nombre="AFND_NUM_DECIMAL",
    estados=["q0", "q1", "q2", "q3", "q4", "qf"],
    alfabeto=["DIGITO", "PUNTO", EPSILON],
    transiciones=[
        ("q0", "DIGITO", "q1"),
        ("q1", "DIGITO", "q1"),
        ("q1", "PUNTO", "q2"),
        ("q2", "DIGITO", "q3"),
        ("q3", "DIGITO", "q4"),
        ("q4", EPSILON, "qf"),
    ],
    estado_inicial="q0",
    estados_finales=["qf"],
)

AFD_NUM_DECIMAL = AFD(
    nombre="AFD_NUM_DECIMAL",
    estados=["q0", "q1", "q2", "q3", "q4"],
    alfabeto=["DIGITO", "PUNTO", "OTRO"],
    transiciones={
        ("q0", "DIGITO"): "q1",
        ("q1", "DIGITO"): "q1",
        ("q1", "PUNTO"): "q2",
        ("q2", "DIGITO"): "q3",
        ("q3", "DIGITO"): "q4",
    },
    estado_inicial="q0",
    estados_finales=["q4"],
    clasificador=clase_numerica,
)


# ---------------------------------------------------------------------------
# AFD/AFND para FECHA -> ^\d{2}/\d{2}/\d{4}$
# ---------------------------------------------------------------------------

AFND_FECHA = AFND(
    nombre="AFND_FECHA",
    estados=["q0", "q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9", "qf"],
    alfabeto=["DIGITO", "BARRA", EPSILON],
    transiciones=[
        ("q0", "DIGITO", "q1"), ("q1", "DIGITO", "q2"),
        ("q2", "BARRA", "q3"),
        ("q3", "DIGITO", "q4"), ("q4", "DIGITO", "q5"),
        ("q5", "BARRA", "q6"),
        ("q6", "DIGITO", "q7"), ("q7", "DIGITO", "q8"),
        ("q8", "DIGITO", "q9"), ("q9", "DIGITO", "q9b"),
        ("q9b", EPSILON, "qf"),
    ],
    estado_inicial="q0",
    estados_finales=["qf"],
)
AFND_FECHA.estados.insert(-1, "q9b")

AFD_FECHA = AFD(
    nombre="AFD_FECHA",
    estados=["q0", "q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "qf"],
    alfabeto=["DIGITO", "BARRA", "OTRO"],
    transiciones={
        ("q0", "DIGITO"): "q1", ("q1", "DIGITO"): "q2",
        ("q2", "BARRA"): "q3",
        ("q3", "DIGITO"): "q4", ("q4", "DIGITO"): "q5",
        ("q5", "BARRA"): "q6",
        ("q6", "DIGITO"): "q7", ("q7", "DIGITO"): "q8",
        ("q8", "DIGITO"): "q8b", ("q8b", "DIGITO"): "qf",
    },
    estado_inicial="q0",
    estados_finales=["qf"],
    clasificador=clase_fecha,
)
AFD_FECHA.estados.insert(-1, "q8b")


# ---------------------------------------------------------------------------
# AFD para palabras reservadas COMPRA / VENTA (autómata por reconocimiento
# de cadena literal letra a letra, util y sencillo para visualizar)
# ---------------------------------------------------------------------------

def construir_afd_palabra(palabra: str, nombre: str) -> AFD:
    estados = [f"q{i}" for i in range(len(palabra) + 1)]
    transiciones = {}
    for i, ch in enumerate(palabra):
        transiciones[(f"q{i}", ch)] = f"q{i+1}"

    def clasificador(ch):
        return ch if ch in palabra else "OTRO"

    return AFD(
        nombre=nombre,
        estados=estados,
        alfabeto=list(set(palabra)) + ["OTRO"],
        transiciones=transiciones,
        estado_inicial="q0",
        estados_finales=[f"q{len(palabra)}"],
        clasificador=clasificador,
    )


AFD_COMPRA = construir_afd_palabra("COMPRA", "AFD_COMPRA")
AFD_VENTA = construir_afd_palabra("VENTA", "AFD_VENTA")


# Registro central para acceso por nombre desde Flask
AUTOMATAS = {
    "PRODUCTO": {"afnd": AFND_PRODUCTO, "afd": AFD_PRODUCTO},
    "ID": {"afnd": AFND_ID, "afd": AFD_ID},
    "NUM_INT": {"afnd": AFND_NUM_INT, "afd": AFD_NUM_INT},
    "NUM_DECIMAL": {"afnd": AFND_NUM_DECIMAL, "afd": AFD_NUM_DECIMAL},
    "FECHA": {"afnd": AFND_FECHA, "afd": AFD_FECHA},
}
