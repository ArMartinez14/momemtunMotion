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

    # === Elegir progresión visible ===
    st.markdown("---")
    progresion_activa = st.selectbox("Selecciona la progresión que quieres visualizar:", ["Progresión 1", "Progresión 2", "Progresión 3"])

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
        "Circuito", "Sección", "Ejercicio", "Series", "Repeticiones",
        "Peso", "Tiempo", "Velocidad", "RIR"
    ]

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
                fila["Circuito"] = ["A", "A", "A", "B", "B", "B"][idx]
                fila["Sección"] = "Warm Up"
                st.markdown(f"##### Ejercicio {idx + 1} - {fila.get('Ejercicio', '')}")
                cols = st.columns([1, 4, 2, 2, 2, 2, 2, 2])

                fila["Circuito"] = cols[0].selectbox("", ["A", "B", "C", "D", "E", "F"],
                    index=["A", "B", "C", "D", "E", "F"].index(fila["Circuito"]) if fila["Circuito"] in ["A", "B", "C", "D", "E", "F"] else 0,
                    key=f"circ_{i}_{idx}", label_visibility="collapsed")

                busqueda = cols[1].text_input("", value=fila["Ejercicio"], key=f"busqueda_{i}_{idx}", label_visibility="collapsed", placeholder="Ejercicio")
                coincidencias = [e for e in lista_ejercicios if busqueda.lower() in e.lower()] if busqueda else lista_ejercicios
                seleccion = cols[1].selectbox("", coincidencias, key=f"selector_{i}_{idx}", label_visibility="collapsed")
                fila["Ejercicio"] = seleccion

                doc_ejercicio = db.collection("ejercicios").where("nombre", "==", seleccion).limit(1).stream()
                implemento = next((doc.to_dict().get("equipo", "") for doc in doc_ejercicio), "")
                pesos = mapa_pesos.get(implemento.lower(), [])

                fila["Series"] = cols[2].text_input("", value=fila["Series"], key=f"ser_{i}_{idx}", label_visibility="collapsed", placeholder="Series")
                fila["Repeticiones"] = cols[3].text_input("", value=fila["Repeticiones"], key=f"rep_{i}_{idx}", label_visibility="collapsed", placeholder="Reps")
                fila["Peso"] = cols[4].selectbox("", pesos, key=f"peso_{i}_{idx}", label_visibility="collapsed") if pesos else cols[4].text_input("", value=fila["Peso"], key=f"peso_{i}_{idx}", label_visibility="collapsed", placeholder="Kg")
                fila["Tiempo"] = cols[5].text_input("", value=fila["Tiempo"], key=f"tiempo_{i}_{idx}", label_visibility="collapsed", placeholder="Seg")
                fila["Velocidad"] = cols[6].text_input("", value=fila["Velocidad"], key=f"vel_{i}_{idx}", label_visibility="collapsed", placeholder="Vel")
                fila["RIR"] = cols[7].text_input("", value=fila["RIR"], key=f"rir_{i}_{idx}", label_visibility="collapsed", placeholder="RIR")

                # === Agregar progresiones ===
                if progresion_activa:
                    p = progresion_activa[-1]  # '1', '2' o '3'
                    prog_cols = st.columns([3, 2, 3, 3])
                    fila[f"Variable_{p}"] = prog_cols[0].selectbox(
                        "", ["", "peso", "velocidad", "tiempo", "rir", "series", "repeticiones"],
                        index=0 if not fila.get(f"Variable_{p}") else ["", "peso", "velocidad", "tiempo", "rir", "series", "repeticiones"].index(fila[f"Variable_{p}"]),
                        key=f"var_{i}_{idx}_{p}", label_visibility="collapsed")
                    fila[f"Cantidad_{p}"] = prog_cols[1].text_input("", value=fila.get(f"Cantidad_{p}", ""), key=f"cant_{i}_{idx}_{p}", label_visibility="collapsed", placeholder="Cantidad")
                    fila[f"Operacion_{p}"] = prog_cols[2].selectbox(
                        "", ["", "multiplicacion", "division", "suma", "resta"],
                        index=0 if not fila.get(f"Operacion_{p}") else ["", "multiplicacion", "division", "suma", "resta"].index(fila[f"Operacion_{p}"]),
                        key=f"ope_{i}_{idx}_{p}", label_visibility="collapsed")
                    fila[f"Semanas_{p}"] = prog_cols[3].text_input("", value=fila.get(f"Semanas_{p}", ""), key=f"sem_{i}_{idx}_{p}", label_visibility="collapsed", placeholder="Semanas")

            st.markdown("#### Work Out")
            for idx in range(6, 12):
                if idx >= len(st.session_state[dia_key]):
                    continue
                fila = st.session_state[dia_key][idx]
                fila["Circuito"] = ["D", "E", "F", "G", "H", "I"][(idx - 6)]
                fila["Sección"] = "Work Out"
                st.markdown(f"##### Ejercicio {idx + 1} - {fila.get('Ejercicio', '')}")
                cols = st.columns([1, 4, 2, 2, 2, 2, 2, 2])
                fila["Circuito"] = cols[0].selectbox("", ["A", "B", "C", "D", "E", "F"],
                    index=["A", "B", "C", "D", "E", "F"].index(fila["Circuito"]) if fila["Circuito"] in ["A", "B", "C", "D", "E", "F"] else 0,
                    key=f"circ_{i}_{idx}", label_visibility="collapsed")

                busqueda = cols[1].text_input("", value=fila["Ejercicio"], key=f"busqueda_{i}_{idx}", label_visibility="collapsed", placeholder="Ejercicio")
                coincidencias = [e for e in lista_ejercicios if busqueda.lower() in e.lower()] if busqueda else lista_ejercicios
                seleccion = cols[1].selectbox("", coincidencias, key=f"selector_{i}_{idx}", label_visibility="collapsed")
                fila["Ejercicio"] = seleccion

                doc_ejercicio = db.collection("ejercicios").where("nombre", "==", seleccion).limit(1).stream()
                implemento = next((doc.to_dict().get("equipo", "") for doc in doc_ejercicio), "")
                pesos = mapa_pesos.get(implemento.lower(), [])

                fila["Series"] = cols[2].text_input("", value=fila["Series"], key=f"ser_{i}_{idx}", label_visibility="collapsed", placeholder="Series")
                fila["Repeticiones"] = cols[3].text_input("", value=fila["Repeticiones"], key=f"rep_{i}_{idx}", label_visibility="collapsed", placeholder="Reps")
                fila["Peso"] = cols[4].selectbox("", pesos, key=f"peso_{i}_{idx}", label_visibility="collapsed") if pesos else cols[4].text_input("", value=fila["Peso"], key=f"peso_{i}_{idx}", label_visibility="collapsed", placeholder="Kg")
                fila["Tiempo"] = cols[5].text_input("", value=fila["Tiempo"], key=f"tiempo_{i}_{idx}", label_visibility="collapsed", placeholder="Seg")
                fila["Velocidad"] = cols[6].text_input("", value=fila["Velocidad"], key=f"vel_{i}_{idx}", label_visibility="collapsed", placeholder="Vel")
                fila["RIR"] = cols[7].text_input("", value=fila["RIR"], key=f"rir_{i}_{idx}", label_visibility="collapsed", placeholder="RIR")

                if progresion_activa:
                    p = progresion_activa[-1]
                    prog_cols = st.columns([3, 2, 3, 3])
                    fila[f"Variable_{p}"] = prog_cols[0].selectbox(
                        "", ["", "peso", "velocidad", "tiempo", "rir", "series", "repeticiones"],
                        index=0 if not fila.get(f"Variable_{p}") else ["", "peso", "velocidad", "tiempo", "rir", "series", "repeticiones"].index(fila[f"Variable_{p}"]),
                        key=f"var_{i}_{idx}_{p}", label_visibility="collapsed")
                    fila[f"Cantidad_{p}"] = prog_cols[1].text_input("", value=fila.get(f"Cantidad_{p}", ""), key=f"cant_{i}_{idx}_{p}", label_visibility="collapsed", placeholder="Cantidad")
                    fila[f"Operacion_{p}"] = prog_cols[2].selectbox(
                        "", ["", "multiplicacion", "division", "suma", "resta"],
                        index=0 if not fila.get(f"Operacion_{p}") else ["", "multiplicacion", "division", "suma", "resta"].index(fila[f"Operacion_{p}"]),
                        key=f"ope_{i}_{idx}_{p}", label_visibility="collapsed")
                    fila[f"Semanas_{p}"] = prog_cols[3].text_input("", value=fila.get(f"Semanas_{p}", ""), key=f"sem_{i}_{idx}_{p}", label_visibility="collapsed", placeholder="Semanas")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📦 Previsualizar rutina"):
            st.write(st.session_state)
    with col2:
        if st.button("💾 Guardar rutina completa"):
            if nombre_sel and correo and entrenador:
                guardar_rutina(nombre_sel, correo, entrenador, fecha_inicio, semanas, dias)
            else:
                st.warning("⚠️ Completa nombre, correo y entrenador antes de guardar.")
