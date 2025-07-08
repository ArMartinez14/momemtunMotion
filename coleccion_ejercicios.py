import csv
import firebase_admin
from firebase_admin import credentials, firestore
import unicodedata

# === 🔤 Función para normalizar texto ===
def normalizar(texto):
    if not texto:
        return ""
    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    return texto

def formatear_id(texto):
    return normalizar(texto).replace(" ", "_").replace("-", "_").replace("°", "")

# === 🔐 Inicializar Firebase ===
cred = credentials.Certificate("rutinasmotion-2f8922ec718f.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# === 📄 Leer CSV ===
with open("ejercicios.csv", encoding="utf-8-sig") as archivo:
    lector = csv.DictReader(archivo)
    ejercicios_raw = list(lector)

# === 🔁 Subir con normalización de ID y campos
for fila in ejercicios_raw:
    fila_normalizada = {}
    
    for clave_original, valor_original in fila.items():
        clave = normalizar(clave_original).replace(" ", "_").replace("-", "_")
        
        # Mantener valor de "nombre" sin guiones bajos
        if clave == "nombre":
            valor = normalizar(valor_original)
        else:
            valor = formatear_id(valor_original)

        fila_normalizada[clave] = valor

    doc_id = formatear_id(fila.get("Nombre", "sin_nombre"))
    db.collection("ejercicios").document(doc_id).set(fila_normalizada)

print(f"✅ Subidos {len(ejercicios_raw)} ejercicios normalizados con ID limpio y campo 'nombre' legible.")
