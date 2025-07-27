import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from herramientas import aplicar_progresion
from guardar_rutina_view import guardar_rutina, aplicar_progresion_rango
import json
import pandas as pd
import matplotlib.pyplot as plt

import unicodedata

def normalizar_texto(texto):
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    return texto


# === INICIALIZAR FIREBASE SOLO UNA VEZ ===
if not firebase_admin._apps:
    cred_dict = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Solo una vez, al inicio del archivo (después de cargar Firebase)
@st.cache_data(show_spinner=False)
def cargar_ejercicios():
    docs = db.collection("ejercicios").stream()
    return {doc.to_dict().get("nombre", ""): doc.to_dict() for doc in docs if doc.exists}

ejercicios_dict = cargar_ejercicios()

# === Cargar usuarios ===
@st.cache_data(show_spinner=False)
def cargar_usuarios():
    docs = db.collection("usuarios").stream()
    return [doc.to_dict() for doc in docs if doc.exists]

def crear_rutinas():
    st.title("Crear nueva rutina")


    usuarios = cargar_usuarios()

    nombres = sorted(set(u.get("nombre", "") for u in usuarios))

    nombre_input = st.text_input("Escribe el nombre del cliente:")
    coincidencias = [n for n in nombres if nombre_input.lower() in n.lower()]
    nombre_sel = st.selectbox("Selecciona de la lista:", coincidencias) if coincidencias else ""

    correo_auto = next((u.get("correo", "") for u in usuarios if u.get("nombre") == nombre_sel), "")
    correo = st.text_input("Correo del cliente:", value=correo_auto)

    fecha_inicio = st.date_input("Fecha de inicio de rutina:", value=datetime.today())
    semanas = st.number_input("Semanas de duración:", min_value=1, max_value=12, value=4)
    entrenador = st.text_input("Nombre del entrenador responsable:")

    st.markdown("---")
    st.subheader("Días de entrenamiento")

    dias = ["Día 1", "Día 2", "Día 3", "Día 4", "Día 5"]
    tabs = st.tabs(dias)

    columnas_tabla = [
        "Circuito", "Sección", "Ejercicio", "Series", "Repeticiones",
        "Peso", "Tiempo", "Velocidad", "RIR", "Tipo", "Video"
    ]

    progresion_activa = st.radio(
        "Progresión activa", ["Progresión 1", "Progresión 2", "Progresión 3"],
        horizontal=True, index=0
    )

    for i, tab in enumerate(tabs):
        with tab:
            with st.expander(f"Ejercicios para {dias[i]}", expanded=(i == 0)):
                dia_key = f"rutina_dia_{i + 1}"

                if dia_key not in st.session_state:
                    st.session_state[dia_key] = [{k: "" for k in columnas_tabla} for _ in range(2)]
                # 👇 aquí va todo el contenido restante de ese día

            
            for seccion in ["Warm Up", "Work Out"]:
                st.subheader(f"{seccion}" if seccion == "Warm Up" else f"{seccion}")
                # === Botón para agregar fila en la sección correspondiente
                key_seccion = f"{dia_key}_{seccion.replace(' ', '_')}"

                if st.button(f"➕ Agregar fila a {seccion} ({dias[i]})", key=f"add_row_{i}_{seccion}"):
                    nueva_fila = {k: "" for k in columnas_tabla}
                    nueva_fila["Sección"] = seccion

                    if key_seccion not in st.session_state:
                        st.session_state[key_seccion] = []

                    st.session_state[key_seccion].append(nueva_fila)

                if key_seccion not in st.session_state:
                    st.session_state[key_seccion] = [{k: "" for k in columnas_tabla} for _ in range(6)]
                    for f in st.session_state[key_seccion]:
                        f["Sección"] = seccion

                for idx, fila in enumerate(st.session_state[key_seccion]):
                    # ✅ Título + checkbox a la derecha
                    cols_titulo = st.columns([9, 1, 1])
                    with cols_titulo[0]:
                        st.markdown(f"#### Ejercicio {idx + 1} - {fila.get('Ejercicio', '')}")
                   # with cols_titulo[1]:
                        #st.markdown("<div style='text-align: right; padding-top: 6px;'>Progresiones</div>", unsafe_allow_html=True)
                   # with cols_titulo[2]:
                        #mostrar_progresion = st.checkbox(" ", key=f"mostrar_prog_{i}_{seccion}_{idx}", label_visibility="collapsed")
 
                    # === Inputs principales ===
                    if seccion == "Work Out":
                        cols = st.columns([1, 3.5, 5, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2])
                    else:
                        cols = st.columns([1, 9, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2])

                    # ✅ Clave única segura para evitar conflicto
                    key_entrenamiento = f"{i}_{seccion.replace(' ', '_')}_{idx}"
                    
                    fila["Circuito"] = cols[0].selectbox(
                        "", ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
                        index=["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"].index(fila["Circuito"]) if fila["Circuito"] else 0,
                        key=f"circ_{key_entrenamiento}", label_visibility="collapsed"
                    )

                    # === Solo aplicar buscador si es Work Out ===
                    if seccion == "Work Out":
                        palabra_busqueda = cols[1].text_input(
                            "Buscar ejercicio", value=fila.get("BuscarEjercicio", ""),
                            key=f"buscar_{key_entrenamiento}",
                            label_visibility="collapsed",
                            placeholder="Palabra clave"
                        )
                        fila["BuscarEjercicio"] = palabra_busqueda

                        ejercicios_encontrados = []
                        try:
                            if palabra_busqueda.strip():
                                palabras_clave = palabra_busqueda.lower().strip().split()

                                ejercicios_encontrados = [
                                    nombre
                                    for nombre in ejercicios_dict.keys()
                                    if all(palabra in nombre.lower() for palabra in palabras_clave)
                                ]
                            else:
                                ejercicios_encontrados = []
                        except Exception as e:
                            st.warning(f"Error al buscar ejercicios: {e}")
                            ejercicios_encontrados = []

                        seleccionado = cols[2].selectbox(
                            "Coincidencias", ejercicios_encontrados if ejercicios_encontrados else ["(sin resultados)"],
                            key=f"selectbox_{key_entrenamiento}", label_visibility="collapsed"
                        )

                        if seleccionado != "(sin resultados)":
                            fila["Ejercicio"] = seleccionado

                            # ✅ Si el ejercicio tiene link de video en Firestore y aún no hay uno manual, lo asignamos automáticamente
                            if not fila.get("Video"):
                                video_auto = ejercicios_dict.get(seleccionado, {}).get("video", "").strip()
                                if video_auto:
                                    fila["Video"] = video_auto
                        else:
                            fila["Ejercicio"] = fila.get("Ejercicio", "")


                        fila["Ejercicio"] = seleccionado if seleccionado != "(sin resultados)" else fila.get("Ejercicio", "")
                    else:
                        fila["Ejercicio"] = cols[1].text_input(
                            "Ejercicio", value=fila["Ejercicio"],
                            key=f"ej_{key_entrenamiento}", label_visibility="collapsed", placeholder="Ejercicio"
                        )



                    fila["Series"] = cols[3].text_input(
                        "", value=fila["Series"],
                        key=f"ser_{key_entrenamiento}", label_visibility="collapsed", placeholder="Series"
                    )

                    col_reps_min = cols[4].text_input(
                        "Min", value=str(fila.get("RepsMin", "")),
                        key=f"repsmin_{key_entrenamiento}", label_visibility="collapsed", placeholder="Mín"
                    )
                    col_reps_max = cols[5].text_input(
                        "Max", value=str(fila.get("RepsMax", "")),
                        key=f"repsmax_{key_entrenamiento}", label_visibility="collapsed", placeholder="Máx"
                    )

                    # Guardar ambos como int si son válidos
                    try:
                        fila["RepsMin"] = int(col_reps_min)
                    except:
                        fila["RepsMin"] = ""

                    try:
                        fila["RepsMax"] = int(col_reps_max)
                    except:
                        fila["RepsMax"] = ""


                    fila["Peso"] = cols[6].text_input(
                        "", value=fila["Peso"],
                        key=f"peso_{key_entrenamiento}", label_visibility="collapsed", placeholder="Kg"
                    )

                    fila["RIR"] = cols[7].text_input(
                        "", value=fila["RIR"],
                        key=f"rir_{key_entrenamiento}", label_visibility="collapsed", placeholder="RIR"
                    )

                    variables_extra = ["", "Tiempo", "Velocidad"]
                    fila["VariableExtra"] = cols[8].selectbox(
                        "", options=variables_extra,
                        index=variables_extra.index(fila.get("VariableExtra", "")),
                        key=f"extra_{key_entrenamiento}",
                        label_visibility="collapsed"
                    )

                    if fila.get("VariableExtra") == "Tiempo":
                        fila["Tiempo"] = cols[9].text_input(
                            "", value=fila["Tiempo"],
                            key=f"tiempo_{key_entrenamiento}",
                            label_visibility="collapsed", placeholder="Seg"
                        )

                    if fila.get("VariableExtra") == "Velocidad":
                        fila["Velocidad"] = cols[9].text_input(
                            "", value=fila["Velocidad"],
                            key=f"velocidad_{key_entrenamiento}",
                            label_visibility="collapsed", placeholder="ms"
                        )

                    # ✅ Mostrar checkboxes en la misma fila
                    # ✅ Fila con checkboxes alineados a la derecha
                    # === CHECKBOXES ALINEADOS A LA DERECHA ===
                    cbox_cols = st.columns([5, 1, 1, 1])  # espacio + link + progresión + copiar

                    with cbox_cols[1]:
                        mostrar_video = st.checkbox("Link de video", key=f"video_check_{key_entrenamiento}")

                    with cbox_cols[2]:
                        mostrar_progresion = st.checkbox("Progresiones", key=f"mostrar_prog_{key_entrenamiento}")

                    with cbox_cols[3]:
                        mostrar_copia = st.checkbox("Copiar Ejercicio", key=f"copia_check_{key_entrenamiento}")

                    # === VIDEO ===
                    if mostrar_video:
                        fila["Video"] = st.text_input(
                            "Link de video (opcional)", value=fila.get("Video", ""),
                            key=f"video_input_{key_entrenamiento}"
                        )
                    else:
                        fila["Video"] = fila.get("Video", "")

                    # === PROGRESIONES ===
                    if mostrar_progresion:
                        st.markdown("#### Progresiones activas")
                        p = int(progresion_activa.split()[-1])  # Detectar si es Progresión 1, 2, 3
                        pcols = st.columns(4)

                        variable_key = f"Variable_{p}"
                        cantidad_key = f"Cantidad_{p}"
                        operacion_key = f"Operacion_{p}"
                        semanas_key = f"Semanas_{p}"

                        fila[variable_key] = pcols[0].selectbox(
                            f"Variable {p}",
                            ["", "peso", "velocidad", "tiempo", "rir", "series", "repeticiones"],
                            index=["", "peso", "velocidad", "tiempo", "rir", "series", "repeticiones"].index(fila.get(variable_key, "")),
                            key=f"var{p}_{key_entrenamiento}"
                        )
                        fila[cantidad_key] = pcols[1].text_input(
                            f"Cantidad {p}", value=fila.get(cantidad_key, ""), key=f"cant{p}_{key_entrenamiento}"
                        )
                        fila[operacion_key] = pcols[2].selectbox(
                            f"Operación {p}", ["", "multiplicacion", "division", "suma", "resta"],
                            index=["", "multiplicacion", "division", "suma", "resta"].index(fila.get(operacion_key, "")),
                            key=f"ope{p}_{key_entrenamiento}"
                        )
                        fila[semanas_key] = pcols[3].text_input(
                            f"Semanas {p}", value=fila.get(semanas_key, ""), key=f"sem{p}_{key_entrenamiento}"
                        )
                    # === COPIAR A OTROS DÍAS ===
                    if mostrar_copia:
                        copiar_cols = st.columns([1, 3])
                        dias_copia = copiar_cols[1].multiselect(
                            "Selecciona día(s) para copiar este ejercicio",
                            dias,
                            key=f"multiselect_{key_entrenamiento}"
                        )

                        if copiar_cols[0].button("✅ Confirmar copia", key=f"confirmar_copia_{key_entrenamiento}") and dias_copia:
                            for dia_destino in dias_copia:
                                idx_dia = dias.index(dia_destino)
                                key_destino = f"rutina_dia_{idx_dia + 1}_{seccion.replace(' ', '_')}"
                                if key_destino not in st.session_state:
                                    st.session_state[key_destino] = []

                                nuevo_ejercicio = {k: v for k, v in fila.items()}

                                # Asegurar que la lista tenga suficiente largo
                                while len(st.session_state[key_destino]) <= idx:
                                    fila_vacia = {k: "" for k in columnas_tabla}
                                    fila_vacia["Sección"] = seccion
                                    st.session_state[key_destino].append(fila_vacia)

                                # Reemplazar o insertar en la misma posición
                                st.session_state[key_destino][idx] = nuevo_ejercicio

                            st.success(f"✅ Ejercicio copiado como Ejercicio {idx + 1} a: {', '.join(dias_copia)}")

    # === IMPORTANTE: Selección de categoría
    st.markdown("---")
    
    # === Normalizador de texto
    import unicodedata
    def normalizar_texto(texto):
        texto = texto.lower().strip()
        texto = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("utf-8")
        return texto

    opcion_categoria = st.sidebar.selectbox("📋 Categoría para análisis:", ["grupo_muscular_principal", "patron_de_movimiento"])

    contador = {}
    nombres_originales = {}

    dias_keys = [k for k in st.session_state if k.startswith("rutina_dia_") and "_Work_Out" in k]

    for key_dia in dias_keys:
        ejercicios = st.session_state[key_dia]

        for ejercicio in ejercicios:
            nombre_raw = ejercicio.get("Ejercicio", "").strip()
            nombre_norm = normalizar_texto(nombre_raw)

            try:
                series = int(ejercicio.get("Series", 0))
            except:
                series = 0

            if not nombre_norm:
                continue

            # Buscar coincidencia exacta normalizada
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

            categoria_norm = normalizar_texto(categoria_valor)
            if categoria_norm in contador:
                contador[categoria_norm] += series
                nombres_originales[categoria_norm].add(categoria_valor)
            else:
                contador[categoria_norm] = series
                nombres_originales[categoria_norm] = {categoria_valor}


    # === Mostrar tabla fija en sidebar
    with st.sidebar:
        st.markdown("### 🧮 Series por categoría")
        if contador:
            df = pd.DataFrame({
                "Categoría": [
                    ", ".join(
                        sorted(
                            cat.replace("_", " ").capitalize()
                            for cat in nombres_originales[k]
                        )
                    ) for k in contador
                ],
                "Series": [contador[k] for k in contador]
            }).sort_values("Series", ascending=False)

            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos de series aún.")

    # ✅ NUEVO BOTÓN: Previsualizar rutina
    if st.button("🔍 Previsualizar rutina"):
        st.subheader("📅 Previsualización de todas las semanas con progresiones aplicadas")

        for semana_idx in range(1, int(semanas) + 1):
            with st.expander(f"Semana {semana_idx}"):
                for i, dia_nombre in enumerate(dias):
                    dia_key = f"rutina_dia_{i + 1}"
                    ejercicios = st.session_state.get(dia_key, [])
                    if not ejercicios:
                        continue

                    st.write(f"**{dia_nombre}**")

                    tabla = []
                    for ejercicio in ejercicios:
                        ejercicio_mod = ejercicio.copy()

                        # Determinar sección por circuito
                        circuito = ejercicio.get("Circuito", "")
                        ejercicio_mod["Sección"] = "Warm Up" if circuito in ["A", "B", "C"] else "Work Out"

                        # Aplicar progresiones
                        for p in range(1, 4):
                            variable = ejercicio.get(f"Variable_{p}", "").strip().lower()
                            cantidad = ejercicio.get(f"Cantidad_{p}", "")
                            operacion = ejercicio.get(f"Operacion_{p}", "").strip().lower()
                            semanas_txt = ejercicio.get(f"Semanas_{p}", "")

                            if variable and operacion and cantidad:
                                try:
                                    semanas_aplicar = [int(s.strip()) for s in semanas_txt.split(",") if s.strip().isdigit()]
                                except:
                                    semanas_aplicar = []

                                for s in range(2, semana_idx + 1):
                                    if s in semanas_aplicar:
                                        if variable == "repeticiones":
                                            reps_min = ejercicio_mod.get("RepsMin", "")
                                            reps_max = ejercicio_mod.get("RepsMax", "")
                                            nuevo_min, nuevo_max = aplicar_progresion_rango(reps_min, reps_max, cantidad, operacion)
                                            ejercicio_mod["RepsMin"] = nuevo_min
                                            ejercicio_mod["RepsMax"] = nuevo_max
                                        else:
                                            valor_base = ejercicio_mod.get(variable.capitalize(), "")
                                            if valor_base != "":
                                                valor_base = aplicar_progresion(valor_base, float(cantidad), operacion)
                                                ejercicio_mod[variable.capitalize()] = valor_base


                        tabla.append({
                            "bloque": ejercicio_mod["Sección"],
                            "circuito": ejercicio_mod["Circuito"],
                            "ejercicio": ejercicio_mod["Ejercicio"],
                            "series": ejercicio_mod["Series"],
                            "repeticiones": ejercicio_mod["Repeticiones"],
                            "peso": ejercicio_mod["Peso"],
                            "tiempo": ejercicio_mod["Tiempo"],
                            "velocidad": ejercicio_mod["Velocidad"],
                            "rir": ejercicio_mod["RIR"],
                            "tipo": ejercicio_mod["Tipo"]
                        })

                    st.dataframe(tabla, use_container_width=True)

    if st.button("Guardar Rutina"):
        if nombre_sel and correo and entrenador:
            guardar_rutina(nombre_sel, correo, entrenador, fecha_inicio, semanas, dias)
        else:
            st.warning("⚠️ Completa nombre, correo y entrenador antes de guardar.")

