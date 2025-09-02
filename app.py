# app.py
from __future__ import annotations
import json
import streamlit as st

# ===== Config de página =====
st.set_page_config(
    page_title="Momentum | Rutinas",
    page_icon="🏋️",
    layout="wide",
)

# ===== Firebase una sola vez (desde secrets) =====
def _init_firestore():
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(json.loads(st.secrets["FIREBASE_CREDENTIALS"]))
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception:
        st.warning("No fue posible inicializar Firebase. Revisa tus secrets.")
        return None

db = _init_firestore()

# ===== Soft Login =====
# ✅ Importa SOLO lo que existe en soft_login_full.py
from soft_login_full import soft_login_barrier, soft_logout

# ===== Utilidades mínimas =====
def _normalizar_email(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "")

@st.cache_data(ttl=60)
def _get_user_role(email: str) -> str | None:
    """Lee el rol desde la colección 'usuarios' (ajusta si tu esquema difiere)."""
    if not email or db is None:
        return None
    try:
        q = db.collection("usuarios").where("correo", "==", email).limit(1).get()
        if q:
            return (q[0].to_dict() or {}).get("rol")
    except Exception:
        pass
    return None

# ===== App principal =====
def main():
    # --- BARRERA DE LOGIN ---
    ok = soft_login_barrier(required_roles=None, titulo="Bienvenido a Momentum")
    if not ok:
        # La función ya muestra la UI de login y hace rerun cuando corresponde
        return

    # Datos de sesión listos por la barrera
    correo = _normalizar_email(st.session_state.get("correo"))
    rol = st.session_state.get("rol") or _get_user_role(correo)
    st.session_state["rol"] = rol

    # --- Sidebar/nav ---
    with st.sidebar:
        st.markdown("### 👤 Sesión")
        st.write(f"**Correo:** {correo or 'N/D'}")
        st.write(f"**Rol:** {rol or 'N/D'}")
        if st.button("Cerrar sesión"):
            soft_logout()

        st.markdown("---")
        st.markdown("### Navegación")

        # Ajusta las opciones a tu app real
        if (rol or "").lower() in ("admin", "entrenador"):
            opciones = [
                "Ver Rutinas",
                "Crear Rutinas",
                "Editar Rutinas",
                "Ingresar Cliente",
                "Disponibilidad Coach",
            ]
        else:
            opciones = ["Ver Rutinas"]

        pagina = st.selectbox("Secciones", opciones, key="nav_select")

    # --- Ruteo con IMPORTS PEREZOSOS (luego del login) ---
    try:
        if pagina == "Ver Rutinas":
            from vista_rutinas import ver_rutinas
            ver_rutinas()
        elif pagina == "Crear Rutinas":
            from crear_rutinas import crear_rutinas
            crear_rutinas()
        elif pagina == "Editar Rutinas":
            from editar_rutinas import editar_rutinas
            editar_rutinas()
        elif pagina == "Ingresar Cliente":
            from ingresar_cliente import ingresar_cliente
            ingresar_cliente()
        elif pagina == "Disponibilidad Coach":
            # Ajusta si tu módulo expone otra función
            from agenda_disponibilidad import app as disponibilidad_app
            disponibilidad_app()
        else:
            st.info("Selecciona una sección en el menú lateral.")
    except ModuleNotFoundError as e:
        st.error(f"No se encontró el módulo de la página: {e.name}.")
    except Exception as e:
        # Muestra el traceback completo para depurar en Cloud
        st.exception(e)

if __name__ == "__main__":
    main()
