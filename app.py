# app.py
from __future__ import annotations
import json
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# ⬇️ Soft login (asegúrate de tener soft_login_full.py en el repo)
from soft_login_full import soft_login_barrier, soft_login_header

# =========================
# Configuración de página
# =========================
st.set_page_config(
    page_title="Momentum | Rutinas",
    page_icon="🏋️",
    layout="wide",
)

# =========================
# Firebase (1 sola vez)
# =========================
def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(st.secrets["FIREBASE_CREDENTIALS"]))
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# =========================
# Utilidades
# =========================
def normalizar_email(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "")

@st.cache_data(ttl=60)
def get_user_role(email: str) -> str | None:
    """
    Busca el rol del usuario en tu colección 'usuarios'.
    Ajusta nombres de colección/campos si tus docs difieren.
    """
    if not email:
        return None

    # 1) Búsqueda por campo 'correo' (exacto)
    q = db.collection("usuarios").where("correo", "==", email).limit(1).get()
    if q:
        return q[0].to_dict().get("rol")

    # 2) (Opcional) si guardas correos normalizados en otro campo
    norm = email.replace("@", "_").replace(".", "_")
    q2 = db.collection("usuarios").where("correo_normalizado", "==", norm).limit(1).get()
    if q2:
        return q2[0].to_dict().get("rol")

    return None

def cargar_pagina(nombre: str):
    """
    Importa y ejecuta la vista correspondiente.
    No importes módulos de páginas al tope para evitar
    efectos colaterales durante el refresco.
    """
    try:
        if nombre == "Ver Rutinas":
            from vista_rutinas import ver_rutinas
            ver_rutinas()
        elif nombre == "Crear Rutinas":
            from crear_rutinas import crear_rutinas
            crear_rutinas()
        elif nombre == "Editar Rutinas":
            from editar_rutinas import editar_rutinas
            editar_rutinas()
        elif nombre == "Ingresar Cliente":
            from ingresar_cliente import ingresar_cliente
            ingresar_cliente()
        elif nombre == "Disponibilidad Coach":
            from agenda_disponibilidad import app as disponibilidad_app  # ejemplo
            disponibilidad_app()
        else:
            st.info("Selecciona una sección en el menú lateral.")
    except ModuleNotFoundError as e:
        st.error(f"No se encontró el módulo de la página: {e.name}.")
    except Exception as e:
        st.exception(e)

# =========================
# App
# =========================
def main():
    # 1) Barrera de soft login SOLO aquí (no en los módulos importados)
    email = soft_login_barrier(required_roles=None)  # no bloquea por rol, solo valida sesión

    # 2) Header con correo + botón Cerrar sesión
    soft_login_header()

    # 3) Rol del usuario
    email_norm = normalizar_email(email)
    rol = get_user_role(email_norm)
    st.session_state["email"] = email_norm
    st.session_state["rol"] = rol

    # 4) Sidebar
    with st.sidebar:
        st.markdown("### 👤 Sesión")
        st.write(f"**Correo:** {email_norm}")
        st.write(f"**Rol:** {rol or 'N/D'}")

        st.markdown("---")
        st.markdown("### Navegación")

        # Menú según rol (ajusta a tus necesidades)
        if rol in ("admin", "entrenador"):
            opciones = [
                "Ver Rutinas",
                "Crear Rutinas",
                "Editar Rutinas",
                "Ingresar Cliente",
                "Disponibilidad Coach",
            ]
        else:
            # Deportista o rol no definido: solo ver
            opciones = ["Ver Rutinas"]

        pagina = st.selectbox("Secciones", opciones, key="nav_select")

    # 5) Contenido principal
    cargar_pagina(pagina)

if __name__ == "__main__":
    main()
