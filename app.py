# -*- coding: utf-8 -*-
"""
app.py
------
Aplicación Flask que conecta todo el pipeline del DSL de GASO AAA:

    Excel -> DSL -> Lexer -> Parser -> Árbol Sintáctico -> JSON -> Dashboard

Rutas principales
------------------
    GET  /                      Página de inicio: cargar Excel o escribir DSL a mano
    POST /cargar-excel          Procesa un Excel subido, compila cada fila, redirige a /compilador
    POST /compilar-manual       Compila un programa DSL escrito a mano por el usuario
    GET  /compilador            Vista del pipeline de compilación (lexer/AFD/AFND/parser/árbol/JSON)
    GET  /dashboard             Dashboard estadístico final
    GET  /api/automata/<token>  JSON con AFND/AFD/tabla de transición de un token (para dibujar en JS)
    GET  /api/reconocer/<token>/<cadena>  Traza de reconocimiento de una cadena concreta
    GET  /descargar-ejemplo     Descarga el Excel de ejemplo

El estado "actual" (operaciones compiladas en la última carga) se
guarda en memoria de proceso (variable global) para simplicidad
académica -- no hay base de datos, todo vive mientras el servidor
está corriendo.
"""

import os
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash

from lexer import tokenize_programa, extraer_lexemas_unicos, TOKEN_REGEX_TABLE
from parser import GRAMATICA_DSL
from interpreter import compilar_sentencia
from excel_to_dsl import excel_a_sentencias, generar_excel_ejemplo
from json_gen import construir_dashboard, nombre_producto
from afd import AUTOMATAS, validar_producto, AFD_NUM_INT, AFD_NUM_DECIMAL, AFD_FECHA, AFD_COMPRA, AFD_VENTA


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
SAMPLE_DIR = os.path.join(BASE_DIR, "sample_data")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SAMPLE_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "gaso-aaa-dsl-academico-2024"

ESTADO = {
    "programa_dsl": "",           
    "resultados_compilacion": [], 
    "operaciones": [],            
    "advertencias_excel": [],     
    "origen": None,               
    "nombre_archivo": None,
}


EJEMPLO_DSL_DEFECTO = (
    "COMPRA PROD-AUD-001 50 25.00\n"
    "VENTA PROD-AUD-001 40 45.00\n"
    "COMPRA PROD-MOU-001 30 45.00\n"
    "VENTA PROD-MOU-001 25 70.00\n"
)


def _recompilar_programa(texto_dsl: str):
    """Corre el programa DSL completo a través de lexer+parser+interpreter,
    actualiza ESTADO con resultados por línea y con las operaciones válidas."""
    resultados = []
    operaciones = []

    for linea_info in tokenize_programa(texto_dsl):
        if linea_info["es_comentario_o_vacia"]:
            continue
        texto = linea_info["texto"].strip()
        if not texto:
            continue
        resultado = compilar_sentencia(texto)
        resultado["numero_linea"] = linea_info["linea"]
        resultados.append(resultado)
        if resultado["resultado"]:
            op = dict(resultado["resultado"])
            op["sentencia"] = texto
            op["fecha"] = None
            op["contraparte"] = None
            op["nombre_producto"] = nombre_producto(op["producto"])
            operaciones.append(op)

    ESTADO["programa_dsl"] = texto_dsl
    ESTADO["resultados_compilacion"] = resultados
    ESTADO["operaciones"] = operaciones
    return resultados, operaciones


@app.route("/")
def index():
    return render_template(
        "index.html",
        ejemplo_dsl=EJEMPLO_DSL_DEFECTO,
        token_regex_table=TOKEN_REGEX_TABLE,
        gramatica=GRAMATICA_DSL,
        tiene_resultados=bool(ESTADO["operaciones"]),
        origen=ESTADO["origen"],
        nombre_archivo=ESTADO["nombre_archivo"],
    )


@app.route("/cargar-excel", methods=["POST"])
def cargar_excel():
    archivo = request.files.get("archivo_excel")
    if not archivo or archivo.filename == "":
        flash("No se seleccionó ningún archivo Excel.", "error")
        return redirect(url_for("index"))

    ruta_guardado = os.path.join(UPLOAD_DIR, archivo.filename)
    archivo.save(ruta_guardado)

    try:
        filas_validas, advertencias = excel_a_sentencias(ruta_guardado)
    except Exception as e:
        flash(f"No se pudo leer el Excel: {e}", "error")
        return redirect(url_for("index"))

    if not filas_validas:
        flash("El Excel no tiene filas válidas para compilar.", "error")
        return redirect(url_for("index"))

    lineas_dsl = [f["sentencia"] for f in filas_validas]
    texto_dsl = "\n".join(lineas_dsl)
    resultados, operaciones = _recompilar_programa(texto_dsl)

    for op, fila in zip(operaciones, filas_validas):
        op["fecha"] = fila["fecha"]
        op["contraparte"] = fila["contraparte"]

    ESTADO["advertencias_excel"] = advertencias
    ESTADO["origen"] = "excel"
    ESTADO["nombre_archivo"] = archivo.filename

    flash(f"Excel procesado: {len(filas_validas)} filas válidas, {len(advertencias)} advertencias.", "success")
    return redirect(url_for("compilador"))


@app.route("/compilar-manual", methods=["POST"])
def compilar_manual():
    texto_dsl = request.form.get("codigo_dsl", "").strip()
    if not texto_dsl:
        flash("Escribe al menos una sentencia DSL.", "error")
        return redirect(url_for("index"))

    _recompilar_programa(texto_dsl)
    ESTADO["advertencias_excel"] = []
    ESTADO["origen"] = "manual"
    ESTADO["nombre_archivo"] = None

    return redirect(url_for("compilador"))


@app.route("/compilador")
def compilador():
    if not ESTADO["resultados_compilacion"]:
        flash("Aún no has compilado ningún programa. Carga un Excel o escribe DSL manualmente.", "error")
        return redirect(url_for("index"))

    lexemas_unicos = extraer_lexemas_unicos(ESTADO["programa_dsl"])

    ejemplo_destacado = next(
        (r for r in ESTADO["resultados_compilacion"] if r["resultado"]), None
    )

    return render_template(
        "compiler.html",
        programa_dsl=ESTADO["programa_dsl"],
        resultados=ESTADO["resultados_compilacion"],
        lexemas_unicos=lexemas_unicos,
        token_regex_table=TOKEN_REGEX_TABLE,
        gramatica=GRAMATICA_DSL,
        ejemplo_destacado=ejemplo_destacado,
        advertencias_excel=ESTADO["advertencias_excel"],
        origen=ESTADO["origen"],
        nombre_archivo=ESTADO["nombre_archivo"],
        total_operaciones=len(ESTADO["operaciones"]),
        automatas_meta=[
            {"clave": "PRODUCTO", "titulo": "AFND/AFD para PRODUCTO", "ejemplo": "PROD-AUD-001"},
            {"clave": "NUM_INT", "titulo": "AFND/AFD para NUM_INT", "ejemplo": "50"},
            {"clave": "NUM_DECIMAL", "titulo": "AFND/AFD para NUM_DECIMAL", "ejemplo": "25.00"},
        ],
    )


@app.route("/dashboard")
def dashboard():
    if not ESTADO["operaciones"]:
        flash("Aún no hay operaciones compiladas para mostrar en el dashboard.", "error")
        return redirect(url_for("index"))

    datos = construir_dashboard(ESTADO["operaciones"])
    return render_template(
        "dashboard.html",
        datos=datos,
        origen=ESTADO["origen"],
        nombre_archivo=ESTADO["nombre_archivo"],
        periodo="Mayo 2024" if ESTADO["origen"] == "excel" else "Sesión manual",
    )

@app.route("/api/automata/<token>")
def api_automata(token):
    token = token.upper()
    if token not in AUTOMATAS:
        return jsonify({"error": f"No existe autómata definido para el token '{token}'."}), 404

    afnd = AUTOMATAS[token]["afnd"]
    afd = AUTOMATAS[token]["afd"]
    return jsonify({
        "token": token,
        "afnd": {
            "nombre": afnd.nombre,
            "estados": afnd.estados,
            "alfabeto": afnd.alfabeto,
            "transiciones": afnd.transiciones,
            "estado_inicial": afnd.estado_inicial,
            "estados_finales": afnd.estados_finales,
            "tabla": afnd.tabla(),
        },
        "afd": {
            "nombre": afd.nombre,
            "estados": afd.estados,
            "alfabeto": afd.alfabeto,
            "estado_inicial": afd.estado_inicial,
            "estados_finales": afd.estados_finales,
            "tabla": afd.tabla(),
                        
            "transiciones": [[o, s, d] for (o, s), d in afd.transiciones.items()],
        },
    })


@app.route("/api/reconocer/<token>/<path:cadena>")
def api_reconocer(token, cadena):
    token = token.upper()
    if token == "PRODUCTO":
        traza = validar_producto(cadena)
    elif token == "NUM_INT":
        traza = AFD_NUM_INT.simular(cadena)
        traza["cadena"] = cadena
    elif token == "NUM_DECIMAL":
        traza = AFD_NUM_DECIMAL.simular(cadena)
        traza["cadena"] = cadena
    elif token == "FECHA":
        traza = AFD_FECHA.simular(cadena)
        traza["cadena"] = cadena
    elif token == "COMPRA":
        traza = AFD_COMPRA.simular(cadena)
        traza["cadena"] = cadena
    elif token == "VENTA":
        traza = AFD_VENTA.simular(cadena)
        traza["cadena"] = cadena
    else:
        return jsonify({"error": f"Token '{token}' no soportado."}), 404

    return jsonify(traza)


@app.route("/api/compilar-sentencia", methods=["POST"])
def api_compilar_sentencia():
    """Compila UNA sentencia individual al vuelo (usado por el campo
    'Probar tu propia sentencia' en la vista del compilador)."""
    sentencia = request.json.get("sentencia", "").strip()
    if not sentencia:
        return jsonify({"error": "Sentencia vacía."}), 400
    resultado = compilar_sentencia(sentencia)
    return jsonify(resultado)


@app.route("/descargar-ejemplo")
def descargar_ejemplo():
    ruta = os.path.join(SAMPLE_DIR, "operaciones_ejemplo.xlsx")
    if not os.path.exists(ruta):
        generar_excel_ejemplo(ruta)
    return send_file(ruta, as_attachment=True, download_name="operaciones_ejemplo_gaso_aaa.xlsx")


@app.route("/reiniciar")
def reiniciar():
    ESTADO["programa_dsl"] = ""
    ESTADO["resultados_compilacion"] = []
    ESTADO["operaciones"] = []
    ESTADO["advertencias_excel"] = []
    ESTADO["origen"] = None
    ESTADO["nombre_archivo"] = None
    flash("Sesión reiniciada.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    if not os.path.exists(os.path.join(SAMPLE_DIR, "operaciones_ejemplo.xlsx")):
        generar_excel_ejemplo(os.path.join(SAMPLE_DIR, "operaciones_ejemplo.xlsx"))
    app.run(debug=True, host="0.0.0.0", port=5000)
