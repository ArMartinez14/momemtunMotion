import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from herramientas import aplicar_progresion
from guardar_rutina_view import guardar_rutina
import json

# === INICIALIZAR FIREBASE SOLO UNA VEZ ===
if not firebase_admin._apps:
    cred_dict = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def crear_rutinas():
    st.title("Crear nueva rutina")

    # === Cargar usuarios ===
    docs = db.collection("usuarios").stream()
    usuarios = [doc.to_dict() for doc in docs if doc.exists]
    nombres = sorted(set(u.get("nombre", "") for u in usuarios))

    nombre_input = st.text_input("Escribe el nombre del cliente:")
    coincidencias = [n for n in nombres if nombre_input.lower() in n.lower()]
    nombre_sel = st.selectbox("Selecciona de la lista:", coincidencias) if coincidencias else ""

    correo_auto = next((u.get("correo", "") for u in usuarios if u.get("nombre") == nombre_sel), "")
    correo = st.text_input("Correo del cliente:", value=correo_auto)

    fecha_inicio = st.date_input("Fecha de inicio de rutina:", value=datetime.today())
    semanas = st.number_input("Semanas de duración:", min_value=1, max_value=12, value=4)
    entrenador = st.text_input("Nombre del entrenador responsable:")

    # === Cargar ejercicios desde Firestore ===
    ejercicios_docs = db.collection("ejercicios").stream()
    lista_ejercicios = sorted([doc.to_dict().get("nombre", "") for doc in ejercicios_docs if doc.exists])
    implementos_docs = db.collection("implementos").stream()
    mapa_pesos = {doc.id.lower(): doc.to_dict().get("pesos", []) for doc in implementos_docs}

    st.markdown("---")
    st.subheader("Días de entrenamiento")

    dias = ["Día 1", "Día 2", "Día 3", "Día 4", "Día 5"]
    tabs = st.tabs(dias)

    columnas_tabla = [
        "Circuito", "Ejercicio", "Series", "Repeticiones",
        "Peso", "Tiempo", "Velocidad", "RIR"
    ]

    progresion_activa = st.radio(
        "Progresión activa", ["Progresión 1", "Progresión 2", "Progresión 3"],
        horizontal=True, index=0
    )

    for i, tab in enumerate(tabs):
        with tab:
            dia_key = f"rutina_dia_{i + 1}"
            if dia_key not in st.session_state:
                st.session_state[dia_key] = [{k: "" for k in columnas_tabla} for _ in range(12)]

            st.write(f"Ejercicios para {dias[i]}")
            if st.button(f"Agregar fila en {dias[i]}", key=f"add_row_{i}"):
                st.session_state[dia_key].append({k: "" for k in columnas_tabla})

            st.markdown("#### Warm Up")
            for idx in range(0, 6):
                if idx >= len(st.session_state[dia_key]):
                    continue
                fila = st.session_state[dia_key][idx]
                fila["Circuito"] = ["A", "B", "C"][(idx % 3)]
                fila["Sección"] = "Warm Up"
                st.markdown(f"##### Ejercicio {idx + 1} - {fila.get('Ejercicio', '')}")
                cols = st.columns([1, 4, 2, 2, 2, 2, 2, 2])
                cols[0].text(fila["Circuito"])

                busqueda = cols[1].text_input("", value=fila["Ejercicio"], key=f"busqueda_{i}_{idx}", label_visibility="collapsed", placeholder="Ejercicio")
                coincidencias = [e for e in lista_ejercicios if busqueda.lower() in e.lower()] if busqueda else lista_ejercicios
                seleccion = cols[1].selectbox("", coincidencias, key=f"selector_{i}_{idx}", label_visibility="collapsed")
                fila["Ejercicio"] = seleccion

                doc_ejercicio = db.collection("ejercicios").where("nombre", "==", seleccion).limit(1).stream()
                implemento = next((doc.to_dict().get("equipo", "") for doc in doc_ejercicio), "")
                pesos = mapa_pesos.get(implemento.lower(), [])

                fila["Series"] = cols[2].text_input("", value=fila["Series"], key=f"ser_{i}_{idx}", label_visibility="collapsed", placeholder="Series")
                fila["Repeticiones"] = cols[3].text_input("", value=fila["Repeticiones"], key=f"rep_{i}_{idx}", label_visibility="collapsed", placeholder="Reps")
                if pesos:
                    fila["Peso"] = cols[4].selectbox("", pesos, key=f"peso_{i}_{idx}", label_visibility="collapsed")
                else:
                    fila["Peso"] = cols[4].text_input("", value=fila["Peso"], key=f"peso_{i}_{idx}", label_visibility="collapsed", placeholder="Kg")
                fila["Tiempo"] = cols[5].text_input("", value=fila["Tiempo"], key=f"tiempo_{i}_{idx}", label_visibility="collapsed", placeholder="Seg")
                fila["Velocidad"] = cols[6].text_input("", value=fila["Velocidad"], key=f"vel_{i}_{idx}", label_visibility="collapsed", placeholder="Vel")
                fila["RIR"] = cols[7].text_input("", value=fila["RIR"], key=f"rir_{i}_{idx}", label_visibility="collapsed", placeholder="RIR")

            st.markdown("#### Work Out")
            for idx in range(6, 12):
                if idx >= len(st.session_state[dia_key]):
                    continue
                fila = st.session_state[dia_key][idx]
                fila["Circuito"] = ["D", "E", "F", "G", "H", "I"][(idx - 6)]
                fila["Sección"] = "Work Out"
                st.markdown(f"##### Ejercicio {idx + 1} - {fila.get('Ejercicio', '')}")
                cols = st.columns([1, 4, 2, 2, 2, 2, 2, 2])
                cols[0].text(fila["Circuito"])

                busqueda = cols[1].text_input("", value=fila["Ejercicio"], key=f"busqueda_{i}_{idx}", label_visibility="collapsed", placeholder="Ejercicio")
                coincidencias = [e for e in lista_ejercicios if busqueda.lower() in e.lower()] if busqueda else lista_ejercicios
                seleccion = cols[1].selectbox("", coincidencias, key=f"selector_{i}_{idx}", label_visibility="collapsed")
                fila["Ejercicio"] = seleccion

                doc_ejercicio = db.collection("ejercicios").where("nombre", "==", seleccion).limit(1).stream()
                implemento = next((doc.to_dict().get("equipo", "") for doc in doc_ejercicio), "")
                pesos = mapa_pesos.get(implemento.lower(), [])

                fila["Series"] = cols[2].text_input("", value=fila["Series"], key=f"ser_{i}_{idx}", label_visibility="collapsed", placeholder="Series")
                fila["Repeticiones"] = cols[3].text_input("", value=fila["Repeticiones"], key=f"rep_{i}_{idx}", label_visibility="collapsed", placeholder="Reps")
                if pesos:
                    fila["Peso"] = cols[4].selectbox("", pesos, key=f"peso_{i}_{idx}", label_visibility="collapsed")
                else:
                    fila["Peso"] = cols[4].text_input("", value=fila["Peso"], key=f"peso_{i}_{idx}", label_visibility="collapsed", placeholder="Kg")
                fila["Tiempo"] = cols[5].text_input("", value=fila["Tiempo"], key=f"tiempo_{i}_{idx}", label_visibility="collapsed", placeholder="Seg")
                fila["Velocidad"] = cols[6].text_input("", value=fila["Velocidad"], key=f"vel_{i}_{idx}", label_visibility="collapsed", placeholder="Vel")
                fila["RIR"] = cols[7].text_input("", value=fila["RIR"], key=f"rir_{i}_{idx}", label_visibility="collapsed", placeholder="RIR")

    st.markdown("---")

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
                        circuito = ejercicio.get("Circuito", "")
                        ejercicio_mod["Sección"] = "Warm Up" if circuito in ["A", "B", "C"] else "Work Out"
                        for p in range(1, 4):
                            variable = ejercicio.get(f"Variable_{p}", "").strip().lower()
                            cantidad = ejercicio.get(f"Cantidad_{p}", "")
                            operacion = ejercicio.get(f"Operacion_{p}", "").strip().lower()
                            semanas_txt = ejercicio.get(f"Semanas_{p}", "")
                            if variable and operacion and cantidad:
                                valor_base = ejercicio_mod.get(variable.capitalize(), "")
                                if valor_base:
                                    valor_actual = valor_base
                                    try:
                                        semanas_aplicar = [int(s.strip()) for s in semanas_txt.split(",") if s.strip().isdigit()]
                                    except:
                                        semanas_aplicar = []
                                    for s in range(2, semana_idx + 1):
                                        if s in semanas_aplicar:
                                            valor_actual = aplicar_progresion(valor_actual, float(cantidad), operacion)
                                    ejercicio_mod[variable.capitalize()] = valor_actual

                        tabla.append({
                            "bloque": ejercicio_mod["Sección"],
                            "circuito": ejercicio_mod["Circuito"],
                            "ejercicio": ejercicio_mod["Ejercicio"],
                            "series": ejercicio_mod["Series"],
                            "repeticiones": ejercicio_mod["Repeticiones"],
                            "peso": ejercicio_mod["Peso"],
                            "tiempo": ejercicio_mod["Tiempo"],
                            "velocidad": ejercicio_mod["Velocidad"],
                            "rir": ejercicio_mod["RIR"]
                        })
                    st.dataframe(tabla, use_container_width=True)

    if st.button("Guardar Rutina"):
        if nombre_sel and correo and entrenador:
            guardar_rutina(nombre_sel, correo, entrenador, fecha_inicio, semanas, dias)
        else:
            st.warning("⚠️ Completa nombre, correo y entrenador antes de guardar.")