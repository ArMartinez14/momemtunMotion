# crear_rutinas.py — Mismo estilo que ver_rutinas.py (solo UI/colores) + Restricción de circuitos por sección
import streamlit as st
import json
import unicodedata
from datetime import date, timedelta, datetime
import pandas as pd

import firebase_admin
from firebase_admin import credentials, firestore

from herramientas import aplicar_progresion
from guardar_rutina_view import guardar_rutina
from soft_login_full import soft_login_barrier

# ==========================
#  PALETA / ESTILOS con soporte claro/oscuro
# ==========================
import streamlit as st

# Paleta modo oscuro (la tuya actual, con terracota)
DARK = dict(
    PRIMARY   ="#00C2FF",
    SUCCESS   ="#22C55E",
    WARNING   ="#F59E0B",
    DANGER    ="#E2725B",   # ← rojo terracota
    BG        ="#0B0F14",
    SURFACE   ="#121821",
    TEXT_MAIN ="#FFFFFF",
    TEXT_MUTED="#94A3B8",
    STROKE    ="rgba(255,255,255,.08)",
)

# Paleta modo claro (también con terracota)
LIGHT = dict(
    PRIMARY   ="#0077FF",
    SUCCESS   ="#16A34A",
    WARNING   ="#D97706",
    DANGER    ="#E2725B",   # ← rojo terracota
    BG        ="#FFFFFF",
    SURFACE   ="#F8FAFC",   
    TEXT_MAIN ="#0F172A",   
    TEXT_MUTED="#475569",   
    STROKE    ="rgba(2,6,23,.08)",  
)


# (Opcional) selector manual en la sidebar: Auto / Oscuro / Claro
with st.sidebar:
    theme_mode = st.selectbox(
        "🎨 Tema", ["Auto", "Oscuro", "Claro"],
        key="theme_mode_crear_rutinas",  # 👈 clave única en esta página
        help="‘Auto’ sigue el modo del sistema; ‘Oscuro/Claro’ fuerzan los colores."
    )


def _vars_block(p):
    return f"""
    --primary:{p['PRIMARY']}; --success:{p['SUCCESS']}; --warning:{p['WARNING']}; --danger:{p['DANGER']};
    --bg:{p['BG']}; --surface:{p['SURFACE']}; --muted:{p['TEXT_MUTED']}; --stroke:{p['STROKE']};
    --text-main:{p['TEXT_MAIN']};
    """

# CSS: define ambas paletas + sobrescritura según sistema + override manual
_css = f"""
<style>
/* Defaults (usaremos LIGHT por accesibilidad si no hay media query) */
:root {{ {_vars_block(LIGHT)} }}

/* Modo oscuro automático por preferencia del sistema */
@media (prefers-color-scheme: dark) {{
  :root {{ {_vars_block(DARK)} }}
}}

/* Estilos base que usan variables */
html,body,[data-testid="stAppViewContainer"]{{ background:var(--bg)!important; color:var(--text-main)!important; }}
h1,h2,h3,h4, label, p, span, div{{ color:var(--text-main); }}
.muted {{ color:var(--muted); font-size:12px; }}
.hr-light {{ border-bottom:1px solid var(--stroke); margin:12px 0; }}
.card {{ background:var(--surface); border:1px solid var(--stroke); border-radius:12px; padding:12px 14px; }}
.h-accent {{ position:relative; padding-left:10px; margin:8px 0 6px; font-weight:700; color:var(--text-main); }}
.h-accent:before {{ content:""; position:absolute; left:0; top:2px; bottom:2px; width:4px; border-radius:3px; background:var(--primary); }}

/* Badges */
.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:700; }}
.badge--success {{ background:var(--success); color:#06210c; }}
.badge--pending {{ background:rgba(0,194,255,.15); color:#055160; border:1px solid rgba(0,194,255,.25); }}

/* Botones */
div.stButton > button[kind="primary"], .stDownloadButton button {{
  background: var(--primary) !important; color:#001018 !important; border:none !important;
  font-weight:700 !important; border-radius:10px !important;
}}
div.stButton > button[kind="secondary"] {{
  background: var(--surface) !important; color: var(--text-main) !important; border:1px solid var(--stroke) !important;
  border-radius:10px !important;
}}
div.stButton > button:hover {{ filter:brightness(0.93); }}

/* Inputs / selects */
[data-baseweb="input"] input, .stTextInput input, .stSelectbox div, .stSlider, textarea{{
  color:var(--text-main)!important;
}}
/* Sticky CTA */
.sticky-cta {{ position:sticky; bottom:0; z-index:10; padding-top:8px;
  background:linear-gradient(180deg, rgba(0,0,0,0), rgba(0,0,0,.06)); backdrop-filter: blur(6px); }}
</style>
"""

# Override manual si el usuario lo fuerza
if theme_mode == "Oscuro":
    _css += f"<style>:root{{ {_vars_block(DARK)} }}</style>"
elif theme_mode == "Claro":
    _css += f"<style>:root{{ {_vars_block(LIGHT)} }}</style>"

st.markdown(_css, unsafe_allow_html=True)

# ==========================
# Utilidades básicas
# ==========================
def proximo_lunes(base: date | None = None) -> date:
    base = base or date.today()
    dias = (7 - base.weekday()) % 7
    if dias == 0: dias = 7
    return base + timedelta(days=dias)

def normalizar_texto(texto: str) -> str:
    texto = (texto or "").lower().strip()
    texto = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("utf-8")
    return texto

def get_circuit_options(seccion: str) -> list[str]:
    """Devuelve circuitos válidos según sección."""
    if (seccion or "").lower().strip() == "warm up":
        return ["A", "B", "C"]
    # Work Out: D en adelante
    return list("DEFGHIJKL")

def clamp_circuito_por_seccion(circ: str, seccion: str) -> str:
    opciones = get_circuit_options(seccion)
    return circ if circ in opciones else opciones[0]

# ==========================
# Firebase (init perezoso)
# ==========================
@st.cache_resource(show_spinner=False)
def get_db():
    if not firebase_admin._apps:
        cred_dict = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

ADMIN_ROLES = {"admin", "administrador", "owner", "Admin", "Administrador"}

@st.cache_data(show_spinner=False)
def cargar_ejercicios():
    db = get_db()
    ejercicios_por_nombre: dict[str, dict] = {}

    def _nombre_visible(d: dict, doc_id: str) -> str:
        # Toma el nombre desde los campos más comunes, o usa el ID como fallback
        return (
            d.get("nombre")
            or d.get("Nombre")
            or d.get("ejercicio")
            or d.get("Ejercicio")
            or doc_id
        ).strip()

    try:
        for doc in db.collection("ejercicios").stream():
            if not doc.exists:
                continue
            data = doc.to_dict() or {}
            nombre = _nombre_visible(data, doc.id)
            if nombre:
                ejercicios_por_nombre[nombre] = data
    except Exception as e:
        st.error(f"Error cargando ejercicios: {e}")

    return ejercicios_por_nombre

@st.cache_data(show_spinner=False)
def cargar_usuarios():
    db = get_db()
    docs = db.collection("usuarios").stream()
    return [doc.to_dict() for doc in docs if doc.exists]

@st.cache_data(show_spinner=False)
def cargar_implementos():
    db = get_db()
    impl = {}
    for doc in db.collection("implementos").stream():
        d = doc.to_dict() or {}
        d["pesos"] = d.get("pesos", [])
        impl[str(doc.id)] = d
    return impl

IMPLEMENTOS = cargar_implementos()

def _ensure_len(lista: list[dict], n: int, plantilla: dict):
    if n < 0: n = 0
    while len(lista) < n: lista.append({k: "" for k in plantilla})
    while len(lista) > n: lista.pop()
    return lista
# === Helpers para cargar una rutina como base (no alteran guardado) ===
def _ejercicio_firestore_a_fila_ui_min(ej: dict) -> dict:
    """Mapea un ejercicio guardado en Firestore -> fila UI de crear_rutinas."""
    fila = {
        "Sección": "", "Circuito": "", "Ejercicio": "", "Detalle": "",
        "Series": "", "RepsMin": "", "RepsMax": "", "Peso": "", "RIR": "",
        "Tiempo": "", "Velocidad": "", "Descanso": "", "Tipo": "", "Video": "",
        # Campos que ya usa tu UI internamente
        "BuscarEjercicio": "",
        "Variable_1": "", "Cantidad_1": "", "Operacion_1": "", "Semanas_1": "",
        "Variable_2": "", "Cantidad_2": "", "Operacion_2": "", "Semanas_2": "",
        "Variable_3": "", "Cantidad_3": "", "Operacion_3": "", "Semanas_3": "",
    }

    # Sección (compatibilidad con 'bloque')
    seccion = ej.get("Sección") or ej.get("bloque") or ""
    if seccion not in ["Warm Up", "Work Out"]:
        seccion = "Warm Up" if (ej.get("circuito","") in ["A","B","C"]) else "Work Out"
    fila["Sección"] = seccion

    # Campos directos con alias
    fila["Circuito"]  = ej.get("Circuito")  or ej.get("circuito")  or ""
    fila["Ejercicio"] = ej.get("Ejercicio") or ej.get("ejercicio") or ""
    fila["Detalle"]   = ej.get("Detalle")   or ej.get("detalle")   or ""
    fila["Series"]    = ej.get("Series")    or ej.get("series")    or ""
    fila["Peso"]      = ej.get("Peso")      or ej.get("peso")      or ""
    fila["RIR"]       = ej.get("RIR")       or ej.get("rir")       or ""
    fila["Tiempo"]    = ej.get("Tiempo")    or ej.get("tiempo")    or ""
    fila["Velocidad"] = ej.get("Velocidad") or ej.get("velocidad") or ""
    fila["Tipo"]      = ej.get("Tipo")      or ej.get("tipo")      or ""
    fila["Video"]     = ej.get("Video")     or ej.get("video")     or ""

    # Descanso: puede venir como número o string "3 min"
    # Descanso: puede venir como "", "3", "3 min", None, número, etc.
    descanso_raw = ej.get("Descanso") or ej.get("descanso") or ""

    if isinstance(descanso_raw, str):
        s = descanso_raw.strip()
        # si está vacío, deja "", si no, toma la primera "palabra" (ej. "3" de "3 min")
        fila["Descanso"] = s.split()[0] if s else ""
    elif descanso_raw is None:
        fila["Descanso"] = ""
    else:
        # números u otros tipos simples -> a string
        try:
            fila["Descanso"] = str(descanso_raw)
        except Exception:
            fila["Descanso"] = ""

    # Reps: distintas variantes guardadas
    if "RepsMin" in ej or "RepsMax" in ej:
        fila["RepsMin"] = str(ej.get("RepsMin",""))
        fila["RepsMax"] = str(ej.get("RepsMax",""))
    elif "reps_min" in ej or "reps_max" in ej:
        fila["RepsMin"] = str(ej.get("reps_min",""))
        fila["RepsMax"] = str(ej.get("reps_max",""))
    else:
        rep = str(ej.get("repeticiones","")).strip()
        if "-" in rep:
            mn, mx = rep.split("-", 1)
            fila["RepsMin"], fila["RepsMax"] = mn.strip(), mx.strip()
        else:
            fila["RepsMin"], fila["RepsMax"] = rep, ""

    # Pista + modo exacto al cargar (igual que en editar)
    if fila["Sección"] == "Work Out":
        fila["BuscarEjercicio"] = fila["Ejercicio"]
        fila["_exact_on_load"] = True  # ← forzar match exacto sólo al cargar


    # Asegurar circuito válido según sección (usas clamp_circuito_por_seccion)
    try:
        fila["Circuito"] = clamp_circuito_por_seccion(fila.get("Circuito","") or "", fila["Sección"])
    except Exception:
        pass

    return fila

def _vaciar_dias_en_session():
    """Limpia todos los días ya cargados en session_state para evitar mezclas."""
    keys = [k for k in list(st.session_state.keys()) if k.startswith("rutina_dia_")]
    for k in keys:
        st.session_state.pop(k, None)
    # también limpiamos flags/copias temporales
    for k in list(st.session_state.keys()):
        if any(p in k for p in ["_Warm_Up_", "_Work_Out_", "multiselect_", "do_copy_"]):
            st.session_state.pop(k, None)

def cargar_doc_en_session_base(rutina_dict: dict):
    """
    Carga la rutina (solo días numéricos) a las claves:
      - rutina_dia_{N}_Warm_Up
      - rutina_dia_{N}_Work_Out
    que tu UI ya usa en crear_rutinas.
    """
    _vaciar_dias_en_session()
    if not rutina_dict:
        return

    # Considera únicamente claves numéricas (tus días)
    dias_ordenados = sorted([int(d) for d in rutina_dict.keys() if str(d).isdigit()])
    for d in dias_ordenados:
        ejercicios_dia = rutina_dict.get(str(d), []) or []
        wu, wo = [], []
        for ej in ejercicios_dia:
            fila = _ejercicio_firestore_a_fila_ui_min(ej)
            if fila.get("Sección") == "Warm Up":
                wu.append(fila)
            else:
                wo.append(fila)
        st.session_state[f"rutina_dia_{int(d)}_Warm_Up"] = wu
        st.session_state[f"rutina_dia_{int(d)}_Work_Out"] = wo

# ==========================
#   PÁGINA: CREAR RUTINAS
# ==========================
def crear_rutinas():
    rol = (st.session_state.get("rol") or "").lower()
    if rol not in ("entrenador", "admin", "administrador"):
        st.warning("No tienes permisos para crear rutinas.")
        return

    st.markdown("<h2 class='h-accent'>Crear nueva rutina</h2>", unsafe_allow_html=True)

    cols_top = st.columns([5, 1])
    with cols_top[1]:
        if st.button("🔄", help="Recargar catálogos", type="secondary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # --- Tarjeta de filtros principales ---
    st.markdown("<div class='card'>", unsafe_allow_html=True)

    ejercicios_dict = cargar_ejercicios()
    usuarios = cargar_usuarios()

    nombres = sorted(set(u.get("nombre", "") for u in usuarios))
    correos_entrenadores = sorted([
        u.get("correo", "") for u in usuarios if (u.get("rol", "") or "").lower() in ["entrenador", "admin", "administrador"]
    ])

    # === Selección de cliente/semana ===
    nombre_input = st.text_input("Escribe el nombre del cliente:")
    coincidencias = [n for n in nombres if nombre_input.lower() in (n or "").lower()]
    nombre_sel = st.selectbox("Selecciona de la lista:", coincidencias) if coincidencias else ""

    correo_auto = next((u.get("correo", "") for u in usuarios if u.get("nombre") == nombre_sel), "")
    correo = st.text_input("Correo del cliente:", value=correo_auto)

    valor_defecto = proximo_lunes()
    sel = st.date_input(
        "Fecha de inicio de rutina:",
        value=valor_defecto,
        help="Solo se usan lunes. Si eliges otro día, se ajustará automáticamente al lunes de esa semana."
    )
    fecha_inicio = sel - timedelta(days=sel.weekday()) if sel.weekday() != 0 else sel
    if sel.weekday() != 0:
        st.markdown("<span class='badge badge--warn'>Ajustado automáticamente al lunes seleccionado</span>", unsafe_allow_html=True)

    semanas = st.number_input("Semanas de duración:", min_value=1, max_value=12, value=4)

    objetivo = st.text_area("🎯 Objetivo de la rutina (opcional)", value=st.session_state.get("objetivo", ""))
    st.session_state["objetivo"] = objetivo

    correo_login = (st.session_state.get("correo") or "").strip().lower()
    entrenador = st.text_input("Correo del entrenador responsable:", value=correo_login, disabled=True)
    # === 📥 Cargar rutina previa del MISMO cliente como base (opcional) ===
    with st.expander("📥 Cargar rutina previa como base", expanded=False):
        correo_base = (correo or "").strip().lower()
        if not correo_base:
            st.info("Primero selecciona el **nombre** (para autocompletar) y el **correo** del cliente.")
        else:
            db = get_db()
            # Trae semanas disponibles para este correo
            semanas_dict = {}
            try:
                for doc in db.collection("rutinas_semanales").where("correo", "==", correo_base).stream():
                    data = doc.to_dict() or {}
                    f = data.get("fecha_lunes")
                    if f:
                        semanas_dict[f] = doc.id
            except Exception as e:
                st.error(f"Error leyendo semanas: {e}")

            if not semanas_dict:
                st.info("Este cliente aún no tiene semanas guardadas en 'rutinas_semanales'.")
            else:
                semanas_ordenadas = sorted(semanas_dict.keys())

                # índice por defecto = última semana, acotado al rango válido
                default_idx = (len(semanas_ordenadas) - 1) if semanas_ordenadas else 0
                default_idx = max(0, min(default_idx, len(semanas_ordenadas) - 1)) if semanas_ordenadas else 0

                semana_base = st.selectbox(
                    "Semana a usar como base:",
                    semanas_ordenadas,
                    index=default_idx,
                    key="sel_semana_base_crear",   # clave única
                )

                if st.button("📥 Cargar como base (no guarda nada)", type="secondary", key="btn_cargar_base_crear"):
                    try:
                        doc_id = semanas_dict.get(semana_base)
                        if not doc_id:
                            st.warning("No se encontró el documento de esa semana.")
                        else:
                            doc_data = db.collection("rutinas_semanales").document(doc_id).get().to_dict() or {}
                            rutina_raw = doc_data.get("rutina", {}) or {}
                            # Solo días numéricos
                            rutina_base = {k: v for k, v in rutina_raw.items() if str(k).isdigit()}

                            # Carga en session_state
                            cargar_doc_en_session_base(rutina_base)

                            st.success(f"Rutina de la semana {semana_base} cargada como base ✅")

                            # 🔁 Importante: forzar un rerun inmediato para evitar desincronización
                            # de índices en selectboxes (causa típica de 'list index out of range').
                            st.rerun()
                    except Exception as e:
                        import traceback
                        st.error(f"No se pudo cargar la rutina base: {e}")
                        st.code("".join(traceback.format_exc()))

    st.markdown("</div>", unsafe_allow_html=True)  # /card
    st.markdown("<div class='hr-light'></div>", unsafe_allow_html=True)

    st.markdown("<h3 class='h-accent'>Días de entrenamiento</h3>", unsafe_allow_html=True)

    dias_labels = ["Día 1", "Día 2", "Día 3", "Día 4", "Día 5"]
    tabs = st.tabs(dias_labels)
    dias = dias_labels  # alias

    BASE_HEADERS = [
        "Circuito", "Buscar Ejercicio", "Ejercicio", "Detalle",
        "Series", "Repeticiones", "Peso", "RIR", "Progresión", "Copiar"
    ]
    BASE_SIZES = [1, 2.0, 2.5, 2.0, 0.8, 1.6, 1.0, 0.8, 1.0, 0.8]

    columnas_tabla = [
        "Circuito", "Sección", "Ejercicio", "Detalle", "Series", "Repeticiones",
        "Peso", "Tiempo", "Velocidad", "Descanso", "RIR", "Tipo", "Video"
    ]

    progresion_activa = st.radio("Progresión activa", ["Progresión 1", "Progresión 2", "Progresión 3"],
                                 horizontal=True, index=0)

    for i, tab in enumerate(tabs):
        with tab:
            dia_key = f"rutina_dia_{i+1}"

            for seccion in ["Warm Up", "Work Out"]:
                key_seccion = f"{dia_key}_{seccion.replace(' ', '_')}"
                if key_seccion not in st.session_state:
                    st.session_state[key_seccion] = [{k: "" for k in columnas_tabla} for _ in range(6)]
                    for f in st.session_state[key_seccion]:
                        f["Sección"] = seccion
                        # normalizar circuito inicial según sección
                        f["Circuito"] = clamp_circuito_por_seccion(f.get("Circuito","") or "", seccion)

                # --- Encabezado de sección con toggles ---
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                head_cols = st.columns([7.6, 1.1, 1.2, 1.2], gap="small")
                with head_cols[0]:
                    st.markdown(f"<h4 class='h-accent' style='margin-top:2px'>{seccion}</h4>", unsafe_allow_html=True)
                with head_cols[1]:
                    show_tiempo_sec = st.toggle(
                        "Tiempo",
                        key=f"show_tiempo_{key_seccion}",
                        value=st.session_state.get(f"show_tiempo_{key_seccion}", False),
                    )
                with head_cols[2]:
                    show_vel_sec = st.toggle(
                        "Velocidad",
                        key=f"show_vel_{key_seccion}",
                        value=st.session_state.get(f"show_vel_{key_seccion}", False),
                    )
                with head_cols[3]:
                    show_descanso_sec = st.toggle(
                        "Descanso",
                        key=f"show_desc_{key_seccion}",
                        value=st.session_state.get(f"show_desc_{key_seccion}", False),
                    )

                # ======= Construcción dinámica de columnas =======
                headers = BASE_HEADERS.copy()
                sizes = BASE_SIZES.copy()

                rir_idx = headers.index("RIR")

                if show_tiempo_sec:
                    headers.insert(rir_idx, "Tiempo")
                    sizes.insert(rir_idx, 0.9)
                    rir_idx += 1
                if show_vel_sec:
                    headers.insert(rir_idx, "Velocidad")
                    sizes.insert(rir_idx, 1.0)
                    rir_idx += 1
                if show_descanso_sec:
                    headers.insert(rir_idx, "Descanso")
                    sizes.insert(rir_idx, 0.9)

                # ---------- FORM por sección ----------
                with st.form(f"form_{key_seccion}", clear_on_submit=False):
                    n_filas = st.number_input(
                        "Filas", key=f"num_{key_seccion}", min_value=0, max_value=30,
                        value=len(st.session_state[key_seccion]), step=1
                    )
                    _ensure_len(st.session_state[key_seccion], n_filas, {k: "" for k in columnas_tabla})
                    st.markdown("")

                    # Encabezados centrados
                    header_cols = st.columns(sizes)
                    for c, title in zip(header_cols, headers):
                        c.markdown(f"<div class='header-center'>{title}</div>", unsafe_allow_html=True)

                    # ------ Render filas ------
                    for idx, fila in enumerate(st.session_state[key_seccion]):
                        key_entrenamiento = f"{i}_{seccion.replace(' ','_')}_{idx}"
                        cols = st.columns(sizes)
                        pos = {h: k for k, h in enumerate(headers)}

                        # === Circuito (RESTRINGIDO POR SECCIÓN) ===
                        opciones_circuito = get_circuit_options(seccion)
                        # normalizar si el valor actual no es válido
                        circ_actual = fila.get("Circuito") or ""
                        if circ_actual not in opciones_circuito:
                            circ_actual = opciones_circuito[0]
                            fila["Circuito"] = circ_actual

                        fila["Circuito"] = cols[pos["Circuito"]].selectbox(
                            "", opciones_circuito,
                            index=(opciones_circuito.index(circ_actual) if circ_actual in opciones_circuito else 0),
                            key=f"circ_{key_entrenamiento}",
                            label_visibility="collapsed"
                        )

                        # Buscar + Ejercicio
                        if seccion == "Work Out":
                            # === Buscar + Ejercicio (modo exacto al cargar, luego fuzzy) ===
                            palabra = cols[pos["Buscar Ejercicio"]].text_input(
                                "", value=fila.get("BuscarEjercicio", ""),
                                key=f"buscar_{key_entrenamiento}", label_visibility="collapsed", placeholder="Buscar…"
                            )
                            fila["BuscarEjercicio"] = palabra

                            nombre_original = (fila.get("Ejercicio","") or "").strip()
                            exact_on_load = bool(fila.get("_exact_on_load", False))

                            def _buscar_fuzzy_local(q: str) -> list[str]:
                                if not q.strip():
                                    return []
                                tokens = normalizar_texto(q).split()
                                res = []
                                for n in ejercicios_dict.keys():
                                    nn = normalizar_texto(n)
                                    if all(t in nn for t in tokens):
                                        res.append(n)
                                return res

                            # Construye lista de opciones
                            if exact_on_load:
                                # Si no escribiste nada o escribiste exactamente el original -> lista exacta
                                if (not palabra.strip()) or (normalizar_texto(palabra) == normalizar_texto(nombre_original)):
                                    ejercicios_encontrados = [nombre_original] if nombre_original else []
                                else:
                                    # El usuario cambió la búsqueda -> pasa a fuzzy y desactiva exact_on_load
                                    ejercicios_encontrados = _buscar_fuzzy_local(palabra)
                                    fila["_exact_on_load"] = False
                            else:
                                ejercicios_encontrados = _buscar_fuzzy_local(palabra)

                            # Fallback: si no hay resultados y tenemos un original, mantenlo como única opción
                            if not ejercicios_encontrados and nombre_original:
                                ejercicios_encontrados = [nombre_original]

                            # Quita duplicados preservando orden
                            vistos = set()
                            ejercicios_encontrados = [e for e in ejercicios_encontrados if not (e in vistos or vistos.add(e))]

                            seleccionado = cols[pos["Ejercicio"]].selectbox(
                                "",
                                ejercicios_encontrados if ejercicios_encontrados else ["(sin resultados)"],
                                key=f"select_{key_entrenamiento}",
                                label_visibility="collapsed"
                            )
                            if seleccionado != "(sin resultados)":
                                fila["Ejercicio"] = seleccionado
                                fila["Video"] = (ejercicios_dict.get(seleccionado, {}) or {}).get("video", "").strip()

                        else:
                            # Warm Up: sin buscador, nombre libre
                            cols[pos["Buscar Ejercicio"]].markdown("&nbsp;", unsafe_allow_html=True)
                            fila["Ejercicio"] = cols[pos["Ejercicio"]].text_input(
                                "", value=fila.get("Ejercicio",""),
                                key=f"ej_{key_entrenamiento}", label_visibility="collapsed", placeholder="Nombre del ejercicio"
                            )

                        # Detalle
                        fila["Detalle"] = cols[pos["Detalle"]].text_input(
                            "", value=fila.get("Detalle",""),
                            key=f"det_{key_entrenamiento}", label_visibility="collapsed", placeholder="Notas (opcional)"
                        )
                        # Series
                        fila["Series"] = cols[pos["Series"]].text_input(
                            "", value=fila.get("Series",""),
                            key=f"ser_{key_entrenamiento}", label_visibility="collapsed", placeholder="N°"
                        )
                        # Reps min/max en una celda
                        cmin, cmax = cols[pos["Repeticiones"]].columns(2)
                        fila["RepsMin"] = cmin.text_input(
                            "", value=str(fila.get("RepsMin","")),
                            key=f"rmin_{key_entrenamiento}", label_visibility="collapsed", placeholder="Min"
                        )
                        fila["RepsMax"] = cmax.text_input(
                            "", value=str(fila.get("RepsMax","")),
                            key=f"rmax_{key_entrenamiento}", label_visibility="collapsed", placeholder="Max"
                        )

                        # Peso (select si implemento tiene pesos)
                        peso_widget_key = f"peso_{key_entrenamiento}"
                        peso_value = fila.get("Peso","")
                        pesos_disponibles = []
                        usar_text_input = True
                        try:
                            nombre_ej = fila.get("Ejercicio","")
                            ej_doc = ejercicios_dict.get(nombre_ej, {}) or {}
                            id_impl = str(ej_doc.get("id_implemento","") or "")
                            if id_impl and id_impl != "1" and id_impl in IMPLEMENTOS:
                                pesos_disponibles = IMPLEMENTOS[id_impl].get("pesos", []) or []
                                usar_text_input = not bool(pesos_disponibles)
                        except Exception:
                            usar_text_input = True

                        if not usar_text_input and pesos_disponibles:
                            opciones_peso = [str(p) for p in pesos_disponibles]
                            # Normaliza el valor actual al set de opciones
                            if str(peso_value) not in opciones_peso and opciones_peso:
                                peso_value = opciones_peso[0]
                            # Índice seguro (0 si no está)
                            idx_peso = opciones_peso.index(str(peso_value)) if str(peso_value) in opciones_peso else 0

                            fila["Peso"] = cols[pos["Peso"]].selectbox(
                                "",
                                options=opciones_peso,
                                index=idx_peso,                  # ← evita index out of range
                                key=peso_widget_key,
                                label_visibility="collapsed"
                            )
                        else:
                            fila["Peso"] = cols[pos["Peso"]].text_input(
                                "", value=str(peso_value),
                                key=peso_widget_key, label_visibility="collapsed", placeholder="Kg"
                            )


                        # Tiempo / Velocidad / Descanso dinámicos
                        if "Tiempo" in pos:
                            fila["Tiempo"] = cols[pos["Tiempo"]].text_input(
                                "", value=str(fila.get("Tiempo","")),
                                key=f"tiempo_{key_entrenamiento}", label_visibility="collapsed", placeholder="Seg"
                            )
                        else:
                            fila.setdefault("Tiempo","")

                        if "Velocidad" in pos:
                            fila["Velocidad"] = cols[pos["Velocidad"]].text_input(
                                "", value=str(fila.get("Velocidad","")),
                                key=f"vel_{key_entrenamiento}", label_visibility="collapsed", placeholder="m/s"
                            )
                        else:
                            fila.setdefault("Velocidad","")

                        if "Descanso" in pos:
                            opciones_descanso = ["", "1", "2", "3", "4", "5"]
                            valor_actual_desc = str(fila.get("Descanso", "")).strip()
                            if " " in valor_actual_desc:
                                valor_actual_desc = valor_actual_desc.split()[0]
                            idx_desc = opciones_descanso.index(valor_actual_desc) if valor_actual_desc in opciones_descanso else 0
                            fila["Descanso"] = cols[pos["Descanso"]].selectbox(
                                "",
                                options=opciones_descanso,
                                index=idx_desc,
                                key=f"desc_{key_entrenamiento}",
                                label_visibility="collapsed",
                                help="Minutos de descanso (1–5). Deja vacío si no aplica."
                            )
                        else:
                            fila.setdefault("Descanso","")

                        # RIR
                        fila["RIR"] = cols[pos["RIR"]].text_input(
                            "", value=fila.get("RIR",""),
                            key=f"rir_{key_entrenamiento}", label_visibility="collapsed", placeholder="RIR"
                        )

                        # Progresiones
                        prog_cell = cols[pos["Progresión"]].columns([1, 1, 1])
                        mostrar_progresion = prog_cell[1].checkbox("", key=f"prog_check_{key_entrenamiento}_{idx}")

                        copy_cell = cols[pos["Copiar"]].columns([1, 1, 1])
                        mostrar_copia = copy_cell[1].checkbox("", key=f"copy_check_{key_entrenamiento}_{idx}")

                        if mostrar_progresion:
                            st.markdown("<div class='hr-light'></div>", unsafe_allow_html=True)
                            st.markdown("<div class='h-accent'>Progresiones activas</div>", unsafe_allow_html=True)
                            p = int(progresion_activa.split()[-1])
                            pcols = st.columns(4)

                            variable_key = f"Variable_{p}"
                            cantidad_key = f"Cantidad_{p}"
                            operacion_key = f"Operacion_{p}"
                            semanas_key = f"Semanas_{p}"

                            opciones_var = ["", "peso", "velocidad", "tiempo", "descanso", "rir", "series", "repeticiones"]
                            opciones_ope = ["", "multiplicacion", "division", "suma", "resta"]

                            fila[variable_key] = pcols[0].selectbox(
                                f"Variable {p}",
                                opciones_var,
                                index=(opciones_var.index(fila.get(variable_key, "")) if fila.get(variable_key, "") in opciones_var else 0),
                                key=f"var{p}_{key_entrenamiento}_{idx}"
                            )
                            fila[cantidad_key] = pcols[1].text_input(
                                f"Cantidad {p}", value=fila.get(cantidad_key, ""), key=f"cant{p}_{key_entrenamiento}_{idx}"
                            )
                            fila[operacion_key] = pcols[2].selectbox(
                                f"Operación {p}", opciones_ope,
                                index=(opciones_ope.index(fila.get(operacion_key, "")) if fila.get(operacion_key, "") in opciones_ope else 0),
                                key=f"ope{p}_{key_entrenamiento}_{idx}"
                            )
                            fila[semanas_key] = pcols[3].text_input(
                                f"Semanas {p}", value=fila.get(semanas_key, ""), key=f"sem{p}_{key_entrenamiento}_{idx}"
                            )

                        # Copia entre días
                        if mostrar_copia:
                            copiar_cols = st.columns([1, 3])
                            st.caption("Selecciona día(s) y presiona **Actualizar sección** para copiar.")
                            dias_copia = copiar_cols[1].multiselect(
                                "Días destino", dias,
                                key=f"multiselect_{key_entrenamiento}_{idx}"
                            )
                            st.session_state[f"do_copy_{key_entrenamiento}_{idx}"] = True
                        else:
                            st.session_state.pop(f"multiselect_{key_entrenamiento}_{idx}", None)
                            st.session_state.pop(f"do_copy_{key_entrenamiento}_{idx}", None)

                    submitted = st.form_submit_button("Actualizar sección", type="primary")
                    if submitted:
                        # Normalización final de circuitos y copia
                        for idx, fila in enumerate(st.session_state[key_seccion]):
                            # Clamp circuito según sección por si entró algo viejo en session_state
                            fila["Circuito"] = clamp_circuito_por_seccion(fila.get("Circuito","") or "", seccion)

                            key_entrenamiento = f"{i}_{seccion.replace(' ','_')}_{idx}"
                            do_copy_key = f"do_copy_{key_entrenamiento}_{idx}"
                            multisel_key = f"multiselect_{key_entrenamiento}_{idx}"
                            if st.session_state.get(do_copy_key):
                                dias_copia = st.session_state.get(multisel_key, [])
                                if dias_copia:
                                    for dia_destino in dias_copia:
                                        idx_dia = dias.index(dia_destino)
                                        key_destino = f"rutina_dia_{idx_dia + 1}_{seccion.replace(' ', '_')}"
                                        if key_destino not in st.session_state:
                                            st.session_state[key_destino] = []
                                        nuevo_ejercicio = {k: v for k, v in fila.items()}
                                        # asegurar tamaño
                                        while len(st.session_state[key_destino]) <= idx:
                                            fila_vacia = {k: "" for k in columnas_tabla}
                                            fila_vacia["Sección"] = seccion
                                            # clamp circuito también en destino
                                            fila_vacia["Circuito"] = clamp_circuito_por_seccion(fila_vacia.get("Circuito","") or "", seccion)
                                            st.session_state[key_destino].append(fila_vacia)
                                        # clamp destino
                                        nuevo_ejercicio["Circuito"] = clamp_circuito_por_seccion(nuevo_ejercicio.get("Circuito","") or "", seccion)
                                        st.session_state[key_destino][idx] = nuevo_ejercicio
                        st.success("Sección actualizada ✅")
                st.markdown("</div>", unsafe_allow_html=True)  # /card

            st.markdown("<div class='hr-light'></div>", unsafe_allow_html=True)

    # ======= Sidebar de análisis =======
    with st.sidebar:
        st.markdown("<div class='sidebar-card'>", unsafe_allow_html=True)
        st.markdown("### 🧮 Series por categoría")
        opcion_categoria = st.selectbox("Categoría para análisis:", ["grupo_muscular_principal", "patron_de_movimiento"])
        st.markdown("</div>", unsafe_allow_html=True)

    ejercicios_dict = cargar_ejercicios()  # asegurar en scope
    contador = {}
    nombres_originales = {}
    dias_keys = [k for k in st.session_state if k.startswith("rutina_dia_") and "_Work_Out" in k]
    for key_dia in dias_keys:
        ejercicios = st.session_state.get(key_dia, [])
        for ejercicio in ejercicios:
            nombre_raw = str(ejercicio.get("Ejercicio", "")).strip()
            nombre_norm = normalizar_texto(nombre_raw)
            try:
                series = int(ejercicio.get("Series", 0))
            except:
                series = 0
            if not nombre_norm: continue
            coincidencias = [
                data for nombre, data in ejercicios_dict.items()
                if normalizar_texto(nombre) == nombre_norm
            ]
            data = coincidencias[0] if coincidencias else None
            if not data:
                categoria_valor = "(no encontrado)"
            else:
                try:
                    categoria_valor = data.get(opcion_categoria, "(sin dato)")
                except:
                    categoria_valor = "(error)"
            categoria_norm = normalizar_texto(str(categoria_valor))
            if categoria_norm in contador:
                contador[categoria_norm] += series
                nombres_originales[categoria_norm].add(categoria_valor)
            else:
                contador[categoria_norm] = series
                nombres_originales[categoria_norm] = {categoria_valor}

    with st.sidebar:
        st.markdown("<div class='sidebar-card'>", unsafe_allow_html=True)
        if contador:
            df = pd.DataFrame({
                "Categoría": [
                    ", ".join(sorted(cat.replace("_", " ").capitalize() for cat in nombres_originales[k]))
                    for k in contador
                ],
                "Series": [contador[k] for k in contador]
            }).sort_values("Series", ascending=False)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos de series aún.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ======= Previsualización =======
    def _f(v):
        try:
            s = str(v).strip().replace(",", ".")
            if s == "": return None
            if "-" in s: s = s.split("-", 1)[0].strip()
            return float(s)
        except: return None

    if st.button("🔍 Previsualizar rutina", type="secondary"):
        st.markdown("<h3 class='h-accent'>📅 Previsualización de todas las semanas con progresiones aplicadas</h3>", unsafe_allow_html=True)
        for semana_idx in range(1, int(semanas) + 1):
            with st.expander(f"Semana {semana_idx}"):
                for i, dia_nombre in enumerate(dias):
                    wu_key = f"rutina_dia_{i + 1}_Warm_Up"
                    wo_key = f"rutina_dia_{i + 1}_Work_Out"
                    ejercicios = (st.session_state.get(wu_key, []) or []) + (st.session_state.get(wo_key, []) or [])
                    if not ejercicios:
                        continue

                    st.write(f"**{dia_nombre}**")
                    tabla = []
                    for ej in ejercicios:
                        ejv = ej.copy()
                        for p in range(1, 3+1):
                            variable = str(ej.get(f"Variable_{p}", "")).strip().lower()
                            cantidad = ej.get(f"Cantidad_{p}", "")
                            operacion = str(ej.get(f"Operacion_{p}", "")).strip().lower()
                            semanas_txt = str(ej.get(f"Semanas_{p}", ""))
                            if not (variable and operacion and cantidad):
                                continue
                            try:
                                semanas_aplicar = [int(s.strip()) for s in semanas_txt.split(",") if s.strip().isdigit()]
                            except:
                                semanas_aplicar = []
                            if semana_idx in semanas_aplicar:
                                if variable == "repeticiones":
                                    try:
                                        mn = _f(ejv.get("RepsMin","")); mx = _f(ejv.get("RepsMax",""))
                                        def op(v, cant, o):
                                            if v is None: return v
                                            v=float(v); cant=float(cant)
                                            return v+cant if o=="suma" else v-cant if o=="resta" else v*cant if o=="multiplicacion" else (v/cant if cant!=0 else v)
                                        ejv["RepsMin"] = op(mn, cantidad, operacion)
                                        ejv["RepsMax"] = op(mx, cantidad, operacion)
                                    except: pass
                                else:
                                    key_cap = variable.capitalize()
                                    val = ejv.get(key_cap, "")
                                    if val != "":
                                        try:
                                            ejv[key_cap] = aplicar_progresion(val, float(cantidad), operacion)
                                        except:
                                            pass

                        rep_str = ""
                        mn, mx = ejv.get("RepsMin",""), ejv.get("RepsMax","")
                        if mn != "" and mx != "":
                            rep_str = f"{mn}–{mx}"
                        elif mn != "" or mx != "":
                            rep_str = str(mn or mx)

                        # El bloque se respeta por "Sección" y circuitos ya están validados por sección
                        tabla.append({
                            "bloque": ejv.get("Sección") or ("Warm Up" if ejv.get("Circuito","") in ["A","B","C"] else "Work Out"),
                            "circuito": ejv.get("Circuito",""),
                            "ejercicio": ejv.get("Ejercicio",""),
                            "series": ejv.get("Series",""),
                            "repeticiones": rep_str,
                            "peso": ejv.get("Peso",""),
                            "tiempo": ejv.get("Tiempo",""),
                            "velocidad": ejv.get("Velocidad",""),
                            "descanso": ejv.get("Descanso",""),
                            "rir": ejv.get("RIR",""),
                            "tipo": ejv.get("Tipo",""),
                        })

                    st.dataframe(pd.DataFrame(tabla), use_container_width=True, hide_index=True)

    # ======= Guardar =======
    if st.button("Guardar Rutina", type="primary", use_container_width=True):
        if all([str(nombre_sel).strip(), str(correo).strip(), str(entrenador).strip()]):
            objetivo = st.session_state.get("objetivo", "")
            guardar_rutina(
                nombre_sel.strip(),
                correo.strip(),
                entrenador.strip(),
                fecha_inicio,
                int(semanas),
                dias_labels,
                objetivo=objetivo,
            )
        else:
            st.warning("⚠️ Completa nombre, correo y entrenador antes de guardar.")

