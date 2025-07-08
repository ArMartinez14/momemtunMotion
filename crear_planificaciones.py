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
        "Circuito", "Sección", "Ejercicio", "Series", "Repeticiones",
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
                st.session_state[dia_key] = [{k: "" for k in columnas_tabla} for _ in range(8)]

            st.write(f"Ejercicios para {dias[i]}")
            if st.button(f"Agregar fila en {dias[i]}", key=f"add_row_{i}"):
                st.session_state[dia_key].append({k: "" for k in columnas_tabla})

            for idx, fila in enumerate(st.session_state[dia_key]):
                st.markdown(f"##### Ejercicio {idx + 1} - {fila.get('Ejercicio', '')}")
                cols = st.columns([1, 2, 4, 2, 2, 2, 2, 2, 2])
                fila["Circuito"] = cols[0].selectbox(
                    "", ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
                    index=["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"].index(fila["Circuito"]) if fila["Circuito"] else 0,
                    key=f"circ_{i}_{idx}", label_visibility="collapsed"
                )
                fila["Sección"] = "Warm Up" if fila["Circuito"] in ["A", "B", "C"] else "Work Out"
                cols[1].text(fila["Sección"])

                busqueda = cols[2].text_input(
                    "", value=fila["Ejercicio"], key=f"busqueda_{i}_{idx}", label_visibility="collapsed", placeholder="Ejercicio"
                )
                coincidencias = [e for e in lista_ejercicios if busqueda.lower() in e.lower()] if busqueda else lista_ejercicios
                seleccion = cols[2].selectbox(
                    "", coincidencias, key=f"selector_{i}_{idx}", label_visibility="collapsed"
                )
                fila["Ejercicio"] = seleccion

                doc_ejercicio = db.collection("ejercicios").where("nombre", "==", seleccion).limit(1).stream()
                implemento = next((doc.to_dict().get("equipo", "") for doc in doc_ejercicio), "")
                pesos = mapa_pesos.get(implemento.lower(), [])

                fila["Series"] = cols[3].text_input("", value=fila["Series"], key=f"ser_{i}_{idx}", label_visibility="collapsed", placeholder="Series")
                fila["Repeticiones"] = cols[4].text_input("", value=fila["Repeticiones"], key=f"rep_{i}_{idx}", label_visibility="collapsed", placeholder="Reps")
                if pesos:
                    fila["Peso"] = cols[5].selectbox("", pesos, key=f"peso_{i}_{idx}", label_visibility="collapsed")
                else:
                    fila["Peso"] = cols[5].text_input("", value=fila["Peso"], key=f"peso_{i}_{idx}", label_visibility="collapsed", placeholder="Kg")

                fila["Tiempo"] = cols[6].text_input("", value=fila["Tiempo"], key=f"tiempo_{i}_{idx}", label_visibility="collapsed", placeholder="Seg")
                fila["Velocidad"] = cols[7].text_input("", value=fila["Velocidad"], key=f"vel_{i}_{idx}", label_visibility="collapsed", placeholder="Vel")
                fila["RIR"] = cols[8].text_input("", value=fila["RIR"], key=f"rir_{i}_{idx}", label_visibility="collapsed", placeholder="RIR")

                if progresion_activa:
                    fila[f"Variable_{progresion_activa[-1]}"] = st.selectbox(
                        "Variable a modificar", ["", "peso", "velocidad", "tiempo", "rir", "series", "repeticiones"],
                        index=0 if not fila.get(f"Variable_{progresion_activa[-1]}") else ["", "peso", "velocidad", "tiempo", "rir", "series", "repeticiones"].index(fila[f"Variable_{progresion_activa[-1]}"]),
                        key=f"var_{i}_{idx}"
                    )
                    fila[f"Cantidad_{progresion_activa[-1]}"] = st.text_input("Cantidad", value=fila.get(f"Cantidad_{progresion_activa[-1]}", ""), key=f"cant_{i}_{idx}")
                    fila[f"Operacion_{progresion_activa[-1]}"] = st.selectbox("Operación", ["", "multiplicacion", "division", "suma", "resta"],
                        index=0 if not fila.get(f"Operacion_{progresion_activa[-1]}") else ["", "multiplicacion", "division", "suma", "resta"].index(fila[f"Operacion_{progresion_activa[-1]}"]),
                        key=f"ope_{i}_{idx}")
                    fila[f"Semanas_{progresion_activa[-1]}"] = st.text_input("Semanas", value=fila.get(f"Semanas_{progresion_activa[-1]}", ""), key=f"sem_{i}_{idx}")

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
