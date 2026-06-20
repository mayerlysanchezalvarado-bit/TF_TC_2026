# -*- coding: utf-8 -*-
"""
json_gen.py
-----------
Toma la lista de operaciones ya interpretadas (cada una un dict
{"operacion","producto","cantidad","precio","total", ...}) y construye
el dataset agregado que alimenta el dashboard estadístico:

    - KPIs: compras totales, ventas totales, utilidad bruta, n° operaciones,
      productos registrados, margen.
    - Series mensuales: compras y ventas por mes (para los gráficos).
    - Resumen de ingresos y costos (tabla tipo estado de resultados).
    - Tablas de compras/ventas recientes.
    - Productos más rentables (ranking por utilidad generada).

Este módulo es agnóstico de Flask: solo recibe/devuelve diccionarios
y listas planas (json-serializables) para que app.py los pase directo
a render_template.
"""

from collections import defaultdict
from datetime import datetime
from typing import List, Dict


NOMBRES_PRODUCTO = {
    "PROD-AUD-001": "Audífonos",
    "PROD-MOU-001": "Mouse Gamer",
    "PROD-TEC-001": "Teclado USB",
    "PROD-MON-001": "Monitor",
    "PROD-LAP-001": "Laptop",
}

MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
            "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def nombre_producto(codigo: str) -> str:
    return NOMBRES_PRODUCTO.get(codigo, codigo)


def _parsear_fecha(fecha_str):
    if not fecha_str:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(fecha_str, fmt)
        except ValueError:
            continue
    return None


def construir_dashboard(operaciones: List[Dict]) -> Dict:
    """
    operaciones: lista de dicts, cada uno con al menos:
        {
          "operacion": "COMPRA"|"VENTA",
          "producto": "PROD-AUD-001",
          "cantidad": int,
          "precio": float,
          "total": float,
          "fecha": "15/05/2024" | None,
          "contraparte": str | None,
          "sentencia": str,
        }

    Devuelve el dict completo que consume dashboard.html.
    """
    compras = [op for op in operaciones if op["operacion"] == "COMPRA"]
    ventas = [op for op in operaciones if op["operacion"] == "VENTA"]

    compras_totales = round(sum(op["total"] for op in compras), 2)
    ventas_totales = round(sum(op["total"] for op in ventas), 2)
    utilidad_bruta = round(ventas_totales - compras_totales, 2)
    margen_pct = round((utilidad_bruta / ventas_totales * 100), 1) if ventas_totales else 0.0

    productos_registrados = sorted({op["producto"] for op in operaciones})

    # ---- Series mensuales --------------------------------------------------
    compras_por_mes = defaultdict(float)
    ventas_por_mes = defaultdict(float)
    orden_meses = []

    for op in operaciones:
        f = _parsear_fecha(op.get("fecha"))
        if not f:
            continue
        clave = (f.year, f.month)
        etiqueta = f"{MESES_ES[f.month - 1]}"
        if clave not in orden_meses:
            orden_meses.append(clave)
        if op["operacion"] == "COMPRA":
            compras_por_mes[clave] += op["total"]
        else:
            ventas_por_mes[clave] += op["total"]

    orden_meses = sorted(set(orden_meses))
    etiquetas_meses = [f"{MESES_ES[m - 1]}" for (y, m) in orden_meses]
    serie_compras = [round(compras_por_mes[c], 2) for c in orden_meses]
    serie_ventas = [round(ventas_por_mes[c], 2) for c in orden_meses]

    max_mensual = max(serie_compras + serie_ventas) if (serie_compras or serie_ventas) else 1

    # ---- Resumen de ingresos / costos (tipo estado de resultados) ---------
    resumen_ingresos = {
        "ventas_totales": ventas_totales,
        "costo_compras": compras_totales,
        "utilidad_bruta": utilidad_bruta,
        "margen_pct": margen_pct,
    }

    # ---- Recientes (orden por fila de inserción, últimas 5) ---------------
    compras_recientes = compras[-6:][::-1]
    ventas_recientes = ventas[-6:][::-1]

    # ---- Productos más rentables -------------------------------------------
    ingresos_por_producto = defaultdict(float)
    costos_por_producto = defaultdict(float)
    unidades_vendidas = defaultdict(int)

    for op in ventas:
        ingresos_por_producto[op["producto"]] += op["total"]
        unidades_vendidas[op["producto"]] += op["cantidad"]
    for op in compras:
        costos_por_producto[op["producto"]] += op["total"]

    ranking = []
    for prod in productos_registrados:
        utilidad_prod = round(ingresos_por_producto[prod] - costos_por_producto[prod], 2)
        ranking.append({
            "producto": prod,
            "nombre": nombre_producto(prod),
            "utilidad": utilidad_prod,
            "unidades_vendidas": unidades_vendidas[prod],
        })
    ranking.sort(key=lambda x: x["utilidad"], reverse=True)
    productos_top = ranking[:5]

    # ---- Donut: distribución de ingresos por tipo de producto -------------
    distribucion_ventas = []
    if ventas_totales > 0:
        for prod in productos_registrados:
            monto = round(ingresos_por_producto[prod], 2)
            if monto <= 0:
                continue
            distribucion_ventas.append({
                "producto": prod,
                "nombre": nombre_producto(prod),
                "monto": monto,
                "pct": round(monto / ventas_totales * 100, 1),
            })
        distribucion_ventas.sort(key=lambda x: x["monto"], reverse=True)

    clientes_activos = len({op["contraparte"] for op in ventas if op.get("contraparte")})
    proveedores_activos = len({op["contraparte"] for op in compras if op.get("contraparte")})

    return {
        "kpis": {
            "compras_totales": compras_totales,
            "ventas_totales": ventas_totales,
            "utilidad_bruta": utilidad_bruta,
            "margen_pct": margen_pct,
            "num_operaciones": len(operaciones),
            "productos_registrados": len(productos_registrados),
            "clientes_activos": clientes_activos,
            "proveedores_activos": proveedores_activos,
        },
        "serie_mensual": {
            "etiquetas": etiquetas_meses,
            "compras": serie_compras,
            "ventas": serie_ventas,
            "max": max_mensual,
        },
        "resumen_ingresos": resumen_ingresos,
        "compras_recientes": compras_recientes,
        "ventas_recientes": ventas_recientes,
        "productos_top": productos_top,
        "distribucion_ventas": distribucion_ventas,
        "lista_productos": productos_registrados,
    }
