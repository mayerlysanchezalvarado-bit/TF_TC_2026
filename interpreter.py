# -*- coding: utf-8 -*-
"""
interpreter.py
--------------
Recorre (evalúa) el árbol sintáctico producido por parser.py y lo
traduce a la estructura de datos final: un diccionario JSON con la
operación comercial ya tipada (cantidad como int, precio como float).

Esta es la fase de "traducción dirigida por la sintaxis" (syntax-directed
translation): cada producción de la gramática tiene asociada una regla
semántica que construye un fragmento del resultado final.

    Operacion -> COMPRA Producto Cantidad Precio
        { "operacion": "COMPRA", "producto": <Producto>,
          "cantidad": int(<Cantidad>), "precio": float(<Precio>) }

    Operacion -> VENTA Producto Cantidad Precio
        { "operacion": "VENTA", ... }
"""

from arbol import NodoArbol


class SemanticErrorDSL(Exception):
    pass


def interpretar(arbol: NodoArbol) -> dict:
    """
    arbol: nodo raíz 'S' devuelto por parser.parsear_tokens().
    Devuelve el diccionario JSON de la operación:
        {"operacion": "COMPRA", "producto": "PROD-AUD-001",
         "cantidad": 50, "precio": 25.5}
    """
    if arbol.simbolo != "S" or not arbol.hijos:
        raise SemanticErrorDSL("Árbol sintáctico inválido: se esperaba raíz 'S' con un hijo 'Operacion'.")

    nodo_operacion = arbol.hijos[0]
    if nodo_operacion.simbolo != "Operacion":
        raise SemanticErrorDSL("Árbol sintáctico inválido: falta el nodo 'Operacion'.")

    # hijos esperados: [terminal COMPRA/VENTA, Producto, Cantidad, Precio]
    terminal_op, nodo_producto, nodo_cantidad, nodo_precio = nodo_operacion.hijos

    tipo_operacion = terminal_op.simbolo  # "COMPRA" | "VENTA"
    producto = nodo_producto.hijos[0].simbolo
    cantidad_str = nodo_cantidad.hijos[0].simbolo
    precio_str = nodo_precio.hijos[0].simbolo

    try:
        cantidad = int(cantidad_str)
    except ValueError:
        raise SemanticErrorDSL(f"La cantidad '{cantidad_str}' no es un entero válido.")

    try:
        precio = float(precio_str)
    except ValueError:
        raise SemanticErrorDSL(f"El precio '{precio_str}' no es un decimal válido.")

    if cantidad <= 0:
        raise SemanticErrorDSL(f"La cantidad debe ser mayor a 0 (se recibió {cantidad}).")
    if precio <= 0:
        raise SemanticErrorDSL(f"El precio debe ser mayor a 0 (se recibió {precio}).")

    return {
        "operacion": tipo_operacion,
        "producto": producto,
        "cantidad": cantidad,
        "precio": precio,
        "total": round(cantidad * precio, 2),
    }


def compilar_sentencia(sentencia: str) -> dict:
    """
    Pipeline completo para UNA sentencia DSL:
        texto -> lexer -> parser -> interpreter -> JSON

    Devuelve un diccionario con TODAS las etapas intermedias, pensado
    para alimentar directamente la vista 'compiler.html':
        {
          "entrada": str,
          "tokens": [...],
          "arbol": {...} | None,
          "arbol_ascii": str | None,
          "resultado": {...} | None,
          "error_lexico": str | None,
          "error_sintactico": str | None,
          "error_semantico": str | None,
        }
    """
    from lexer import tokenize, LexicalError
    from parser import parsear_tokens, SyntaxErrorDSL

    salida = {
        "entrada": sentencia,
        "tokens": [],
        "arbol": None,
        "arbol_ascii": None,
        "resultado": None,
        "error_lexico": None,
        "error_sintactico": None,
        "error_semantico": None,
    }

    try:
        tokens = tokenize(sentencia)
    except LexicalError as e:
        salida["error_lexico"] = str(e)
        return salida

    salida["tokens"] = [t.to_dict() for t in tokens]

    try:
        arbol = parsear_tokens(tokens)
    except SyntaxErrorDSL as e:
        salida["error_sintactico"] = e.mensaje
        return salida

    salida["arbol"] = arbol.to_dict()
    salida["arbol_ascii"] = arbol.to_ascii()

    try:
        resultado = interpretar(arbol)
    except SemanticErrorDSL as e:
        salida["error_semantico"] = str(e)
        return salida

    salida["resultado"] = resultado
    return salida
