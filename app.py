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
from soft_login_full import soft_login_barrier, soft_logout

# ===== Utilidades mínimas =====
def _normalizar_email(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "")

def _read_admin_emails_from_secrets() -> set[str]:
    """
    Permite whitelists de admin opcionalmente por secrets:
    - Como lista: ADMIN_EMAILS = ["admin@dominio.com", "coach@dominio.com"]
    - O como string separada por comas: ADMIN_EMAILS = "a@b.com,c@d.com"
    """
    raw = st.secrets.get("ADMIN_EMAILS", [])
    if isinstance(raw, (list, tuple, set)):
        return {str(x).strip().lower() for x in raw if str(x).strip()}
    try:
        return {e.strip().lower() for e in str(raw).split(",") if e.strip()}
    except Exception:
        return set()

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

def _is_staff(rol: str | None, correo: str | None) -> bool:
    """
    Staff si:
    - rol es admin/entrenador
    - o el correo está en ADMIN_EMAILS (secrets)
    - o (por compatibilidad con tu flujo previo) DEFAULT_FULL_MENU está en True (por defecto True)
    """
    admin_emails = _read_admin_emails_from_secrets()
    default_full_menu = bool(st.secrets.get("DEFAULT_FULL_MENU", True))
    r = (rol or "").strip().lower()
    c = (correo or "").strip().lower()

    if r in ("admin", "entrenador"):
        return True
    if c in admin_emails:
        return True
    # Compatibilidad: mostrar menú completo por defecto si no hay rol claro
    if default_full_menu:
        return True
    return False

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

        # 👇 Lógica ajustada: por defecto muestra menú completo (como tenías antes).
        if _is_staff(rol, correo):
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
            from agenda_disponibilidad import app as disponibilidad_app
            disponibilidad_app()
        else:
            st.info("Selecciona una sección en el menú lateral.")
    except ModuleNotFoundError as e:
        st.error(f"No se encontró el módulo de la página: {e.name}.")
    except Exception as e:
        st.exception(e)

if __name__ == "__main__":
    main()
