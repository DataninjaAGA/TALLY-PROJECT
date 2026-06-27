from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from src.excel_reader import DailyCheckError, get_candidate_sheet_names, load_daily_check, parse_daily_check, summarize_documents
from src.pdf_generator import build_many_pdfs
from src.zip_generator import build_zip

APP_TITLE = "Tally Generator"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")

st.title("📄 Tally Generator")
st.caption("Carga el Daily Check, valida las aeronaves detectadas y descarga todos los tallys en PDF dentro de un ZIP.")

with st.sidebar:
    st.header("Configuración")
    include_cancelled = st.toggle(
        "Incluir tareas canceladas/cerradas",
        value=False,
        help="Por defecto se omiten porque en los tallys de referencia no aparecen las tareas con DONE=CANCELLED/CLOSED.",
    )
    include_man_hours = st.toggle(
        "Completar M/H",
        value=False,
        help="Si lo activas, se intenta tomar M/H desde la columna TC M/H o desde la hoja HM.",
    )
    logo_path = "assets/logo.png" if Path("assets/logo.png").exists() else None
    st.divider()
    st.write("Formato actual:")
    st.code("REGISTER / TASK CARD / DESCRIPTION / M/H / WO\nSTATUS / LOGBOOK PG. / REMARK", language="text")

uploaded_file = st.file_uploader("Sube el archivo Daily Check", type=["xlsx", "xlsm"])

if uploaded_file is None:
    st.info("Sube un archivo .xlsx o .xlsm para iniciar.")
    st.stop()

try:
    file_bytes = uploaded_file.getvalue()
    workbook = load_daily_check(file_bytes)
    candidates = get_candidate_sheet_names(workbook)
    if not candidates:
        st.error("No encontré una hoja con encabezados tipo Daily Check.")
        st.stop()

    selected_sheet = st.selectbox("Hoja a procesar", candidates, index=0)
    documents = parse_daily_check(
        workbook,
        sheet_name=selected_sheet,
        include_cancelled=include_cancelled,
        include_man_hours=include_man_hours,
    )

except DailyCheckError as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:
    st.exception(exc)
    st.stop()

if not documents:
    st.warning("La hoja fue leída, pero no se encontraron aeronaves con tareas para generar tallys.")
    st.stop()

summary = summarize_documents(documents)
summary_df = pd.DataFrame(summary)

left, right = st.columns([2, 1])
with left:
    st.subheader("Vista previa de tallys detectados")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
with right:
    st.metric("Tallys a generar", len(documents))
    st.metric("Tareas totales", sum(len(doc.tasks) for doc in documents))
    st.metric("Estación", documents[0].station if documents else "")

with st.expander("Ver detalle de tareas por aeronave"):
    detail_rows = []
    for doc in documents:
        for task in doc.tasks:
            detail_rows.append(
                {
                    "Register": doc.register,
                    "WO": task.work_order,
                    "Task Card": task.task_card,
                    "Description": task.description,
                    "Remark": task.remark,
                    "Source Row": task.source_row,
                }
            )
    st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

if st.button("Generar PDFs y ZIP", type="primary"):
    with st.spinner("Generando tallys..."):
        pdf_files = build_many_pdfs(documents, logo_path=logo_path)
        zip_bytes = build_zip(pdf_files)

    st.success(f"Listo. Se generaron {len(pdf_files)} PDFs.")
    st.download_button(
        label="Descargar ZIP",
        data=zip_bytes,
        file_name="tallys_generados.zip",
        mime="application/zip",
    )
