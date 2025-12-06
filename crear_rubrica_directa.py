import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Inicializar Firebase
cred = credentials.Certificate("serviceAccountKey.json")
try:
    firebase_admin.get_app()
except:
    firebase_admin.initialize_app(cred)

db = firestore.client()

print("=" * 60)
print("🚀 CREADOR DE RÚBRICA FLIA 2025")
print("=" * 60)

# 1. Desactivar rúbricas anteriores
print("\n🔄 Paso 1: Desactivando rúbricas anteriores...")
rubricas_anteriores = db.collection('rubricas').where('activa', '==', True).stream()
count_desactivadas = 0
for rubrica in rubricas_anteriores:
    db.collection('rubricas').document(rubrica.id).update({'activa': False})
    count_desactivadas += 1
    print(f"   ✓ Rúbrica {rubrica.id} desactivada")

if count_desactivadas == 0:
    print("   ℹ️  No había rúbricas activas")

# 2. Crear la nueva rúbrica
print("\n📝 Paso 2: Creando nueva rúbrica...")

rubrica_data = {
    'nombre': 'Rúbrica FLIA 2025',
    'anio': 2025,
    'activa': True,
    'criterios': [
        {
            'nombre': 'Innovación',
            'porcentaje': 20.0,
            'puntos_maximos': 10,
            'descripcion': 'Originalidad y creatividad en la solución propuesta'
        },
        {
            'nombre': 'Visión Empresarial',
            'porcentaje': 10.0,
            'puntos_maximos': 10,
            'descripcion': 'Potencial comercial y viabilidad del proyecto'
        },
        {
            'nombre': 'Expresión Verbal',
            'porcentaje': 10.0,
            'puntos_maximos': 10,
            'descripcion': 'Claridad y calidad de la presentación oral'
        },
        {
            'nombre': 'Principio de Funcionamiento',
            'porcentaje': 15.0,
            'puntos_maximos': 10,
            'descripcion': 'Comprensión técnica y fundamentos teóricos'
        },
        {
            'nombre': 'Presentación',
            'porcentaje': 10.0,
            'puntos_maximos': 10,
            'descripcion': 'Calidad visual y organización'
        },
        {
            'nombre': 'Aplicación',
            'porcentaje': 20.0,
            'puntos_maximos': 10,
            'descripcion': 'Utilidad práctica y solución a problemas reales'
        },
        {
            'nombre': 'Creatividad',
            'porcentaje': 15.0,
            'puntos_maximos': 10,
            'descripcion': 'Enfoque único y pensamiento innovador'
        }
    ],
    'fecha_creacion': firestore.SERVER_TIMESTAMP,
    'creado_por': 'admin@ugb.edu.sv'
}

# Verificar suma de porcentajes
total = sum(c['porcentaje'] for c in rubrica_data['criterios'])
print(f"   📊 Suma de porcentajes: {total}%")

if total != 100.0:
    print(f"   ❌ ERROR: Los porcentajes no suman 100% (suma: {total}%)")
    exit(1)

# Guardar en Firestore
print("   💾 Guardando en Firebase...")
doc_ref = db.collection('rubricas').add(rubrica_data)
rubrica_id = doc_ref[1].id

print(f"\n✅ ¡RÚBRICA CREADA EXITOSAMENTE!")
print("=" * 60)
print(f"📋 ID: {rubrica_id}")
print(f"📋 Nombre: {rubrica_data['nombre']}")
print(f"📋 Año: {rubrica_data['anio']}")
print(f"📋 Criterios: {len(rubrica_data['criterios'])}")
print(f"📋 Estado: {'ACTIVA' if rubrica_data['activa'] else 'INACTIVA'}")
print("=" * 60)

# 3. Verificar que se guardó correctamente
print("\n🔍 Paso 3: Verificando lectura...")
rubrica_verificacion = db.collection('rubricas').document(rubrica_id).get()
if rubrica_verificacion.exists:
    datos = rubrica_verificacion.to_dict()
    print(f"   ✓ Rúbrica leída correctamente")
    print(f"   ✓ Tiene {len(datos.get('criterios', []))} criterios")
    print(f"   ✓ Estado activa: {datos.get('activa')}")
    
    # Mostrar criterios
    print("\n📋 Criterios de evaluación:")
    for i, c in enumerate(datos.get('criterios', []), 1):
        print(f"   {i}. {c['nombre']} - {c['porcentaje']}% ({c['puntos_maximos']} pts)")
else:
    print(f"   ❌ ERROR: No se pudo leer la rúbrica")
    exit(1)

print("\n" + "=" * 60)
print("🎉 ¡TODO LISTO!")
print("=" * 60)
print("\n👉 PRÓXIMOS PASOS:")
print("   1. Ve a tu navegador")
print("   2. Presiona Ctrl + Shift + R para recargar")
print("   3. La rúbrica debería aparecer ahora")
print("\n" + "=" * 60)