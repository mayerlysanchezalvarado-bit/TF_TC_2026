# GASO AAA — DSL académico de Compras y Ventas

Aplicación web en **Flask** que implementa, de extremo a extremo, un
Domain Specific Language (DSL) propio para registrar operaciones
comerciales de compra/venta, junto con el pipeline completo de un
compilador simplificado:

```
Excel → DSL → Lexer → Parser → Árbol Sintáctico → JSON → Dashboard
```

## Instalación

```bash
pip install -r requirements.txt
python app.py
```

Luego abre **http://localhost:5000** en el navegador.

## Estructura del proyecto

```
gaso_dsl/
├── app.py             # Rutas Flask (vistas + API JSON para el front-end)
├── lexer.py            # Analizador léxico: texto -> lista de Tokens
├── afd.py               # AFND y AFD (con tabla de transiciones) por cada token
├── parser.py            # Parser descendente recursivo -> Árbol sintáctico
├── arbol.py              # Estructura de nodo de árbol (to_dict / to_ascii)
├── interpreter.py        # Recorre el árbol y traduce a JSON (traducción dirigida por sintaxis)
├── json_gen.py            # Agrega operaciones -> KPIs, series mensuales, rankings
├── excel_to_dsl.py         # Convierte filas de Excel en sentencias DSL válidas
├── templates/
│   ├── base.html            # Layout compartido (nav, flash messages)
│   ├── index.html            # Paso 1: cargar Excel o escribir DSL a mano
│   ├── compiler.html          # Paso 2: lexemas, tokens, AFND/AFD, árbol, JSON
│   └── dashboard.html          # Paso 3: dashboard estadístico final
├── static/style.css            # Identidad visual "documento técnico de compilador"
└── sample_data/
    └── operaciones_ejemplo.xlsx  (se genera automáticamente al iniciar)
```

## El DSL

Cada sentencia tiene el formato:

```
COMPRA <PRODUCTO> <CANTIDAD> <PRECIO>
VENTA  <PRODUCTO> <CANTIDAD> <PRECIO>
```

Ejemplo:

```
COMPRA PROD-AUD-001 50 25.00
VENTA  PROD-AUD-001 40 45.00
```

### Tokens

| Token              | Expresión regular           | Ejemplo        |
|--------------------|------------------------------|-----------------|
| PALABRA_RESERVADA | `^(COMPRA\|VENTA)$`          | COMPRA          |
| PRODUCTO            | `^PROD-[A-Z]{3}-\d{3}$`       | PROD-AUD-001    |
| NUM_INT              | `^\d+$`                       | 50              |
| NUM_DECIMAL           | `^\d+\.\d{2}$`                 | 25.00           |
| FECHA (opcional)       | `^\d{2}/\d{2}/\d{4}$`           | 15/05/2024      |

### Gramática libre de contexto

```
S          → Operacion
Operacion  → COMPRA Producto Cantidad Precio
Operacion  → VENTA  Producto Cantidad Precio
Producto   → PRODUCTO
Cantidad   → NUM_INT
Precio     → NUM_DECIMAL
```

## Flujo de uso

1. **Cargar datos** (`/`): sube un Excel con columnas `operacion, producto,
   cantidad, precio, fecha, contraparte` (alias flexibles), o escribe
   sentencias DSL directamente en el textarea.
2. **Ver el compilador** (`/compilador`): inspecciona los lexemas
   encontrados, sus tokens, los autómatas AFND/AFD que los reconocen
   (con un panel interactivo para probar cualquier cadena en vivo),
   y despliega cada sentencia para ver su árbol sintáctico y el JSON
   traducido. Las sentencias con error léxico/sintáctico/semántico se
   marcan claramente.
3. **Ver el dashboard** (`/dashboard`): KPIs, gráfico de compras/ventas
   mensuales, distribución de ingresos por producto, resumen de
   ingresos, compras/ventas recientes y productos más rentables —
   todo calculado a partir del JSON generado en el paso anterior.

## Notas de diseño

- El estado (programa DSL compilado y operaciones válidas) se guarda
  en memoria de proceso, sin base de datos, para mantener el alcance
  académico y simple. Usa `/reiniciar` para limpiar la sesión.
- Las filas de Excel con datos inválidos (producto mal formado,
  cantidad/precio faltante, tipo de operación desconocido) se
  descartan con un motivo explícito, sin detener el procesamiento
  de las demás filas.
- Los autómatas se definen formalmente en `afd.py` (estados, alfabeto,
  transiciones, estado inicial/final) y se exponen vía
  `/api/automata/<token>` para que el navegador los dibuje en SVG,
  y vía `/api/reconocer/<token>/<cadena>` para animar el reconocimiento
  carácter por carácter de cualquier cadena que el usuario escriba.
