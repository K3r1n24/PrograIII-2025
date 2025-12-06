"""
Script para generar el hash de contraseña
Ejecuta: python generar_hash.py
"""

from werkzeug.security import generate_password_hash

# Cambia esta contraseña por la que quieras
PASSWORD = "Admin2025!"

# Generar hash
password_hash = generate_password_hash(PASSWORD)

print("="*60)
print("🔐 HASH DE CONTRASEÑA GENERADO")
print("="*60)
print(f"\nContraseña:    {PASSWORD}")
print(f"\nHash generado:\n{password_hash}")
print("\n" + "="*60)
print("📋 Copia el hash de arriba y pégalo en Firebase")
print("="*60)
