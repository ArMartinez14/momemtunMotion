# app.py
import streamlit as st
st.set_page_config(page_title="Momentum", layout="wide")

# === Login de pantalla completa ===
from soft_login_bar import soft_login_fullpage, require_login, require_role

# Secciones
from vista_rutinas import ver_rutinas
from crear_planificaciones import crear_rutinas
from editar_rutinas import editar_rutinas
from crear_descarga import descarga_rutina
from borrar_rutinas import borrar_rutinas
from ingresar_cliente_view import ingresar_cliente_o_video_o_ejercicio
from seccion_ejercicios import base_ejercicios

# (opcional) init firebase si usas DB global
import json
import firebase_admin
from firebase_admin import credentials, initialize_app
if not firebase_admin._apps:
    try:
        cred_dict = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(cred_dict)
        initialize_app(cred)
    except Exception:
        pass

# ===========================
# 1) Login (pantalla completa)
# ===========================
soft_login_fullpage(app_name="Momentum")  # muestra título, input y botón "Continuar"
require_login()                           # exige sesión

rol = (st.session_state.get("rol") or "").lower()

# ===========================
# 2) Vista según rol
# ===========================
if rol == "deportista":
    # Sin menú: acceso exclusivo a Ver Rutinas
    st.title("🏋️ Tu Rutina")
    ver_rutinas()
    st.stop()

elif rol in ("entrenador", "admin", "administrador"):
    # Menú completo
    st.sidebar.title("Menú principal")
    opciones_menu = (
        "Inicio",
        "Ver Rutinas",
        "Crear Rutinas",
        "Ingresar Deportista o Video",
        "Borrar Rutinas",
        "Editar Rutinas",
        "Ejercicios",
        "Descarga Rutina",
        "Reportes",
    )
    opcion = st.sidebar.radio("Selecciona una opción:", opciones_menu)

    # Seguridad explícita (por si cambias permisos en el futuro)
    require_role(("entrenador", "admin", "administrador"))

    if opcion == "Inicio":
        st.markdown(
            """
            <div style='text-align: center; margin-top: 100px;'>
                <img src='https://i.ibb.co/YL1HbLj/motion-logo.png' width='100'>
                <h1>Bienvenido a Momentum</h1>
                <p style='font-size:18px;'>Selecciona una opción del menú para comenzar</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif opcion == "Ver Rutinas":
        ver_rutinas()
    elif opcion == "Crear Rutinas":
        # Esta pantalla además tiene su propio require_role interno
        crear_rutinas()
    elif opcion == "Ingresar Deportista o Video":
        ingresar_cliente_o_video_o_ejercicio()
    elif opcion == "Borrar Rutinas":
        borrar_rutinas()
    elif opcion == "Editar Rutinas":
        editar_rutinas()
    elif opcion == "Ejercicios":
        base_ejercicios()
    elif opcion == "Descarga Rutina":
        descarga_rutina()
    elif opcion == "Reportes":
        from reportes import ver_reportes  # import perezoso
        ver_reportes()

else:
    # Fallback seguro
    st.info("Rol no reconocido. Mostrando vista de deportista.")
    ver_rutinas()
