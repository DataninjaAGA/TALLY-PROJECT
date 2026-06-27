# Tally Generator

Aplicativo en Python + Streamlit para cargar un archivo **Daily Check** en Excel, extraer las tareas por aeronave y generar automáticamente un PDF de **Tally Sheet** por registro. Al final entrega todos los PDFs dentro de un archivo ZIP.

## 1. Estructura del repositorio

```text
tally-generator/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml
├── assets/
│   └── logo.png              # opcional
├── src/
│   ├── __init__.py
│   ├── models.py
│   ├── utils.py
│   ├── excel_reader.py
│   ├── pdf_generator.py
│   └── zip_generator.py
└── tests/
    └── test_parser.py
```

## 2. Requisitos

- Python 3.10 o superior.
- Git instalado, si se subirá a GitHub.
- Un archivo Daily Check `.xlsx` o `.xlsm` con una hoja operativa tipo `GDL`.

## 3. Instalación local paso a paso

### Paso 1: Crear carpeta del proyecto

```bash
mkdir tally-generator
cd tally-generator
```

Copia dentro de esa carpeta todos los archivos de este repositorio.

### Paso 2: Crear entorno virtual

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En Mac/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Paso 3: Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 4: Ejecutar la app

```bash
streamlit run app.py
```

Streamlit abrirá la app en el navegador. Normalmente la URL local será parecida a:

```text
http://localhost:8501
```

## 4. Uso del aplicativo

1. Abre la app.
2. Carga el archivo Daily Check.
3. Selecciona la hoja a procesar, por ejemplo `GDL`.
4. Revisa la vista previa de aeronaves y tareas detectadas.
5. Presiona **Generar PDFs y ZIP**.
6. Descarga `tallys_generados.zip`.
7. Descomprime el ZIP para obtener archivos como:

```text
N506VL T.pdf
N512VL T.pdf
XA-VRI T.pdf
...
```

## 5. Lógica implementada

La extracción usa estas reglas iniciales basadas en el Daily Check de referencia:

- Busca una hoja con encabezados `A/C`, `WO`, `TASK CARD`, `DESCRIPTION` y `STATUS`.
- Cada nuevo registro de aeronave inicia cuando la columna `A/C` contiene valores como `N506VL` o `XA-VRI`.
- Las filas siguientes pertenecen a esa aeronave hasta encontrar otro registro.
- El `WO` se hereda dentro del mismo bloque cuando viene vacío.
- Las tareas con `DONE = CANCELLED` o `DONE = CLOSED` se omiten por defecto.
- Las filas tipo `TRANSIT CHECK / RON` sin `TASK CARD` ni `DESCRIPTION` no generan tally.
- El campo `STATUS` del Daily Check se coloca en `REMARK` del PDF.
- `M/H` queda vacío por defecto para coincidir con los PDFs de referencia. Puede activarse desde la barra lateral.

## 6. Logo

El generador usa un texto simple `volaris` como marcador. Si deseas usar un logo real, coloca una imagen en:

```text
assets/logo.png
```

La app la detectará automáticamente.

## 7. Subir a GitHub

Desde la carpeta del proyecto:

```bash
git init
git add .
git commit -m "Initial tally generator app"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/tally-generator.git
git push -u origin main
```

## 8. Publicar en Streamlit Community Cloud

1. Sube el repositorio a GitHub.
2. Entra a Streamlit Community Cloud.
3. Selecciona **Deploy an app**.
4. Conecta tu repositorio.
5. Define `app.py` como archivo principal.
6. Despliega.

El archivo `requirements.txt` debe estar en la raíz del repositorio para que Streamlit instale las dependencias.

## 9. Archivos principales

### `app.py`

Interfaz Streamlit: carga archivo, muestra vista previa, genera PDFs y habilita descarga ZIP.

### `src/excel_reader.py`

Contiene la lógica de lectura del Daily Check y agrupación por aeronave.

### `src/pdf_generator.py`

Dibuja el Tally Sheet directamente en PDF usando ReportLab.

### `src/zip_generator.py`

Empaqueta los PDFs en un ZIP descargable.

## 10. Ajustes frecuentes

### Cambiar reglas de exclusión

Edita esta función en `src/utils.py`:

```python
def should_exclude_task(done_value, include_cancelled=False):
    ...
```

### Cambiar columnas del Daily Check

Edita estas constantes en `src/excel_reader.py`:

```python
COL_AIRCRAFT = 1
COL_FLIGHT = 2
COL_ARR = 3
COL_DEPT = 4
COL_WO = 5
COL_TASK_CARD = 6
COL_DESCRIPTION = 7
COL_STATUS = 8
COL_DONE = 9
COL_PENDING = 10
COL_COMMENTS = 11
COL_MAN_HOURS = 12
```

### Cambiar formato del PDF

Edita coordenadas, anchos de columnas y textos fijos en `src/pdf_generator.py`.
