import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import json
from herramientas import actualizar_progresiones_individual
from soft_login_bar import require_login, require_role  # <-- NUEVO

def obtener_lista_ejercicios(data_dia):
    if isinstance(data_dia, dict):
        return list(data_dia.values())
    elif isinstance(data_dia, list):
        return data_dia
    else:
        return []
def _as_str(v):
    return "" if v is None else str(v)

def _to_int_or_empty(v):
    try:
        return int(v)
    except Exception:
        return ""

def _sanitize_ejercicio(item):
    """Convierte cualquier variante a nuestro esquema v2 (dict limpio y seguro)."""
    if not isinstance(item, dict):
        return None

    circuito = _as_str(item.get("circuito", item.get("Circuito", ""))).strip().upper()
    bloque   = item.get("bloque") or item.get("seccion")
    if not bloque:
        bloque = "Warm Up" if circuito in ["A","B","C"] else "Work Out"

    ej = {
        "bloque": bloque,
        "circuito": circuito,
        "ejercicio": _as_str(item.get("ejercicio", item.get("Ejercicio",""))).strip(),
        "detalle": _as_str(item.get("detalle", item.get("Detalle",""))).strip(),
        "series": _as_str(item.get("series", item.get("Series",""))).strip(),
        "reps_min": _to_int_or_empty(item.get("reps_min", item.get("RepsMin",""))),
        "reps_max": _to_int_or_empty(item.get("reps_max", item.get("RepsMax",""))),
        "peso": item.get("peso", item.get("Peso","")),
        "tiempo": _as_str(item.get("tiempo", item.get("Tiempo",""))).strip(),
        "velocidad": _as_str(item.get("velocidad", item.get("Velocidad",""))).strip(),
        "rir": _as_str(item.get("rir", item.get("RIR",""))).strip(),
        "tipo": _as_str(item.get("tipo", item.get("Tipo",""))).strip(),
        "video": _as_str(item.get("video", item.get("Video",""))).strip(),
        "comentario": _as_str(item.get("comentario","")),
    }

    sd = item.get("series_data", [])
    if not isinstance(sd, list):
        sd = []
    fixed_sd = []
    for s in sd:
        if isinstance(s, dict):
            fixed_sd.append({
                "reps": _as_str(s.get("reps","")),
                "peso": _as_str(s.get("peso","")),
                "rir":  _as_str(s.get("rir","")),
            })
    ej["series_data"] = fixed_sd

    for k in ["peso_alcanzado", "reps_alcanzadas", "rir_alcanzado", "coach_responsable"]:
        if k in item:
            ej[k] = item[k]

    return ej

def _sanitize_lista(raw):
    """Acepta list o dict y devuelve SIEMPRE lista de ejercicios v2."""
    if isinstance(raw, dict):
        iterable = raw.values()
    elif isinstance(raw, list):
        iterable = raw
    else:
        iterable = []
    out = []
    for it in iterable:
        ej = _sanitize_ejercicio(it)
        if ej and ej.get("ejercicio","").strip():
            out.append(ej)
    return out

def _strip_ui_keys(e):
    """Elimina llaves de UI y deja sólo las del contrato v2."""
    keep = {
        "bloque","circuito","ejercicio","detalle","series",
        "reps_min","reps_max","peso","tiempo","velocidad","rir",
        "tipo","video","series_data","comentario",
        "peso_alcanzado","reps_alcanzadas","rir_alcanzado","coach_responsable"
    }
    return {k: v for k, v in e.items() if k in keep}


def _to_int_or_empty(v):
    try:
        return int(v)
    except Exception:
        return ""

def _as_str(v):
    return "" if v is None else str(v)

def _sanitize_ejercicio(item):
    """Convierte cualquier variante a nuestro esquema v2 (dict limpio y seguro)."""
    if not isinstance(item, dict):
        return None

    # Detecta bloque si faltara (fall back por circuito: A-C warm, D-L work)
    circuito = _as_str(item.get("circuito", item.get("Circuito", ""))).strip().upper()
    bloque   = item.get("bloque") or item.get("seccion")
    if not bloque:
        try:
            bloque = "Warm Up" if circuito in ["A", "B", "C"] else "Work Out"
        except Exception:
            bloque = "Work Out"

    ej = {
        "bloque": bloque,
        "circuito": circuito,
        "ejercicio": _as_str(item.get("ejercicio", item.get("Ejercicio", ""))).strip(),
        "detalle": _as_str(item.get("detalle", item.get("Detalle",""))).strip(),
        "series": _as_str(item.get("series", item.get("Series",""))).strip(),
        "reps_min": _to_int_or_empty(item.get("reps_min", item.get("RepsMin",""))),
        "reps_max": _to_int_or_empty(item.get("reps_max", item.get("RepsMax",""))),
        "peso": item.get("peso", item.get("Peso","")),
        "tiempo": _as_str(item.get("tiempo", item.get("Tiempo",""))).strip(),
        "velocidad": _as_str(item.get("velocidad", item.get("Velocidad",""))).strip(),
        "rir": _as_str(item.get("rir", item.get("RIR",""))).strip(),
        "tipo": _as_str(item.get("tipo", item.get("Tipo",""))).strip(),
        "video": _as_str(item.get("video", item.get("Video",""))).strip(),
        "comentario": _as_str(item.get("comentario","")),
    }

    # series_data debe ser lista de dicts con keys fijas
    sd = item.get("series_data", [])
    if not isinstance(sd, list):
        sd = []
    fixed_sd = []
    for s in sd:
        if isinstance(s, dict):
            fixed_sd.append({
                "reps": _as_str(s.get("reps","")),
                "peso": _as_str(s.get("peso","")),
                "rir":  _as_str(s.get("rir","")),
            })
    ej["series_data"] = fixed_sd

    # Métricas opcionales (si venían):
    for k in ["peso_alcanzado", "reps_alcanzadas", "rir_alcanzado", "coach_responsable"]:
        if k in item:
            ej[k] = item[k]

    return ej

def _sanitize_lista(raw):
    """Acepta list o dict y devuelve SIEMPRE lista de ejercicios v2."""
    if isinstance(raw, dict):
        iterable = raw.values()
    elif isinstance(raw, list):
        iterable = raw
    else:
        iterable = []
    out = []
    for it in iterable:
        ej = _sanitize_ejercicio(it)
        if ej and ej.get("ejercicio","").strip():
            out.append(ej)
    return out

def _ordenar_circuito(e):
    orden = {c: i+1 for i, c in enumerate(list("ABCDEFGHIJKL"))}
    return orden.get(e.get("circuito",""), 999)

def ver_rutinas():
    # === INICIALIZAR FIREBASE SOLO UNA VEZ solo una===
    if not firebase_admin._apps:
        cred_dict = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)

    db = firestore.client()

    # ---- Soft login: exige que haya sesión ----
    require_login()  # <-- NUEVO (bloquea si no hay st.session_state.correo)

    def normalizar_correo(correo):
        return correo.strip().lower().replace("@", "_").replace(".", "_")

    def obtener_fecha_lunes():
        hoy = datetime.now()
        lunes = hoy - timedelta(days=hoy.weekday())
        return lunes.strftime("%Y-%m-%d")

    def es_entrenador(rol):
        return rol.lower() in ["entrenador", "admin", "administrador"]

    def ordenar_circuito(ejercicio):
        orden = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7}
        return orden.get(ejercicio.get("circuito", ""), 99)

    @st.cache_data
    def cargar_rutinas_filtradas(correo, rol):
        if es_entrenador(rol):
            docs = db.collection("rutinas_semanales").stream()
        else:
            docs = db.collection("rutinas_semanales").where("correo", "==", correo).stream()
        return [doc.to_dict() for doc in docs]

    correo_raw = st.session_state.get("correo", "").strip().lower()
    if not correo_raw:
        st.error("❌ No hay correo registrado. Por favor vuelve a iniciar sesión.")
        st.stop()

    correo_norm = normalizar_correo(correo_raw)

    # ---------- Bloque ajustado para soft login ----------
    doc_user = db.collection("usuarios").document(correo_norm).get()
    if doc_user.exists:
        datos_usuario = doc_user.to_dict()
        nombre_doc = datos_usuario.get("nombre", "")
        rol_doc = (datos_usuario.get("rol", "") or "").lower()
    else:
        nombre_doc = ""   # <-- NUEVO: no frenamos si no existe el doc
        rol_doc = ""      # <-- NUEVO

    # Rol y nombre finales desde soft login (con fallback al doc si existía)
    nombre = nombre_doc or st.session_state.get("correo", "Usuario")
    rol = (st.session_state.get("rol") or rol_doc or "deportista").lower()
    # -----------------------------------------------------

    cols = st.columns([5, 1])
    with cols[1]:
        if st.button("🔄"):
            st.cache_data.clear()

    if st.checkbox("👤 Mostrar información personal", value=True):
        st.success(f"Bienvenido {nombre} ({rol})")

    rutinas = cargar_rutinas_filtradas(correo_raw, rol)
    if not rutinas:
        st.warning("⚠️ No se encontraron rutinas.")
        st.stop()

    if es_entrenador(rol):
        clientes = sorted(set(r["cliente"] for r in rutinas if "cliente" in r))
        cliente_input = st.text_input("👤 Escribe el nombre del cliente:", key="cliente_input")
        cliente_opciones = [c for c in clientes if cliente_input.lower() in c.lower()]
        cliente_sel = st.selectbox("Selecciona cliente:", cliente_opciones if cliente_opciones else clientes, key="cliente_sel")
        rutinas_cliente = [r for r in rutinas if r.get("cliente") == cliente_sel]
    else:
        rutinas_cliente = rutinas

    # ✅ Obtener correo real del cliente seleccionado
    correo_cliente = rutinas_cliente[0].get("correo", "")
    correo_cliente_norm = normalizar_correo(correo_cliente)

    semanas = sorted({r["fecha_lunes"] for r in rutinas_cliente}, reverse=True)
    semana_actual = obtener_fecha_lunes()
    semana_sel = st.selectbox("📆 Semana", semanas, index=semanas.index(semana_actual) if semana_actual in semanas else 0, key="semana_sel")

    rutina_doc = next((r for r in rutinas_cliente if r["fecha_lunes"] == semana_sel), None)
    if not rutina_doc:
        st.warning("⚠️ No hay rutina para esa semana.")
        st.stop()
    # === Mostrar bloque de rutina (si existe)
    bloque_id = rutina_doc.get("bloque_rutina")

    if bloque_id:
        # Buscar todas las semanas con este bloque para este cliente
        bloques_mismo_cliente = [
            r for r in rutinas_cliente if r.get("bloque_rutina") == bloque_id
        ]
        fechas_bloque = sorted([r["fecha_lunes"] for r in bloques_mismo_cliente])
        
        try:
            semana_actual_idx = fechas_bloque.index(semana_sel) + 1
            total_semanas_bloque = len(fechas_bloque)
            st.markdown(f"📦 <b>Bloque de rutina:</b> Semana {semana_actual_idx} de {total_semanas_bloque}", unsafe_allow_html=True)
        except ValueError:
            st.info("ℹ️ Semana no encontrada en bloque de rutina.")
    else:
        st.warning("⚠️ Esta rutina no tiene un identificador de bloque.")

    dias_disponibles = sorted(
        [k for k in rutina_doc["rutina"].keys() if k.isdigit()],
        key=int
    )

    dia_sel = st.selectbox("📅 Día", dias_disponibles, key="dia_sel")
    ejercicios = _sanitize_lista(rutina_doc["rutina"].get(str(dia_sel), []))
    ejercicios.sort(key=_ordenar_circuito)

    st.markdown(f"### Ejercicios del día {dia_sel}")
    
    st.markdown("""
        <style>
        .compact-input input { font-size: 12px !important; width: 100px !important; }
        .linea-blanca { border-bottom: 2px solid white; margin: 15px 0; }
        .ejercicio { font-size: 18px !important; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    ejercicios_por_circuito = {}
    for e in ejercicios:
        circuito = e.get("circuito", "Z").upper()
        ejercicios_por_circuito.setdefault(circuito, []).append(e)

    for circuito, lista in sorted(ejercicios_por_circuito.items()):
        if circuito == "A":
            st.subheader("Warm-Up")
        elif circuito == "D":
            st.subheader("Workout")

        st.markdown(f"### Circuito {circuito}")
        st.markdown("<div class='bloque'>", unsafe_allow_html=True)

        for idx, e in enumerate(lista):
            ejercicio = e.get("ejercicio", f"Ejercicio {idx+1}")
            ejercicio_id = f"{circuito}_{ejercicio}_{idx}".lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "")
            # === Obtener información del ejercicio ===
            ejercicio = e.get("ejercicio", f"Ejercicio {idx+1}")
            detalle = e.get("detalle", "").strip()
            series = e.get("series", "")
            peso = e.get("peso", "")
            reps_min = e.get("reps_min") or e.get("RepsMin", "")
            reps_max = e.get("reps_max") or e.get("RepsMax", "")
            repeticiones = e.get("repeticiones", "")
            rir = e.get("rir", "")
            tiempo = e.get("tiempo", "")

            # === Construir string de repeticiones
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

            # === Mostrar nombre + detalle si existe
            nombre_mostrar = ejercicio
            if detalle:
                nombre_mostrar += f" — {detalle}"

            # === Mostrar como botón solo si tiene video
            video_url = e.get("video", "").strip()
            video_btn_key = f"video_btn_{circuito}_{idx}"
            mostrar_video_key = f"mostrar_video_{circuito}_{idx}"

            if video_url:
                boton_presionado = st.button(
                    f"{nombre_mostrar} 🎥 — {info_str}",
                    key=video_btn_key,
                    help="Haz clic para ver video"
                )

                if boton_presionado:
                    st.session_state[mostrar_video_key] = not st.session_state.get(mostrar_video_key, False)

                # Mostrar video si fue activado
                if st.session_state.get(mostrar_video_key, False):
                    if "youtube.com/shorts/" in video_url:
                        try:
                            video_id = video_url.split("shorts/")[1].split("?")[0]
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                        except:
                            pass
                    st.video(video_url)
            else:
                # Sin video ➜ solo texto
                st.markdown(f"**{nombre_mostrar} — {info_str}**")

            # === Verificar si hay datos de la sesión anterior antes de mostrar el botón
            hay_sesion_anterior = False
            match_ant = None

            try:
                idx_semana_actual = semanas.index(semana_sel)
                if idx_semana_actual + 1 < len(semanas):
                    semana_ant = semanas[idx_semana_actual + 1]
                    doc_ant = next((r for r in rutinas_cliente if r["fecha_lunes"] == semana_ant), None)

                    if doc_ant:
                        rutina_ant = doc_ant.get("rutina", {})
                        ejercicios_ant = rutina_ant.get(str(dia_sel), [])

                        nombre_actual = e.get("ejercicio", "").strip().lower()
                        circuito_actual = e.get("circuito", "").strip().lower()

                        match_ant = next(
                            (
                                ex for ex in ejercicios_ant
                                if ex.get("ejercicio", "").strip().lower() == nombre_actual and
                                ex.get("circuito", "").strip().lower() == circuito_actual
                            ),
                            None
                        )

                        if match_ant:
                            hay_sesion_anterior = True
            except Exception as err:
                st.warning(f"⚠️ Error buscando sesión anterior: {err}")

            # === Mostrar el botón solo si hay sesión anterior
            if hay_sesion_anterior:
                ver_sesion_ant = st.checkbox("📂 Sesión anterior", key=f"prev_{ejercicio_id}")

                if ver_sesion_ant:
                    series_ant = match_ant.get("series_data", [])

                    if match_ant and isinstance(series_ant, list) and len(series_ant) > 0:
                        st.markdown("📌 <b>Datos de la sesión anterior:</b>", unsafe_allow_html=True)
                        for s_idx, serie_ant in enumerate(series_ant):
                            reps = serie_ant.get("reps", "-") or "-"
                            peso = serie_ant.get("peso", "-") or "-"
                            rir = serie_ant.get("rir", "-") or "-"
                            st.markdown(
                                f"<div style='font-size:16px; padding-left:10px;'>"
                                f"<b>Serie {s_idx+1}:</b> {reps} reps · {peso} kg · RIR {rir if rir != '' else '-'}</div>",
                                unsafe_allow_html=True
                            )
                    else:
                        st.info("ℹ️ No hay datos registrados de la sesión anterior para este ejercicio.")
        
        # === Mostrar reporte por circuito ===
        if f"mostrar_reporte_{circuito}" not in st.session_state:
            st.session_state[f"mostrar_reporte_{circuito}"] = False

        if st.button(f"📝 Reporte {circuito}", key=f"btn_reporte_{circuito}"):
            st.session_state[f"mostrar_reporte_{circuito}"] = not st.session_state[f"mostrar_reporte_{circuito}"]

        if st.session_state[f"mostrar_reporte_{circuito}"]:
            st.markdown(f"### 📋 Registro del circuito {circuito}")

            for idx, e in enumerate(lista):
                ejercicio = e.get("ejercicio", f"Ejercicio {idx+1}")
                ejercicio_id = f"{circuito}_{ejercicio}_{idx}".lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "")
                st.markdown(f"#### {ejercicio}")

                try:
                    num_series = int(e.get("series", 0))
                except:
                    num_series = 0

                if "series_data" not in e or not isinstance(e["series_data"], list) or len(e["series_data"]) != num_series:
                    e["series_data"] = [{"reps": "", "peso": "", "rir": ""} for _ in range(num_series)]

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

                e["comentario"] = st.text_input(
                    "Comentario general", value=e.get("comentario", ""),
                    placeholder="Comentario", key=f"coment_{ejercicio_id}"
                )

    # === RPE DE LA SESIÓN ===
    rpe_key = f"rpe_sesion_{semana_sel}_{dia_sel}"
    valor_rpe_inicial = rutina_doc["rutina"].get(dia_sel + "_rpe", "")

    st.markdown("### 📌 RPE de la sesión")
    rpe_valor = st.number_input(
    "RPE percibido del día (0-10)", min_value=0.0, max_value=10.0, step=0.5,
    value=float(valor_rpe_inicial) if valor_rpe_inicial != "" else 0.0,
    key=rpe_key
)
    st.markdown("---")
    
    # ✅ GUARDAR CAMBIOS (reemplaza este bloque completo)
    if st.button("💾 Guardar cambios del día", key=f"guardar_{dia_sel}_{semana_sel}"):
        with st.spinner("Guardando..."):
            fecha_norm = semana_sel.replace("-", "_")
            doc_id = f"{correo_cliente_norm}_{fecha_norm}"

            try:
                semanas_futuras = sorted([s for s in semanas if s > semana_sel])

                for idx, e in enumerate(ejercicios):
                    # --- Parseo de series_data para métricas alcanzadas ---
                    series_data = e.get("series_data", [])
                    pesos, reps, rirs = [], [], []

                    for s_idx, s in enumerate(series_data):
                        peso_raw = _as_str(s.get("peso", "")).strip()
                        reps_raw = _as_str(s.get("reps", "")).strip()
                        rir_raw  = _as_str(s.get("rir", "")).strip()

                        try:
                            val = peso_raw.replace(",", ".").replace("kg", "").strip()
                            if val != "":
                                pesos.append(float(val))
                        except:
                            pass
                        try:
                            if reps_raw.isdigit():
                                reps.append(int(reps_raw))
                        except:
                            pass
                        try:
                            val = rir_raw.replace(",", ".")
                            if val != "":
                                rirs.append(float(val))
                        except:
                            pass

                    peso_alcanzado  = max(pesos) if pesos else None
                    reps_alcanzadas = max(reps)  if reps  else None
                    rir_alcanzado   = min(rirs)  if rirs  else None

                    if peso_alcanzado is not None: e["peso_alcanzado"] = peso_alcanzado
                    if reps_alcanzadas is not None: e["reps_alcanzadas"] = reps_alcanzadas
                    if rir_alcanzado is not None:   e["rir_alcanzado"]  = rir_alcanzado

                    comentario = _as_str(e.get("comentario", "")).strip()
                    hay_input = bool(pesos or reps or rirs or comentario)
                    if hay_input:
                        e["coach_responsable"] = correo_raw

                    # Si no hay peso alcanzado, no propagamos delta (pero sí guardaremos el día actual más abajo)
                    if peso_alcanzado is None:
                        continue

                    # === Actualiza progresión individual ===
                    actualizar_progresiones_individual(
                        nombre=rutina_doc.get("cliente", ""),
                        correo=correo_cliente,
                        ejercicio=e["ejercicio"],
                        circuito=e.get("circuito", ""),
                        bloque=e.get("bloque", e.get("seccion", "")),
                        fecha_actual_lunes=semana_sel,
                        dia_numero=int(dia_sel),
                        peso_alcanzado=peso_alcanzado
                    )

                    # === Propaga delta de peso a semanas futuras ===
                    try:
                        peso_actual = float(_as_str(e.get("peso", 0)).replace(",", "."))
                    except Exception:
                        peso_actual = 0.0
                    delta = peso_alcanzado - peso_actual
                    if delta == 0:
                        continue

                    nombre_ejercicio = e["ejercicio"]
                    circuito = e.get("circuito", "")
                    bloque   = e.get("bloque", e.get("seccion", ""))

                    for s in semanas_futuras:
                        fecha_norm_fut = s.replace("-", "_")
                        doc_id_fut = f"{correo_cliente_norm}_{fecha_norm_fut}"
                        doc_ref = db.collection("rutinas_semanales").document(doc_id_fut)
                        doc = doc_ref.get()
                        if not doc.exists:
                            continue

                        rutina_fut = doc.to_dict().get("rutina", {})
                        # 🔧 **AQUÍ** saneamos SIEMPRE ANTES DE USAR
                        ejercicios_fut = _sanitize_lista(rutina_fut.get(str(dia_sel), []))

                        changed = False
                        for j, ef in enumerate(ejercicios_fut):
                            mismo_ejercicio = (ef.get("ejercicio", "") == nombre_ejercicio)
                            mismo_circuito  = (ef.get("circuito", "")  == circuito)
                            mismo_bloque    = (ef.get("bloque", ef.get("seccion", "")) == bloque)

                            if mismo_ejercicio and mismo_circuito and mismo_bloque:
                                try:
                                    base = ef.get("peso", 0)
                                    base = 0 if base == "" else float(_as_str(base).replace(",", "."))
                                except Exception:
                                    base = 0.0
                                ef["peso"] = round(base + float(delta), 2)
                                ejercicios_fut[j] = ef
                                changed = True

                        if changed:
                            # Guardar el día como lista uniforme y saneada
                            doc_ref.update({f"rutina.{str(dia_sel)}": [_strip_ui_keys(x) for x in ejercicios_fut]})

                # ✅ Actualiza documento actual (día seleccionado)
                doc_ref_final = db.collection("rutinas_semanales").document(doc_id)
                doc_final = doc_ref_final.get()

                if doc_final.exists:
                    doc_ref_final.update({
                        f"rutina.{str(dia_sel)}": [_strip_ui_keys(x) for x in ejercicios],
                        f"rutina.{str(dia_sel)}_rpe": rpe_valor
                    })
                    if rol.strip().lower() == "deportista":
                        st.success(f"✅ Cambios guardados, {nombre}. ¡Buen entrenamiento! 💪")
                    else:
                        st.success(f"✅ Cambios guardados para {rutina_doc.get('cliente','')}.")
                else:
                    st.warning("⚠️ No se encontró el documento. No se guardaron los cambios.")

            except Exception as e:
                st.error("❌ Error durante el guardado.")
                st.exception(e)
