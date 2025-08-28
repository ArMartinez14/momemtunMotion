# soft_login_full.py
from __future__ import annotations
import json
import streamlit as st

# API pública
__all__ = ["soft_login_fullpage", "require_login", "require_role"]

# ----- helpers -----
def _init_db():
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            cred_dict = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception:
        return None

def _find_user_by_email(db, correo: str):
    if db is None:
        return None
    try:
        q = db.collection("usuarios").where("correo", "==", correo.strip().lower()).limit(1).stream()
        doc = next(q, None)
        if not doc:
            return None
        d = doc.to_dict() or {}
        return {
            "correo": d.get("correo", correo).strip().lower(),
            "nombre": d.get("nombre", "") or d.get("displayName", ""),
            "rol": (d.get("rol", "") or d.get("tipo", "") or "deportista").strip().lower(),
        }
    except Exception:
        return None

def require_login():
    if not st.session_state.get("correo"):
        st.stop()

def require_role(roles: tuple[str, ...] | list[str]):
    rol = (st.session_state.get("rol") or "").lower()
    if rol not in [r.lower() for r in roles]:
        st.error("No tienes permisos para ver esta sección.")
        st.stop()

# ----- UI principal -----
def soft_login_fullpage(app_name: str = "Momentum"):
    # init session keys
    st.session_state.setdefault("correo", "")
    st.session_state.setdefault("rol", "")
    st.session_state.setdefault("nombre", "")

    if st.session_state.correo:
        # Ya logueado: no mostramos el formulario
        return

    # estilos simples para centrar y dar aire
    st.markdown(
        """
        <style>
        .login-wrapper {max-width: 1100px; margin: 40px auto 0;}
        .login-desc {color: #bbb; font-size: 18px; margin-top: -6px; margin-bottom: 24px;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown("<div class='login-wrapper'>", unsafe_allow_html=True)
        st.title(f"Bienvenido a {app_name}")
        st.markdown("<div class='login-desc'>Ingresa tu correo (no se requiere contraseña).</div>", unsafe_allow_html=True)

        correo = st.text_input("Correo electrónico", key="login_correo", placeholder="nombre@dominio.com")

        if st.button("Continuar"):
            correo = (correo or "").strip().lower()
            if not correo:
                st.warning("Escribe tu correo para continuar.")
                st.stop()

            db = _init_db()
            user = _find_user_by_email(db, correo)

            if not user:
                st.error("Correo no encontrado. Verifica o contacta al administrador.")
                st.stop()

            # set sesión
            st.session_state.correo = user["correo"]
            st.session_state.rol = user["rol"] if user["rol"] in ("entrenador", "deportista", "admin", "administrador") else "deportista"
            st.session_state.nombre = user.get("nombre", "")
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
