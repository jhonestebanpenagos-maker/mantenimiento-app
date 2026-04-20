# migrar_passwords.py
# Ejecutar UNA SOLA VEZ para hashear las contraseñas existentes
# Luego puedes borrar este archivo

import hashlib
from supabase import create_client

# =====================================================
# CONFIGURACIÓN: pon tus credenciales directamente aquí
# (solo para este script de migración, no va a producción)
# =====================================================
SUPABASE_URL = "https://fquudfxkybqylcgtbbin.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZxdXVkZnhreWJxeWxjZ3RiYmluIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQyNjE4MDYsImV4cCI6MjA3OTgzNzgwNn0.Wf5i2KEvzWXj3dwsY5HxBOp3AcOX82h6WytZ0bH3dHg"

def hashear_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def migrar():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. Traer todos los usuarios
    res = supabase.table("usuarios").select("id, nombre, password").execute()
    
    if not res.data:
        print("No se encontraron usuarios.")
        return
    
    print(f"Encontrados {len(res.data)} usuarios. Iniciando migración...\n")
    
    exitosos = 0
    fallidos = 0
    
    for user in res.data:
        uid       = user['id']
        nombre    = user['nombre']
        pass_actual = user['password']
        
        # Verificamos si ya está hasheada (SHA-256 siempre tiene 64 caracteres)
        if len(pass_actual) == 64:
            print(f"  ⏭️  {nombre} — ya está hasheada, omitiendo.")
            continue
        
        # Hashear y actualizar
        try:
            nuevo_hash = hashear_password(pass_actual)
            supabase.table("usuarios").update(
                {"password": nuevo_hash}
            ).eq("id", uid).execute()
            
            print(f"  ✅  {nombre} — migrada correctamente.")
            exitosos += 1
            
        except Exception as e:
            print(f"  ❌  {nombre} — ERROR: {e}")
            fallidos += 1
    
    print(f"\n{'='*40}")
    print(f"Migración completa.")
    print(f"  Exitosos : {exitosos}")
    print(f"  Fallidos : {fallidos}")
    print(f"  Omitidos : {len(res.data) - exitosos - fallidos}")
    print(f"{'='*40}")
    print("\nYa puedes borrar este archivo. No lo subas a producción.")

if __name__ == "__main__":
    migrar()
