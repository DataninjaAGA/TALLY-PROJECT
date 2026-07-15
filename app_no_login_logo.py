from __future__ import annotations

import hmac
from pathlib import Path

import pandas as pd
import streamlit as st

from src.excel_reader import DailyCheckError, get_candidate_sheet_names, load_daily_check, parse_daily_check, summarize_documents
from src.pdf_generator import build_many_pdfs
from src.zip_generator import build_zip

APP_TITLE = "Volaris Tally Project"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")


def _get_credentials() -> dict[str, str]:
    """Return username/password pairs configured in Streamlit Secrets.

    Expected Streamlit Secrets format:

    [credentials]
    usuario1 = "contraseña1"
    usuario2 = "contraseña2"
    """
    try:
        credentials = st.secrets.get("credentials", {})
    except Exception:
        return {}

    return {str(user): str(password) for user, password in dict(credentials).items()}


def _is_valid_login(username: str, password: str) -> bool:
    """Validate credentials safely, supporting accented characters.

    hmac.compare_digest can raise TypeError when comparing non-ASCII
    Python strings, for example passwords containing ñ or accented vowels.
    Encoding both values to UTF-8 bytes keeps the comparison constant-time
    and allows passwords like "contraseña1".
    """
    credentials = _get_credentials()
    expected_password = credentials.get(username)
    if expected_password is None:
        return False

    expected_bytes = str(expected_password).encode("utf-8")
    supplied_bytes = str(password).encode("utf-8")
    return hmac.compare_digest(expected_bytes, supplied_bytes)


def _show_login() -> None:
    """Render a simple login screen without logo display."""
    st.markdown(
        """
        <style>
            .login-spacer {
                height: 2.5rem;
            }
            .login-title {
                text-align: center;
                font-size: 2.2rem;
                font-weight: 750;
                margin-top: 0.30rem;
                margin-bottom: 0.25rem;
            }
            .login-subtitle {
                text-align: center;
                color: rgba(49, 51, 63, 0.72);
                margin-bottom: 1.25rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    credentials = _get_credentials()
    if not credentials:
        st.error("No hay usuarios configurados en Streamlit Secrets.")
        st.info(
            "Configura tus usuarios en Streamlit: Manage app → Settings → Secrets. "
            "Ejemplo:\n\n[credentials]\nusuario1 = \"contraseña1\"\nusuario2 = \"contraseña2\""
        )
        st.stop()

    left, center, right = st.columns([1, 1.15, 1])
    with center:
        st.markdown('<div class="login-spacer"></div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">Volaris Tally Project</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="login-subtitle">Ingresa tus credenciales para generar tallys en PDF.</div>',
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", type="primary", use_container_width=True)

    if submitted:
        username = username.strip()
        if _is_valid_login(username, password):
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.rerun()
        else:
            with center:
                st.error("Usuario o contraseña incorrectos.")

def _require_login() -> None:
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        _show_login()
        st.stop()


_require_login()

with st.sidebar:
    st.success(f"Sesión activa: {st.session_state.get('username', '')}")
    if st.button("Cerrar sesión"):
        st.session_state["authenticated"] = False
        st.session_state.pop("username", None)
        st.rerun()

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
