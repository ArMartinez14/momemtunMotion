# ver_rutinas.py — versión con "modo entrenador" para deportistas y "Sesión anterior" por ejercicio

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta, date
import json
import random
import re

from herramientas import actualizar_progresiones_individual
from soft_login_full import soft_login_barrier

soft_login_barrier(required_roles=["entrenador", "deportista", "admin"])

# ==========================
#  Mensajes motivacionales
# ==========================
MENSAJES_MOTIVACIONALES = [
    "💪 ¡Éxito en tu entrenamiento de hoy, {nombre}! 🔥",
    "🚀 {nombre}, cada repetición te acerca más a tu objetivo.",
    "🏋️‍♂️ {nombre}, hoy es un gran día para superar tus límites.",
    "🔥 Vamos {nombre}, conviértete en la mejor versión de ti mismo.",
    "⚡ {nombre}, la constancia es la clave. ¡Dalo todo hoy!",
    "🥇 {nombre}, cada sesión es un paso más hacia la victoria.",
    "🌟 Nunca te detengas, {nombre}. ¡Hoy vas a brillar en tu entrenamiento!",
    "🏆 {nombre}, recuerda: disciplina > motivación. ¡Tú puedes!",
    "🙌 A disfrutar el proceso, {nombre}. ¡Confía en ti!",
    "💥 {nombre}, el esfuerzo de hoy es el resultado de mañana.",
    "⚡ {nombre}, supera tus límites ahora mismo.",
    "🔥 {nombre}, no rendirse es tu especialidad.",
    "🍃 {nombre}, jamás te rindas.",
    "🔥 {nombre}, cada repetición es un paso más cerca de tu mejor versión.",
    "🏋️ {nombre}, los límites están en tu mente, el cuerpo puede más.",
    "🔥 {nombre}, no pares cuando estés cansado, para cuando hayas terminado.",
    "💪 {nombre}, cada gota de sudor es inversión en tu rendimiento.",
    "🚀 {nombre}, cada serie cuenta, cada día suma. ¡Hazlo grande!",
    "🔥 {nombre}, la incomodidad es la señal de que estás creciendo.",
    "🏹 {nombre}, entrena como si fueras a competir contra tu mejor versión.",
    "🌌 {nombre}, si quieres resultados distintos, exige más de ti mismo.",
    "💥 {nombre}, la fuerza no viene de lo que puedes hacer, sino de lo que superas.",
    "🔥 {nombre}, hoy es el día perfecto para superar tu récord.",
    "🔥 {nombre}, tu cuerpo puede aguantar más de lo que tu mente cree.",
    "⚔️ {nombre}, cada levantamiento es una batalla, ¡gánala!",
    "🔥 {nombre}, no esperes motivación, crea disciplina en cada serie.",
    "💪 {nombre}, los campeones se forman cuando nadie los ve entrenar.",
]

# ==========================
#  Helpers numéricos
# ==========================
def _to_float_or_none(v):
    try:
        s = str(v).strip().replace(",", ".")
        if s == "":
            return None
        if "-" in s:
            s = s.split("-", 1)[0].strip()
        return float(s)
    except:
        return None

def _to_float_or_zero(v):
    f = _to_float_or_none(v)
    return 0.0 if f is None else f

# ==========================
#  Mensaje motivador diario
# ==========================
def mensaje_motivador_del_dia(nombre: str, correo_id: str) -> str:
    hoy = date.today().isoformat()
    key = f"mot_msg_{correo_id}_{hoy}"
    if key not in st.session_state:
        st.session_state[key] = random.choice(MENSAJES_MOTIVACIONALES).format(nombre=nombre or "Atleta")
    return st.session_state[key]

def mostrar_banner_motivador(texto: str):
    st.markdown(
        f"""
        <div style='
            background: linear-gradient(90deg, #1e88e5 0%, #42a5f5 100%);
            padding:14px 16px;
            border-radius:12px;
            margin:14px 0;
            color:white;
            font-size:18px;
            text-align:center;
            font-weight:700;'>
            {texto}
        </div>
        """,
        unsafe_allow_html=True
    )

# ==========================
#  Normalizaciones de ejercicios
# ==========================
def _to_ej_dict(x):
    """Normaliza un ejercicio a dict uniforme."""
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        return {
            "bloque": "",
            "seccion": "",
            "circuito": "",
            "ejercicio": x,
            "detalle": "",
            "series": "",
            "reps_min": "",
            "reps_max": "",
            "peso": "",
            "tiempo": "",
            "velocidad": "",
            "rir": "",
            "tipo": "",
            "video": "",
        }
    return {}

def ordenar_circuito(ejercicio):
    if not isinstance(ejercicio, dict):
        return 99
    orden = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7}
    return orden.get(str(ejercicio.get("circuito", "")).upper(), 99)

def obtener_lista_ejercicios(data_dia):
    """
    Devuelve SIEMPRE una lista de dicts (ejercicios). Soporta:
    - {"ejercicios": {"0": {...}, "1": {...}}}
    - {"0": {...}, "1": {...}}
    - [ {...}, {...} ]
    """
    if data_dia is None:
        return []

    if isinstance(data_dia, dict):
        if "ejercicios" in data_dia:
            ejercicios = data_dia["ejercicios"]
            if isinstance(ejercicios, dict):
                try:
                    pares = sorted(ejercicios.items(), key=lambda kv: int(kv[0]))
                    return [v for _, v in pares if isinstance(v, dict)]
                except Exception:
                    return [v for v in ejercicios.values() if isinstance(v, dict)]
            elif isinstance(ejercicios, list):
                return [e for e in ejercicios if isinstance(e, dict)]
            else:
                return []

        claves_numericas = [k for k in data_dia.keys() if str(k).isdigit()]
        if claves_numericas:
            try:
                pares = sorted(((k, data_dia[k]) for k in claves_numericas), key=lambda kv: int(kv[0]))
                return [v for _, v in pares if isinstance(v, dict)]
            except Exception:
                return [data_dia[k] for k in data_dia if isinstance(data_dia[k], dict)]

        return [v for v in data_dia.values() if isinstance(v, dict)]

    if isinstance(data_dia, list):
        if len(data_dia) == 1 and isinstance(data_dia[0], dict) and "ejercicios" in data_dia[0]:
            return obtener_lista_ejercicios(data_dia[0])
        return [e for e in data_dia if isinstance(e, dict)]

    return []

def _num_or_empty(x):
    s = str(x).strip()
    m = re.search(r"-?\d+(\.\d+)?", s)
    return m.group(0) if m else ""

def defaults_de_ejercicio(e: dict):
    """Valores por defecto para construir series_data."""
    reps_def = _num_or_empty(e.get("reps_min", "")) or _num_or_empty(e.get("repeticiones", ""))
    peso_def = _num_or_empty(e.get("peso", ""))
    rir_def  = _num_or_empty(e.get("rir", ""))
    return reps_def, peso_def, rir_def

def a_lista_de_ejercicios(ejercicios):
    if ejercicios is None:
        return []
    if isinstance(ejercicios, dict):
        try:
            pares = sorted(ejercicios.items(), key=lambda kv: int(kv[0]))
            ejercicios = [v for _, v in pares]
        except Exception:
            ejercicios = list(ejercicios.values())
    if not isinstance(ejercicios, list):
        ejercicios = []
    ejercicios = [e for e in ejercicios if isinstance(e, dict)]
    return ejercicios

# ==========================
#  Helpers de guardado puntual
# ==========================
def _match_mismo_ejercicio(a: dict, b: dict) -> bool:
    """Coincidencia estable por campos lógicos."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    return (
        (a.get("ejercicio", "") == b.get("ejercicio", "")) and
        (a.get("circuito", "")  == b.get("circuito", ""))  and
        (a.get("bloque", a.get("seccion", "")) == b.get("bloque", b.get("seccion", "")))
    )

def _parsear_series(series_data: list[dict]):
    """Devuelve (peso_alcanzado, reps_alcanzadas, rir_alcanzado) a partir de series_data."""
    pesos, reps, rirs = [], [], []
    for s in (series_data or []):
        try:
            val = str(s.get("peso", "")).replace(",", ".").replace("kg", "").strip()
            if val != "":
                pesos.append(float(val))
        except:
            pass
        try:
            reps_raw = str(s.get("reps", "")).strip()
            if reps_raw.isdigit():
                reps.append(int(reps_raw))
        except:
            pass
        try:
            val = str(s.get("rir", "")).replace(",", ".").strip()
            if val != "":
                rirs.append(float(val))
        except:
            pass

    peso_alcanzado  = max(pesos) if pesos else None
    reps_alcanzadas = max(reps)  if reps  else None
    rir_alcanzado   = min(rirs)  if rirs  else None
    return peso_alcanzado, reps_alcanzadas, rir_alcanzado

def guardar_reporte_ejercicio(
    db,
    correo_cliente_norm: str,
    semana_sel: str,
    dia_sel: str,
    ejercicio_editado: dict,
):
    """
    Guarda SOLO el ejercicio indicado dentro de 'rutina.{dia_sel}' del documento
    {correo_cliente_norm}_{semana_sel}. Upsert del día; no toca otros días.
    """
    fecha_norm = semana_sel.replace("-", "_")
    doc_id = f"{correo_cliente_norm}_{fecha_norm}"
    doc_ref = db.collection("rutinas_semanales").document(doc_id)
    doc = doc_ref.get()

    if not doc.exists:
        # Crea documento con el día y solo este ejercicio
        doc_ref.set({"rutina": {dia_sel: [ejercicio_editado]}}, merge=True)
        return True

    rutina = doc.to_dict().get("rutina", {})
    ejercicios_raw = rutina.get(dia_sel, [])
    ejercicios_lista = obtener_lista_ejercicios(ejercicios_raw)

    changed = False
    for i, ex in enumerate(ejercicios_lista):
        if _match_mismo_ejercicio(ex, ejercicio_editado):
            ejercicios_lista[i] = ejercicio_editado
            changed = True
            break

    if not changed:
        # si no existía, lo agrega al final (puedes omitir esto si no quieres insertar)
        ejercicios_lista.append(ejercicio_editado)

    doc_ref.set({"rutina": {dia_sel: ejercicios_lista}}, merge=True)
    return True

# ==========================
#  Fechas/semana anterior
# ==========================
def lunes_str_a_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def semana_anterior(fecha_lunes_str: str) -> str:
    return (lunes_str_a_date(fecha_lunes_str) - timedelta(days=7)).strftime("%Y-%m-%d")

# ==========================
#  Vista principal
# ==========================
def ver_rutinas():
    # === FIREBASE INIT ===
    if not firebase_admin._apps:
        cred_dict = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    def normalizar_correo(correo):
        return correo.strip().lower().replace("@", "_").replace(".", "_")

    def obtener_fecha_lunes():
        hoy = datetime.now()
        lunes = hoy - timedelta(days=hoy.weekday())
        return lunes.strftime("%Y-%m-%d")

    def es_entrenador(rol):
        return rol.lower() in ["entrenador", "admin", "administrador"]

    @st.cache_data
    def cargar_rutinas_filtradas(correo, rol):
        if es_entrenador(rol):
            docs = db.collection("rutinas_semanales").stream()
        else:
            docs = db.collection("rutinas_semanales").where("correo", "==", correo).stream()
        return [doc.to_dict() for doc in docs]

    # === Usuario actual
    correo_raw = st.session_state.get("correo", "").strip().lower()
    if not correo_raw:
        st.error("❌ No hay correo registrado. Por favor vuelve a iniciar sesión.")
        st.stop()

    correo_norm = normalizar_correo(correo_raw)

    doc_user = db.collection("usuarios").document(correo_norm).get()
    if not doc_user.exists:
        st.error(f"❌ No se encontró el usuario con ID '{correo_norm}'. Contacta a soporte.")
        st.stop()

    datos_usuario = doc_user.to_dict()
    nombre = datos_usuario.get("nombre", "Usuario")
    rol = datos_usuario.get("rol", "desconocido")
    rol = st.session_state.get("rol", rol)

    # Mensaje motivador solo deportistas
    if rol.strip().lower() == "deportista":
        mensaje = mensaje_motivador_del_dia(nombre, correo_norm)
        mostrar_banner_motivador(mensaje)

    cols = st.columns([5, 1])
    with cols[1]:
        if st.button("🔄"):
            st.cache_data.clear()
            st.rerun()

    if st.checkbox("👤 Mostrar información personal", value=True):
        st.success(f"Bienvenido {nombre} ({rol})")

    # === Cargar rutinas
    rutinas = cargar_rutinas_filtradas(correo_raw, rol)
    if not rutinas:
        st.warning("⚠️ No se encontraron rutinas.")
        st.stop()

    # Entrenador: elegir cliente
    if es_entrenador(rol):
        clientes = sorted(set(r["cliente"] for r in rutinas if "cliente" in r))
        cliente_input = st.text_input("👤 Escribe el nombre del cliente:", key="cliente_input")
        cliente_opciones = [c for c in clientes if cliente_input.lower() in c.lower()]
        cliente_sel = st.selectbox("Selecciona cliente:", cliente_opciones if cliente_opciones else clientes, key="cliente_sel")
        rutinas_cliente = [r for r in rutinas if r.get("cliente") == cliente_sel]
    else:
        rutinas_cliente = rutinas

    correo_cliente = rutinas_cliente[0].get("correo", "")
    correo_cliente_norm = normalizar_correo(correo_cliente)

    semanas = sorted({r["fecha_lunes"] for r in rutinas_cliente}, reverse=True)
    semana_actual = obtener_fecha_lunes()
    semana_sel = st.selectbox(
        "📆 Semana",
        semanas,
        index=semanas.index(semana_actual) if semana_actual in semanas else 0,
        key="semana_sel"
    )

    rutina_doc = next((r for r in rutinas_cliente if r["fecha_lunes"] == semana_sel), None)
    if not rutina_doc:
        st.warning("⚠️ No hay rutina para esa semana.")
        st.stop()

    # Info de bloque
    bloque_id = rutina_doc.get("bloque_rutina")
    if bloque_id:
        bloques_mismo_cliente = [r for r in rutinas_cliente if r.get("bloque_rutina") == bloque_id]
        fechas_bloque = sorted([r["fecha_lunes"] for r in bloques_mismo_cliente])
        try:
            semana_actual_idx = fechas_bloque.index(semana_sel) + 1
            total_semanas_bloque = len(fechas_bloque)
            st.markdown(f"📦 <b>Bloque de rutina:</b> Semana {semana_actual_idx} de {total_semanas_bloque}", unsafe_allow_html=True)
        except ValueError:
            st.info("ℹ️ Semana no encontrada en bloque de rutina.")
    else:
        st.warning("⚠️ Esta rutina no tiene un identificador de bloque.")

    dias_disponibles = sorted([k for k in rutina_doc["rutina"].keys() if k.isdigit()], key=int)
    dia_sel = st.selectbox("📅 Día", dias_disponibles, key="dia_sel")

    ejercicios = obtener_lista_ejercicios(rutina_doc["rutina"][dia_sel])
    ejercicios.sort(key=ordenar_circuito)

    # ==========================
    #  NUEVO: banderas de visibilidad y sesión anterior
    # ==========================
    is_entrenador = es_entrenador(rol)
    show_adv_controls = False
    if not is_entrenador and rol.strip().lower() == "deportista":
        show_adv_controls = st.checkbox(
            "Mostrar Sesiones Anteriores",
            value=False,
            help="Muestra los mismos checkboxes que ve un entrenador bajo cada ejercicio (incluye 'Sesión anterior')."
        )
    can_show_per_exercise_toggles = is_entrenador or show_adv_controls

    # Si se podrán ver los controles por ejercicio (entrenador o deportista en modo avanzado),
    # preparamos referencia a la semana anterior para el MISMO día:
    rutina_prev_doc = None
    ejercicios_prev_map = {}
    if can_show_per_exercise_toggles:
        semana_prev = semana_anterior(semana_sel)
        rutina_prev_doc = next((r for r in rutinas_cliente if r.get("fecha_lunes") == semana_prev), None)
        if rutina_prev_doc and str(dia_sel) in rutina_prev_doc.get("rutina", {}):
            ejercicios_prev = obtener_lista_ejercicios(rutina_prev_doc["rutina"][str(dia_sel)])
            for ex in ejercicios_prev:
                key_prev = (
                    (ex.get("bloque") or ex.get("seccion") or "").strip().lower(),
                    (ex.get("circuito") or "").strip().upper(),
                    (ex.get("ejercicio") or "").strip().lower(),
                )
                ejercicios_prev_map[key_prev] = ex

    def _prev_para(e_act: dict):
        key_act = (
            (e_act.get("bloque") or e_act.get("seccion") or "").strip().lower(),
            (e_act.get("circuito") or "").strip().upper(),
            (e_act.get("ejercicio") or "").strip().lower(),
        )
        return ejercicios_prev_map.get(key_act)

    # ===== Estilos =====
    st.markdown(f"### Ejercicios del día {dia_sel}")
    st.markdown("""
        <style>
        .compact-input input { font-size: 12px !important; width: 100px !important; }
        .linea-blanca { border-bottom: 2px solid white; margin: 15px 0; }
        .ejercicio { font-size: 18px !important; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    # ===== Agrupar por circuito y render =====
    ejercicios_por_circuito = {}
    for e in ejercicios:
        circuito = (e.get("circuito", "Z") or "Z").upper()
        ejercicios_por_circuito.setdefault(circuito, []).append(e)

    for circuito, lista in sorted(ejercicios_por_circuito.items()):
        if circuito == "A":
            st.subheader("Warm-Up")
        elif circuito == "D":
            st.subheader("Workout")

        st.markdown(f"### Circuito {circuito}")
        st.markdown("<div class='bloque'>", unsafe_allow_html=True)

        for idx, e in enumerate(lista):
            # ======= Header/Info del ejercicio =======
            ejercicio_nombre = e.get("ejercicio", f"Ejercicio {idx+1}")
            ejercicio_id = f"{circuito}_{ejercicio_nombre}_{idx}".lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "")

            detalle = (e.get("detalle", "") or "").strip()
            series = e.get("series", "")
            peso = e.get("peso", "")
            reps_min = e.get("reps_min") or e.get("RepsMin", "")
            reps_max = e.get("reps_max") or e.get("RepsMax", "")
            repeticiones = e.get("repeticiones", "")
            rir = e.get("rir", "")
            tiempo = e.get("tiempo", "")

            if reps_min != "" and reps_max != "":
                rep_str = f"{series}x {reps_min} a {reps_max}"
            elif reps_min != "":
                rep_str = f"{series}x{reps_min}+"
            elif reps_max != "":
                rep_str = f"{series}x≤{reps_max}"
            elif repeticiones:
                rep_str = f"{series}x{repeticiones}"
            else:
                rep_str = f"{series}x"

            peso_str = f"{peso}kg" if peso else ""
            tiempo_str = f"{tiempo} seg" if tiempo else ""
            rir_str = f"RIR {rir}" if rir else ""

            info_partes = [rep_str]
            if peso_str: info_partes.append(peso_str)
            if tiempo_str: info_partes.append(tiempo_str)
            if rir_str: info_partes.append(rir_str)
            info_str = " · ".join(info_partes)

            nombre_mostrar = ejercicio_nombre
            if detalle:
                nombre_mostrar += f" — {detalle}"

            video_url = (e.get("video", "") or "").strip()
            video_btn_key = f"video_btn_{circuito}_{idx}"
            mostrar_video_key = f"mostrar_video_{circuito}_{idx}"

            if video_url:
                boton_presionado = st.button(f"{nombre_mostrar} 🎥 — {info_str}", key=video_btn_key, help="Haz clic para ver video")
                if boton_presionado:
                    st.session_state[mostrar_video_key] = not st.session_state.get(mostrar_video_key, False)
                if st.session_state.get(mostrar_video_key, False):
                    if "youtube.com/shorts/" in video_url:
                        try:
                            video_id = video_url.split("shorts/")[1].split("?")[0]
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                        except:
                            pass
                    st.video(video_url)
            else:
                st.markdown(f"**{nombre_mostrar} — {info_str}**")

            # ===== NUEVO: checkbox por ejercicio "Sesión anterior"
            ver_prev = False
            if can_show_per_exercise_toggles:
                ver_prev = st.checkbox(
                    "📅 Sesión anterior",
                    key=f"chk_prev_{ejercicio_id}",
                    help="Muestra un resumen con Rep/Peso/RIR de la semana anterior si existe."
                )

            if ver_prev:
                ex_prev = _prev_para(e) if ejercicios_prev_map else None
                if ex_prev:
                    peso_alc, reps_alc, rir_alc = _parsear_series(ex_prev.get("series_data", []))
                    peso_prev = peso_alc if peso_alc is not None else ex_prev.get("peso_alcanzado", "")
                    reps_prev = reps_alc if reps_alc is not None else ex_prev.get("reps_alcanzadas", "")
                    rir_prev  = rir_alc  if rir_alc  is not None else ex_prev.get("rir_alcanzado", "")

                    info_prev = []
                    if reps_prev not in ("", None): info_prev.append(f"Reps: {reps_prev}")
                    if peso_prev not in ("", None): info_prev.append(f"Peso: {peso_prev}")
                    if rir_prev  not in ("", None): info_prev.append(f"RIR: {rir_prev}")

                    st.caption("Sesión anterior → " + (" | ".join(info_prev) if info_prev else "sin datos guardados."))
                else:
                    st.caption("Sesión anterior → sin coincidencias para este ejercicio.")

        # ===== Panel Reporte por circuito =====
        if f"mostrar_reporte_{circuito}" not in st.session_state:
            st.session_state[f"mostrar_reporte_{circuito}"] = False

        if st.button(f"📝 Reporte {circuito}", key=f"btn_reporte_{circuito}"):
            st.session_state[f"mostrar_reporte_{circuito}"] = not st.session_state[f"mostrar_reporte_{circuito}"]

        if st.session_state[f"mostrar_reporte_{circuito}"]:
            st.markdown(f"### 📋 Registro del circuito {circuito}")

            for idx, e in enumerate(lista):
                ejercicio_nombre = e.get("ejercicio", f"Ejercicio {idx+1}")
                ejercicio_id = f"{circuito}_{ejercicio_nombre}_{idx}".lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "")
                st.markdown(f"#### {ejercicio_nombre}")

                # ===== Inicializar/ajustar series_data SIEMPRE (aunque no abran inputs) =====
                try:
                    num_series = int(e.get("series", 0))
                except:
                    num_series = 0

                reps_def, peso_def, rir_def = defaults_de_ejercicio(e)
                if "series_data" not in e or not isinstance(e["series_data"], list) or len(e["series_data"]) != num_series:
                    e["series_data"] = [{"reps": reps_def, "peso": peso_def, "rir": rir_def} for _ in range(num_series)]
                else:
                    for s in e["series_data"]:
                        if not str(s.get("reps", "")).strip():
                            s["reps"] = reps_def
                        if not str(s.get("peso", "")).strip():
                            s["peso"] = peso_def
                        if not str(s.get("rir", "")).strip():
                            s["rir"] = rir_def

                # ===== Render inputs por serie =====
                for s_idx in range(num_series):
                    st.markdown(f"**Serie {s_idx + 1}**")
                    s_cols = st.columns(3)

                    e["series_data"][s_idx]["reps"] = s_cols[0].text_input(
                        "Reps", value=e["series_data"][s_idx].get("reps", ""),
                        placeholder="Reps", key=f"rep_{ejercicio_id}_{s_idx}", label_visibility="collapsed"
                    )

                    e["series_data"][s_idx]["peso"] = s_cols[1].text_input(
                        "Peso", value=e["series_data"][s_idx].get("peso", ""),
                        placeholder="Kg", key=f"peso_{ejercicio_id}_{s_idx}", label_visibility="collapsed"
                    )

                    e["series_data"][s_idx]["rir"] = s_cols[2].text_input(
                        "RIR", value=e["series_data"][s_idx].get("rir", ""),
                        placeholder="RIR", key=f"rir_{ejercicio_id}_{s_idx}", label_visibility="collapsed"
                    )

                # ===== Comentario general =====
                e["comentario"] = st.text_input(
                    "Comentario general", value=e.get("comentario", ""),
                    placeholder="Comentario", key=f"coment_{ejercicio_id}"
                )

                # ===== Botón GUARDAR SOLO ESTE REPORTE =====
                btn_guardar_key = f"guardar_reporte_{ejercicio_id}"
                if st.button("💾 Guardar este reporte", key=btn_guardar_key):
                    with st.spinner("Guardando reporte del ejercicio..."):
                        # 1) métricas alcanzadas a partir de series_data
                        peso_alc, reps_alc, rir_alc = _parsear_series(e.get("series_data", []))
                        if peso_alc is not None: e["peso_alcanzado"] = peso_alc
                        if reps_alc is not None: e["reps_alcanzadas"] = reps_alc
                        if rir_alc  is not None: e["rir_alcanzado"]  = rir_alc

                        # 2) responsable si hay datos
                        hay_input = any([
                            (e.get("comentario", "") or "").strip(),
                            peso_alc is not None,
                            reps_alc is not None,
                            rir_alc  is not None
                        ])
                        if hay_input:
                            e["coach_responsable"] = correo_raw

                        if "bloque" not in e:
                            e["bloque"] = e.get("seccion", "")

                        ok = guardar_reporte_ejercicio(
                            db=db,
                            correo_cliente_norm=correo_cliente_norm,
                            semana_sel=semana_sel,
                            dia_sel=str(dia_sel),
                            ejercicio_editado=e,
                        )

                        if ok:
                            st.success("✅ Reporte guardado.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("❌ No se pudo guardar el reporte.")

    # ===== RPE de la sesión =====
    rpe_key = f"rpe_sesion_{semana_sel}_{dia_sel}"
    valor_rpe_inicial = rutina_doc["rutina"].get(str(dia_sel) + "_rpe", "")

    st.markdown("### 📌 RPE de la sesión")
    rpe_valor = st.number_input(
        "RPE percibido del día (0-10)", min_value=0.0, max_value=10.0, step=0.5,
        value=float(valor_rpe_inicial) if valor_rpe_inicial != "" else 0.0,
        key=rpe_key
    )
    st.markdown("---")

    # ===== Botón global (opcional, lo mantengo) =====
    if st.button("💾 Guardar cambios del día", key=f"guardar_{dia_sel}_{semana_sel}"):
        with st.spinner("Guardando..."):
            fecha_norm = semana_sel.replace("-", "_")
            doc_id = f"{correo_cliente_norm}_{fecha_norm}"
            try:
                # Upsert del día actual completo (ejercicios editados y RPE)
                doc_ref_final = db.collection("rutinas_semanales").document(doc_id)
                doc_ref_final.set({"rutina": {str(dia_sel): ejercicios, f"{str(dia_sel)}_rpe": rpe_valor}}, merge=True)

                st.cache_data.clear()
                if rol.strip().lower() == "deportista":
                    st.success(f"✅ Cambios guardados, {nombre}. ¡Buen entrenamiento! 💪")
                else:
                    st.success(f"✅ Cambios guardados para {rutina_doc.get('cliente','')}.")
                st.rerun()
            except Exception as e:
                st.error("❌ Error durante el guardado.")
                st.exception(e)

# Ejecutar la vista (si este archivo se usa como página)
if __name__ == "__main__":
    ver_rutinas()
