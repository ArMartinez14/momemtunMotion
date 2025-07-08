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

    variables_progresion = ["", "peso", "velocidad", "tiempo", "rir", "series", "repeticiones"]
    operaciones = ["", "multiplicacion", "division", "suma", "resta"]

    for i, tab in enumerate(tabs):
        with tab:
            dia_key = f"rutina_dia_{i + 1}"
            if dia_key not in st.session_state:
                rutina_vacia = []
                for j in range(12):
                    fila = {k: "" for k in columnas_tabla}
                    fila["Circuito"] = ["A", "A", "A", "B", "B", "B", "D", "D", "E", "E", "F", "F"][j]
                    fila["Sección"] = "Warm Up" if j < 6 else "Work Out"
                    for p in range(1, 4):
                        fila[f"Variable_{p}"] = ""
                        fila[f"Cantidad_{p}"] = ""
                        fila[f"Operacion_{p}"] = ""
                        fila[f"Semanas_{p}"] = ""
                    rutina_vacia.append(fila)
                st.session_state[dia_key] = rutina_vacia

            st.write(f"Ejercicios para {dias[i]}")

            st.markdown("#### Warm Up")
            for idx in range(0, 6):
                fila = st.session_state[dia_key][idx]
                fila["Sección"] = "Warm Up"
                st.markdown(f"##### Ejercicio {idx + 1} - {fila.get('Ejercicio', '')}")
                cols = st.columns([1, 4, 2, 2, 2, 2, 2, 2] + [2]*4*3)

                fila["Circuito"] = cols[0].selectbox("", ["A", "B", "C"], index=["A", "B", "C"].index(fila["Circuito"]) if fila["Circuito"] in ["A", "B", "C"] else 0, key=f"circuito_{i}_{idx}", label_visibility="collapsed")
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

                for p in range(1, 4):
                    fila[f"Variable_{p}"] = cols[7 + p*4 + 0].selectbox("", variables_progresion, index=variables_progresion.index(fila.get(f"Variable_{p}", "")), key=f"var{p}_{i}_{idx}", label_visibility="collapsed")
                    fila[f"Cantidad_{p}"] = cols[7 + p*4 + 1].text_input("", value=fila.get(f"Cantidad_{p}", ""), key=f"cant{p}_{i}_{idx}", label_visibility="collapsed", placeholder=f"Cant{p}")
                    fila[f"Operacion_{p}"] = cols[7 + p*4 + 2].selectbox("", operaciones, index=operaciones.index(fila.get(f"Operacion_{p}", "")), key=f"ope{p}_{i}_{idx}", label_visibility="collapsed")
                    fila[f"Semanas_{p}"] = cols[7 + p*4 + 3].text_input("", value=fila.get(f"Semanas_{p}", ""), key=f"sem{p}_{i}_{idx}", label_visibility="collapsed", placeholder=f"Sem{p}")

            st.markdown("#### Work Out")
            for idx in range(6, len(st.session_state[dia_key])):
                fila = st.session_state[dia_key][idx]
                fila["Sección"] = "Work Out"
                st.markdown(f"##### Ejercicio {idx + 1} - {fila.get('Ejercicio', '')}")
                cols = st.columns([1, 4, 2, 2, 2, 2, 2, 2] + [2]*4*3)

                fila["Circuito"] = cols[0].selectbox("", ["D", "E", "F", "G", "H", "I"], index=["D", "E", "F", "G", "H", "I"].index(fila["Circuito"]) if fila["Circuito"] in ["D", "E", "F", "G", "H", "I"] else 0, key=f"circuito_{i}_{idx}", label_visibility="collapsed")
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

                for p in range(1, 4):
                    fila[f"Variable_{p}"] = cols[7 + p*4 + 0].selectbox("", variables_progresion, index=variables_progresion.index(fila.get(f"Variable_{p}", "")), key=f"var{p}_{i}_{idx}", label_visibility="collapsed")
                    fila[f"Cantidad_{p}"] = cols[7 + p*4 + 1].text_input("", value=fila.get(f"Cantidad_{p}", ""), key=f"cant{p}_{i}_{idx}", label_visibility="collapsed", placeholder=f"Cant{p}")
                    fila[f"Operacion_{p}"] = cols[7 + p*4 + 2].selectbox("", operaciones, index=operaciones.index(fila.get(f"Operacion_{p}", "")), key=f"ope{p}_{i}_{idx}", label_visibility="collapsed")
                    fila[f"Semanas_{p}"] = cols[7 + p*4 + 3].text_input("", value=fila.get(f"Semanas_{p}", ""), key=f"sem{p}_{i}_{idx}", label_visibility="collapsed", placeholder=f"Sem{p}")
