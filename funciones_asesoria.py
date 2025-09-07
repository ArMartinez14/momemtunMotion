# funciones_asesoria.py
import streamlit as st

from seccion_ejercicios import base_ejercicios
from vista_rutinas import ver_rutinas
from borrar_rutinas import borrar_rutinas
from ingresar_cliente_view import ingresar_cliente_o_video_o_ejercicio
from crear_planificaciones import crear_rutinas
from editar_rutinas import editar_rutinas
from crear_descarga import descarga_rutina
from reportes import ver_reportes
from admin_resumen import ver_resumen_entrenadores

from rol_router import (
    exponer, requires_capability,
    ROL_ADMIN, ROL_ENTRENADOR, ROL_DEPORTISTA
)

# === VER RUTINAS (todos) ===
@exponer("ver_rutinas", roles=[ROL_ADMIN, ROL_ENTRENADOR, ROL_DEPORTISTA])
def feature_ver_rutinas():
    ver_rutinas()

# === CREAR RUTINAS (admin/entrenador) ===
@exponer("crear_rutinas", roles=[ROL_ADMIN, ROL_ENTRENADOR])
def feature_crear_rutinas():
    crear_rutinas()

# === EDITAR RUTINAS (admin/entrenador) ===
@exponer("editar_rutinas", roles=[ROL_ADMIN, ROL_ENTRENADOR])
def feature_editar_rutinas():
    editar_rutinas()

# === REPORTES (admin/entrenador) ===
@exponer("ver_reportes", roles=[ROL_ADMIN, ROL_ENTRENADOR])
def feature_ver_reportes():
    ver_reportes()

# === DESCARGA (todos) ===
@exponer("descargar_rutinas", roles=[ROL_ADMIN, ROL_ENTRENADOR, ROL_DEPORTISTA])
def feature_descarga_rutina():
    descarga_rutina()

# === GESTIONAR CLIENTES (admin/entrenador) ===
@requires_capability("gestionar_clientes")
@exponer("gestionar_clientes", roles=[ROL_ADMIN, ROL_ENTRENADOR])
def feature_gestionar_clientes():
    ingresar_cliente_o_video_o_ejercicio()

# === EJERCICIOS (admin/entrenador) ===
@exponer("ejercicios", roles=[ROL_ADMIN, ROL_ENTRENADOR])
def feature_ejercicios():
    base_ejercicios()

# === RESUMEN ADMIN (solo admin) ===
@exponer("resumen_admin", roles=[ROL_ADMIN])
def feature_resumen_admin():
    ver_resumen_entrenadores()
