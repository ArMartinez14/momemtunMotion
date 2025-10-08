# login_gate.py
import streamlit as st
import extra_streamlit_components as stx
import streamlit.components.v1 as components
from firebase_login import firebase_login_ui
from auth_guard import ensure_user_session, is_token_expired

def get_cookie_manager():
    return stx.CookieManager()

def login_barrier(cookie_name: str = "fb_idtoken") -> bool:
    st.subheader("Autenticación")
    cookie_manager = get_cookie_manager()

    script = f"""
    <script>
    (function() {{
      const cookieName = "{cookie_name}";
      const maxAgeDays = 7;
      function setCookieFromToken(token) {{
        if (!token) {{
          return;
        }}
        const expires = new Date(Date.now() + maxAgeDays * 24 * 60 * 60 * 1000).toUTCString();
        const isHttps = window.location.protocol === "https:";
        const sameSite = isHttps ? "SameSite=None" : "SameSite=Lax";
        const secure = isHttps ? ";Secure" : "";
        document.cookie = `${{cookieName}}=${{token}};expires=${{expires}};path=/;${{sameSite}}${{secure}}`;
      }}
      function propagateFromStorage() {{
        try {{
          const stored = window.localStorage.getItem("fb_idtoken");
          if (stored) {{
            setCookieFromToken(stored);
          }}
        }} catch (err) {{
          console.warn("No se pudo leer localStorage", err);
        }}
      }}
      window.addEventListener("message", (event) => {{
        if (!event.data || event.data.type !== "fb_idtoken" || !event.data.token) {{
          return;
        }}
        try {{
          window.localStorage.setItem("fb_idtoken", event.data.token);
        }} catch (err) {{
          console.warn("No se pudo persistir token en localStorage", err);
        }}
        setCookieFromToken(event.data.token);
      }});
      propagateFromStorage();
      document.addEventListener("visibilitychange", () => {{
        if (!document.hidden) {{
          propagateFromStorage();
        }}
      }});
      setInterval(propagateFromStorage, 1500);
    }})();
    </script>
    """
    components.html(script, height=0)

    if st.session_state.pop("auth_clear_cookie", False):
        try:
            cookie_manager.delete(cookie_name)
        except Exception:
            pass

    auth_error = st.session_state.pop("auth_error", None)
    if auth_error:
        st.error(auth_error)

    # Lee token de cookie
    id_token = cookie_manager.get(cookie_name)

    # Si no hay sesión válida, muestra UI de login
    if not id_token or ("user" not in st.session_state) or is_token_expired():
        st.info("Inicia sesión para continuar.")
        firebase_login_ui(cookie_name=cookie_name, height=560)  # embebe FirebaseUI

        # Reintenta leer cookie por si el usuario acaba de loguearse
        id_token = cookie_manager.get(cookie_name)
        if id_token and ensure_user_session(id_token):
            st.success("Sesión iniciada ✅")
            st.experimental_rerun()
        else:
            st.stop()  # corta la ejecución hasta que haya sesión

    # Verifica/actualiza datos de sesión si el token cambió
    if id_token and ensure_user_session(id_token):
        st.success(f"Conectado: {st.session_state['correo']}")
        return True

    st.stop()
