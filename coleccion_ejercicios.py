import firebase_admin
from firebase_admin import credentials, firestore

# === 1️⃣ Inicializar Firebase desde archivo local ===
cred = credentials.Certificate("firebase.json")  # Asegúrate que este archivo esté en la misma carpeta
firebase_admin.initialize_app(cred)
db = firestore.client()

# === 2️⃣ Ejercicios de prueba ===
ejercicios = [
    {
        "nombre_es": "Sentadilla",
        "nombre_en": "Squat",
        "grupo_muscular": "Piernas",
        "tipo": "Fuerza",
        "equipo": "Barra",
        "nivel": "Intermedio"
    },
    {
        "nombre_es": "Peso muerto",
        "nombre_en": "Deadlift",
        "grupo_muscular": "Espalda",
        "tipo": "Fuerza",
        "equipo": "Barra",
        "nivel": "Intermedio"
    },
    {
        "nombre_es": "Prensa 45°",
        "nombre_en": "Leg Press 45",
        "grupo_muscular": "Piernas",
        "tipo": "Fuerza",
        "equipo": "Prensa 45°",
        "nivel": "Intermedio"
    }
]

for ejercicio in ejercicios:
    doc_id = ejercicio["nombre_es"].lower().replace(" ", "_").replace("°", "")
    db.collection("ejercicios").document(doc_id).set(ejercicio)

print("✅ Ejercicios cargados correctamente")

# === 3️⃣ Implementos de prueba ===
implementos = [
    {
        "nombre": "Barra",
        "tipo": "Libre",
        "pesos_disponibles": [20, 25, 30, 35, 40, 45, 50, 55, 60]
    },
    {
        "nombre": "Prensa 45°",
        "tipo": "Máquina",
        "pesos_disponibles": [7, 14, 21, 28, 35, 42, 49, 56]
    }
]

for impl in implementos:
    doc_id = impl["nombre"].lower().replace(" ", "_").replace("°", "")
    db.collection("implementos").document(doc_id).set(impl)

print("✅ Implementos cargados correctamente")
