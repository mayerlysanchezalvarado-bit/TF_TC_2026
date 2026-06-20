# -*- coding: utf-8 -*-
"""
excel_to_dsl.py
---------------
Convierte un archivo Excel con operaciones comerciales (filas de
compra/venta) en sentencias del DSL de GASO AAA, una por fila.

Formato esperado del Excel (encabezados flexibles, no sensibles a
mayúsculas/acentos):

    operacion | producto       | cantidad | precio | fecha       | cliente_o_proveedor
    COMPRA    | PROD-AUD-001   | 50       | 25.50  | 15/05/2024  | Importaciones SAC
    VENTA     | PROD-MOU-001   | 25       | 70.00  | 20/05/2024  | Cliente A

Reglas de normalización:
    - 'operacion' se pasa a mayúsculas; sinónimos comunes
      (compra/compras/purchase -> COMPRA, venta/ventas/sale -> VENTA).
    - 'producto' se castea a string y se limpia de espacios.
    - 'cantidad' se castea a entero.
    - 'precio' se formatea siempre con 2 decimales (NUM_DECIMAL exige \\d+\\.\\d{2}).
    - Filas con datos faltantes o inválidos se reportan como advertencias
      pero no detienen el procesamiento de las demás filas.
"""

import re
import pandas as pd
from typing import List, Dict, Tuple


COLUMNAS_ALIAS = {
    "operacion": ["operacion", "operación", "tipo", "tipo_operacion", "movimiento"],
    "producto": ["producto", "producto_codigo", "codigo_producto", "sku", "código"],
    "cantidad": ["cantidad", "cant", "cant.", "qty"],
    "precio": ["precio", "precio_unitario", "precio unit.", "precio_unit", "p.unit", "precio unit"],
    "fecha": ["fecha", "fecha_operacion", "date"],
    "contraparte": ["proveedor", "cliente", "contraparte", "cliente_proveedor", "tercero"],
}

SINONIMOS_OPERACION = {
    "compra": "COMPRA", "compras": "COMPRA", "purchase": "COMPRA", "buy": "COMPRA",
    "venta": "VENTA", "ventas": "VENTA", "sale": "VENTA", "sell": "VENTA",
}


def _normalizar_columnas(df: pd.DataFrame) -> Dict[str, str]:
    """Detecta qué columna real del Excel corresponde a cada campo lógico."""
    mapeo = {}
    columnas_lower = {c.lower().strip(): c for c in df.columns}
    for campo, alias_list in COLUMNAS_ALIAS.items():
        for alias in alias_list:
            if alias in columnas_lower:
                mapeo[campo] = columnas_lower[alias]
                break
    return mapeo


def _normalizar_operacion(valor) -> str:
    txt = str(valor).strip().lower()
    return SINONIMOS_OPERACION.get(txt, str(valor).strip().upper())


def _normalizar_producto(valor) -> str:
    return str(valor).strip().upper()


def _normalizar_precio(valor) -> str:
    """Devuelve el precio como string con exactamente 2 decimales."""
    f = float(valor)
    return f"{f:.2f}"


def excel_a_sentencias(filepath: str) -> Tuple[List[Dict], List[Dict]]:
    """
    Lee el Excel y devuelve (filas_validas, advertencias):

      filas_validas: lista de dicts:
          {"fila_excel": int, "sentencia": "COMPRA PROD-AUD-001 50 25.50",
           "fecha": "15/05/2024" | None, "contraparte": str | None}

      advertencias: lista de dicts:
          {"fila_excel": int, "motivo": str, "datos_originales": dict}
    """
    df = pd.read_excel(filepath)
    mapeo = _normalizar_columnas(df)

    requeridos = ["operacion", "producto", "cantidad", "precio"]
    faltantes = [r for r in requeridos if r not in mapeo]
    if faltantes:
        raise ValueError(
            f"El Excel no tiene columnas reconocibles para: {', '.join(faltantes)}. "
            f"Columnas encontradas: {list(df.columns)}"
        )

    filas_validas = []
    advertencias = []

    for idx, row in df.iterrows():
        fila_excel = idx + 2  # +2: encabezado ocupa fila 1, idx es 0-based
        datos_originales = row.to_dict()
        try:
            if row[mapeo["operacion"]] is None or pd.isna(row[mapeo["operacion"]]):
                raise ValueError("falta el tipo de operación (COMPRA/VENTA)")
            if row[mapeo["producto"]] is None or pd.isna(row[mapeo["producto"]]):
                raise ValueError("falta el código de producto")
            if pd.isna(row[mapeo["cantidad"]]):
                raise ValueError("falta la cantidad")
            if pd.isna(row[mapeo["precio"]]):
                raise ValueError("falta el precio")

            operacion = _normalizar_operacion(row[mapeo["operacion"]])
            if operacion not in ("COMPRA", "VENTA"):
                raise ValueError(f"tipo de operación desconocido: '{row[mapeo['operacion']]}'")

            producto = _normalizar_producto(row[mapeo["producto"]])
            if not re.match(r"^PROD-[A-Z]{3}-\d{3}$", producto):
                raise ValueError(
                    f"el código de producto '{producto}' no respeta el formato PROD-XXX-000"
                )

            cantidad = int(float(row[mapeo["cantidad"]]))
            if cantidad <= 0:
                raise ValueError(f"la cantidad debe ser mayor a 0 (se recibió {cantidad})")

            precio_str = _normalizar_precio(row[mapeo["precio"]])
            if float(precio_str) <= 0:
                raise ValueError(f"el precio debe ser mayor a 0 (se recibió {precio_str})")

            sentencia = f"{operacion} {producto} {cantidad} {precio_str}"

            fecha = None
            if "fecha" in mapeo and not pd.isna(row[mapeo["fecha"]]):
                fecha_val = row[mapeo["fecha"]]
                if hasattr(fecha_val, "strftime"):
                    fecha = fecha_val.strftime("%d/%m/%Y")
                else:
                    fecha = str(fecha_val)

            contraparte = None
            if "contraparte" in mapeo and not pd.isna(row[mapeo["contraparte"]]):
                contraparte = str(row[mapeo["contraparte"]]).strip()

            filas_validas.append({
                "fila_excel": fila_excel,
                "sentencia": sentencia,
                "fecha": fecha,
                "contraparte": contraparte,
            })

        except Exception as e:
            advertencias.append({
                "fila_excel": fila_excel,
                "motivo": str(e),
                "datos_originales": {k: (None if pd.isna(v) else v) for k, v in datos_originales.items()},
            })

    return filas_validas, advertencias


def generar_excel_ejemplo(filepath: str):
    """
    Genera el Excel de ejemplo "oficial" de GASO AAA: operaciones de
    compra/venta de enero a mayo 2024, con precios y cantidades simples
    y redondas (pensadas para que el dashboard se vea limpio y coherente,
    sin perseguir un total "mágico" exacto).
    """
    filas = [
        # ---- COMPRAS (mayo 2024) ------------------------------------------
        {"operacion": "COMPRA", "producto": "PROD-AUD-001", "cantidad": 50, "precio": 25.00,
         "fecha": "15/05/2024", "contraparte": "Importaciones SAC"},
        {"operacion": "COMPRA", "producto": "PROD-MOU-001", "cantidad": 30, "precio": 45.00,
         "fecha": "16/05/2024", "contraparte": "Global Tech"},
        {"operacion": "COMPRA", "producto": "PROD-TEC-001", "cantidad": 20, "precio": 30.00,
         "fecha": "17/05/2024", "contraparte": "Asia Supply"},
        {"operacion": "COMPRA", "producto": "PROD-MON-001", "cantidad": 15, "precio": 300.00,
         "fecha": "08/05/2024", "contraparte": "Pacific Imports"},
        {"operacion": "COMPRA", "producto": "PROD-LAP-001", "cantidad": 5, "precio": 1500.00,
         "fecha": "05/05/2024", "contraparte": "Importaciones SAC"},

        # ---- VENTAS (mayo 2024) --------------------------------------------
        {"operacion": "VENTA", "producto": "PROD-AUD-001", "cantidad": 40, "precio": 45.00,
         "fecha": "20/05/2024", "contraparte": "Cliente A"},
        {"operacion": "VENTA", "producto": "PROD-MOU-001", "cantidad": 25, "precio": 70.00,
         "fecha": "21/05/2024", "contraparte": "Cliente B"},
        {"operacion": "VENTA", "producto": "PROD-TEC-001", "cantidad": 15, "precio": 55.00,
         "fecha": "22/05/2024", "contraparte": "Cliente C"},
        {"operacion": "VENTA", "producto": "PROD-MON-001", "cantidad": 12, "precio": 450.00,
         "fecha": "10/05/2024", "contraparte": "Cliente D"},
        {"operacion": "VENTA", "producto": "PROD-LAP-001", "cantidad": 4, "precio": 1900.00,
         "fecha": "12/05/2024", "contraparte": "Cliente E"},

        # ---- abril 2024 -------------------------------------------------------
        {"operacion": "COMPRA", "producto": "PROD-AUD-001", "cantidad": 35, "precio": 25.00,
         "fecha": "03/04/2024", "contraparte": "Importaciones SAC"},
        {"operacion": "COMPRA", "producto": "PROD-MOU-001", "cantidad": 18, "precio": 45.00,
         "fecha": "10/04/2024", "contraparte": "Global Tech"},
        {"operacion": "VENTA", "producto": "PROD-AUD-001", "cantidad": 28, "precio": 45.00,
         "fecha": "15/04/2024", "contraparte": "Cliente A"},
        {"operacion": "VENTA", "producto": "PROD-MOU-001", "cantidad": 16, "precio": 70.00,
         "fecha": "20/04/2024", "contraparte": "Cliente B"},

        # ---- marzo 2024 ---------------------------------------------------------
        {"operacion": "COMPRA", "producto": "PROD-TEC-001", "cantidad": 15, "precio": 30.00,
         "fecha": "05/03/2024", "contraparte": "Asia Supply"},
        {"operacion": "VENTA", "producto": "PROD-TEC-001", "cantidad": 12, "precio": 55.00,
         "fecha": "18/03/2024", "contraparte": "Cliente C"},

        # ---- febrero 2024 ---------------------------------------------------------
        {"operacion": "COMPRA", "producto": "PROD-MON-001", "cantidad": 10, "precio": 300.00,
         "fecha": "08/02/2024", "contraparte": "Pacific Imports"},
        {"operacion": "VENTA", "producto": "PROD-MON-001", "cantidad": 8, "precio": 450.00,
         "fecha": "22/02/2024", "contraparte": "Cliente D"},

        # ---- enero 2024 ----------------------------------------------------------
        {"operacion": "COMPRA", "producto": "PROD-LAP-001", "cantidad": 4, "precio": 1500.00,
         "fecha": "10/01/2024", "contraparte": "Importaciones SAC"},
        {"operacion": "VENTA", "producto": "PROD-LAP-001", "cantidad": 3, "precio": 1900.00,
         "fecha": "25/01/2024", "contraparte": "Cliente E"},
    ]

    for f in filas:
        f["cantidad"] = int(round(f["cantidad"]))

    df = pd.DataFrame(filas)
    df.to_excel(filepath, index=False)
    return filepath


if __name__ == "__main__":
    generar_excel_ejemplo("sample_data/operaciones_ejemplo.xlsx")
    validas, advertencias = excel_a_sentencias("sample_data/operaciones_ejemplo.xlsx")
    print(f"Filas válidas: {len(validas)}, advertencias: {len(advertencias)}")
    for v in validas[:5]:
        print(v)
