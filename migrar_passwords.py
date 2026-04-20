# migrar_passwords.py
import hashlib
import os
from supabase import create_client

# Lee las credenciales desde variables de entorno
# (GitHub Actions las inyecta automáticamente desde los Secrets)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def hashear_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def migrar():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ ERROR: No se encontraron las variables de entorno.")
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    res = supabase.table("usuarios").select("id, nombre, password").execute()
    
    if not res.data:
        print("No se encontraron usuarios.")
        return
    
    print(f"Encontrados {len(res.data)} usuarios. Iniciando migración...\n")
    
    exitosos = 0
    fallidos = 0
    
    for user in res.data:
        uid         = user['id']
        nombre      = user['nombre']
        pass_actual = user['password']
        
        # Si ya tiene 64 caracteres, ya está hasheada
        if len(str(pass_actual)) == 64:
            print(f"  ⏭️  {nombre} — ya hasheada, omitiendo.")
            continue
        
        try:
            nuevo_hash = hashear_password(str(pass_actual))
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

if __name__ == "__main__":
    migrar()
