# guardar_rutina.py
import json
import uuid
from datetime import timedelta
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

from herramientas import aplicar_progresion, normalizar_texto  # ya lo tienes


def _get_db():
    """Obtiene un cliente Firestore, inicializando si hace falta."""
    if not firebase_admin._apps:
        cred_dict = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()


def aplicar_progresion_rango(valor_min, valor_max, cantidad, operacion):
    def operar(valor, cantidad, operacion):
        try:
            v = float(valor)
            c = float(cantidad)
            if operacion == "suma":
                return int(round(v + c))
            elif operacion == "resta":
                return int(round(v - c))
            elif operacion == "multiplicacion":
                return int(round(v * c))
            elif operacion == "division" and c != 0:
                return int(round(v / c))
        except Exception:
            pass
        return valor

    nuevo_min = operar(valor_min, cantidad, operacion) if valor_min != "" else ""
    nuevo_max = operar(valor_max, cantidad, operacion) if valor_max != "" else ""
    return nuevo_min, nuevo_max


def _to_int_or_empty(v):
    try:
        return int(v)
    except Exception:
        return ""


def guardar_rutina(nombre_sel, correo, entrenador, fecha_inicio, semanas, dias):
    """
    nombre_sel: nombre del cliente (string)
    correo: correo del cliente
    entrenador: correo del entrenador (responsable)
    fecha_inicio: date (lunes de la semana 1)
    semanas: int
    dias: lista de labels ["Día 1", ...] (solo usamos el índice)
    """
    db = _get_db()

    # 🆕 Identificador de bloque (estable para todas las semanas que se guardan en esta acción)
    bloque_id = str(uuid.uuid4())

    try:
        for semana in range(int(semanas)):
            fecha_semana = fecha_inicio + timedelta(weeks=semana)
            fecha_str = fecha_semana.strftime("%Y-%m-%d")
            fecha_norm = fecha_semana.strftime("%Y_%m_%d")
            correo_norm = correo.strip().lower().replace("@", "_").replace(".", "_")
            cliente_norm = normalizar_texto(nombre_sel.title())

            rutina_semana = {
                "cliente": cliente_norm,
                "correo": correo,
                "fecha_lunes": fecha_str,
                "entrenador": (entrenador or "").strip().lower(),
                "bloque_rutina": bloque_id,
                "rutina": {}
            }

            # Recorremos días por índice (claves de session_state usan índice 1..N)
            for i, _dia_label in enumerate(dias):
                numero_dia = str(i + 1)
                lista_ejercicios = []

                for seccion in ["Warm Up", "Work Out"]:
                    dia_key = f"rutina_dia_{i + 1}_{seccion.replace(' ', '_')}"
                    ejercicios = st.session_state.get(dia_key, [])

                    for ejercicio in ejercicios:
                        if not str(ejercicio.get("Ejercicio", "")).strip():
                            continue  # filas vacías fuera

                        ejercicio_mod = dict(ejercicio)  # copia

                        # --- Normalizar RepsMin/RepsMax a int o "" ---
                        ejercicio_mod["RepsMin"] = _to_int_or_empty(ejercicio_mod.get("RepsMin", ""))
                        ejercicio_mod["RepsMax"] = _to_int_or_empty(ejercicio_mod.get("RepsMax", ""))

                        # === APLICAR PROGRESIONES (para semana > 1 según "Semanas_p") ===
                        campos_progresion = {
                            "peso": "Peso",
                            "rir": "RIR",
                            "tiempo": "Tiempo",
                            "velocidad": "Velocidad",
                            "repeticiones": ("RepsMin", "RepsMax"),
                            "series": "Series",
                        }

                        for var_interna, var_real in campos_progresion.items():
                            if isinstance(var_real, tuple):
                                # Rango de repeticiones
                                min_key, max_key = var_real
                                valor_min = ejercicio_mod.get(min_key, "")
                                valor_max = ejercicio_mod.get(max_key, "")

                                for p in range(1, 4):
                                    var = str(ejercicio.get(f"Variable_{p}", "")).strip().lower()
                                    if var != "repeticiones":
                                        continue
                                    cantidad = ejercicio.get(f"Cantidad_{p}", "")
                                    operacion = str(ejercicio.get(f"Operacion_{p}", "")).strip().lower()
                                    semanas_txt = str(ejercicio.get(f"Semanas_{p}", ""))

                                    if not (cantidad and operacion):
                                        continue

                                    try:
                                        semanas_aplicar = [int(s.strip()) for s in semanas_txt.split(",") if s.strip().isdigit()]
                                    except Exception:
                                        semanas_aplicar = []

                                    # Se aplican a partir de la semana 2; aquí estamos parados en 'semana' base 0
                                    for s in range(2, semana + 2):
                                        if s in semanas_aplicar:
                                            valor_min, valor_max = aplicar_progresion_rango(valor_min, valor_max, cantidad, operacion)

                                ejercicio_mod[min_key] = valor_min
                                ejercicio_mod[max_key] = valor_max

                            else:
                                # Escala simple (peso, rir, tiempo, velocidad, series)
                                valor_actual = ejercicio_mod.get(var_real, "")
                                if valor_actual == "":
                                    continue

                                for p in range(1, 4):
                                    var = str(ejercicio.get(f"Variable_{p}", "")).strip().lower()
                                    if var != var_interna:
                                        continue
                                    cantidad = ejercicio.get(f"Cantidad_{p}", "")
                                    operacion = str(ejercicio.get(f"Operacion_{p}", "")).strip().lower()
                                    semanas_txt = str(ejercicio.get(f"Semanas_{p}", ""))

                                    if not (cantidad and operacion):
                                        continue

                                    try:
                                        semanas_aplicar = [int(s.strip()) for s in semanas_txt.split(",") if s.strip().isdigit()]
                                    except Exception:
                                        semanas_aplicar = []

                                    for s in range(2, semana + 2):
                                        if s in semanas_aplicar:
                                            try:
                                                valor_actual = aplicar_progresion(valor_actual, float(cantidad), operacion)
                                            except Exception:
                                                pass

                                ejercicio_mod[var_real] = valor_actual

                        # --- Armar payload de ejercicio para Firestore ---
                        lista_ejercicios.append({
                            "bloque": ejercicio_mod.get("Sección", seccion),
                            "circuito": ejercicio_mod.get("Circuito", ""),
                            "ejercicio": ejercicio_mod.get("Ejercicio", ""),
                            "detalle": ejercicio_mod.get("Detalle", ""),
                            "series": ejercicio_mod.get("Series", ""),
                            "reps_min": ejercicio_mod.get("RepsMin", ""),
                            "reps_max": ejercicio_mod.get("RepsMax", ""),
                            "peso": ejercicio_mod.get("Peso", ""),
                            "tiempo": ejercicio_mod.get("Tiempo", ""),
                            "velocidad": ejercicio_mod.get("Velocidad", ""),
                            "rir": ejercicio_mod.get("RIR", ""),
                            "tipo": ejercicio_mod.get("Tipo", ""),
                            "video": ejercicio_mod.get("Video", ""),
                        })

                if lista_ejercicios:
                    rutina_semana["rutina"][numero_dia] = lista_ejercicios

            # === GUARDAR SOLO SI TIENE DÍAS ===
            if rutina_semana["rutina"]:
                doc_id = f"{correo_norm}_{fecha_norm}"
                db.collection("rutinas_semanales").document(doc_id).set(rutina_semana)

        st.success(f"✅ Rutina generada correctamente para {semanas} semanas.")

    except Exception as e:
        st.error(f"❌ Error al guardar la rutina: {e}")

