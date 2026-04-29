# 📧 Cambios en el Sistema de Correo — Changelog

## Fecha: 2026-04-29

---

## 🔴 Problemas Identificados

### 1. Correos desaparecen al recargar la página
**Causa raíz:** Los correos descargados vivían solo en `st.session_state['_correos_pendientes']` (RAM del navegador). Al recargar la página, cerrar el navegador, o que Streamlit reinicie el session → se pierden completamente.

**No había tabla `emails_pendientes`** — solo existía `emails_procesados` (los que ya se gestionaron). Los que estaban "esperando decisión" no tenían respaldo en BD.

### 2. Botón "Revisar Correo" se cuelga infinitamente
**Causa raíz:** `descargar_correos_nuevos()` descargaba el RFC822 completo de cada correo (cuerpo + adjuntos + imágenes). Si un correo tenía un PDF de 5MB, `mail.fetch(msg_id, "(RFC822)")` se colgaba sin timeout. Con 20 correos, podía tardar 10+ minutos.

Además, `imaplib.IMAP4_SSL` ignora `socket.setdefaulttimeout()` en la conexión SSL inicial.

### 3. Correos en limbo (ni OT, ni descartados, ni avance)
**Causa raíz:** El filtro `_obtener_procesados()` consultaba `emails_procesados` y descartaba todo lo que apareciera ahí. Si algún flujo marcó un correo incorrectamente, desaparecía sin rastro. No había forma de ver qué correos estaban realmente en Gmail vs la BD.

### 4. Búsqueda limitada a 3 días
**Causa raíz:** `dias_atras=3` en `descargar_correos_nuevos()` significaba que solo se buscaban correos de los últimos 3 días. Correos más antiguos nunca aparecían.

---

## ✅ Soluciones Implementadas

### Commit 1: `17e39e6` — Persistencia + Auditoría
**Archivos:** `utils/email_monitor.py`, `views/ordenes/__init__.py`, `sql/emails_persistence.sql`

- **Tabla `emails_pendientes`**: persiste correos descargados en Supabase (upsert por message_id)
- **`_guardar_correo_pendiente()`**: guarda cada correo descargado en la tabla
- **`_obtener_pendientes_guardados()`**: restaura correos pendientes desde BD al recargar
- **`_eliminar_pendiente()`**: limpia de `emails_pendientes` al gestionar (Crear OT, Vincular, Descartar)
- **`barrido_base_datos_correos()`**: función de auditoría completa de la BD
- **`render_auditoria_correos()`**: pestaña "🔍 Auditoría" con métricas, desglose por acción, correos huérfanos
- **Restauración automática**: si `session_state` está vacío, carga pendientes desde BD
- **SQL de migración**: `sql/emails_persistence.sql`

### Commit 2: `a145fd4` — Timeout IMAP + Comparación Gmail vs BD
**Archivos:** `utils/email_monitor.py`, `views/ordenes/__init__.py`

- **`IMAP_TIMEOUT = 30`**: timeout global para operaciones IMAP
- **`_conectar_imap()`**: aplica timeout via `mail.socket().settimeout()`
- **`_fetch_con_timeout()`**: wrapper con timeout por operación fetch
- **`comparar_gmail_vs_bd()`**: compara headers de Gmail vs `emails_procesados` + `emails_pendientes`
- **`render_comparacion_gmail_bd()`**: pestaña "🔄 Comparar" con correos en limbo
- **`dias_atras`** subió de 3 a 7 días
- **Pestaña "🔄 Comparar"** en módulo de Órdenes → Supervisión

### Commit 3: `67e9c67` — Solo Headers + Contenido Bajo Demanda
**Archivos:** `utils/email_monitor.py`

- **`descargar_correos_nuevos()` reescrito**: SOLO descarga headers (`BODY[HEADER.FIELDS]`), nunca RFC822 completo
- **`cargar_contenido_correo()`**: descarga contenido completo de UN correo bajo demanda (timeout 30s)
- **`contenido_cargado` flag**: cada correo trackea si ya se descargó el contenido
- **Botón "⬇️ Cargar contenido completo"** dentro del expander de cada correo
- **Tarjeta muestra** "Contenido no cargado" si solo tiene headers
- **`select('INBOX', readonly=True)`** para operación de solo lectura

### Commit 4: `11283f8` — Diagnóstico Paso a Paso
**Archivos:** `utils/email_monitor.py`

- **Diagnóstico en tiempo real** al hacer clic en "Revisar Correo":
  1. Verificación de credenciales
  2. Conexión IMAP SSL
  3. Autenticación
  4. Selección de INBOX (muestra total de mensajes)
  5. Búsqueda con fallback: 7d → 30d → ALL
  6. Descarga de headers con progress bar
- Si falla en algún paso, muestra el error exacto

### Commit 5: `fc27bdc` — Fetch con Thread Timeout
**Archivos:** `utils/email_monitor.py`

- **Thread por correo**: cada fetch de header se ejecuta en un `ThreadPoolExecutor` con timeout de 12s
- Si un correo se cuelga, el thread se mata y continúa con el siguiente
- **`RFC822.HEADER`** en vez de `BODY[HEADER.FIELDS]` (más compatible con servidores)
- **Progress bar + contador** "Correo X/Y" en tiempo real
- **Cuenta errores/timeouts** y los reporta al final

---

## 📊 Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `utils/email_monitor.py` | Persistencia, descarga headers-only, contenido bajo demanda, diagnóstico, thread timeout, comparación Gmail vs BD, auditoría |
| `views/ordenes/__init__.py` | Pestañas "📧 Correo", "🔄 Comparar", "🔍 Auditoría" |
| `sql/emails_persistence.sql` | SQL para crear tablas `emails_pendientes` y `emails_procesados` |

---

## 🗄️ Tablas de Base de Datos

### `emails_pendientes` (NUEVA)
Correos descargados de Gmail pendientes de gestión.

```sql
CREATE TABLE emails_pendientes (
    message_id TEXT PRIMARY KEY,
    remitente TEXT,
    remitente_nombre TEXT,
    asunto TEXT,
    fecha_correo TEXT,
    cuerpo_corto TEXT,
    n_adjuntos INTEGER DEFAULT 0,
    leido BOOLEAN DEFAULT FALSE,
    descargado_en TIMESTAMPTZ DEFAULT NOW()
);
```

### `emails_procesados` (YA EXISTÍA)
Correos que ya fueron gestionados.

```sql
CREATE TABLE emails_procesados (
    message_id TEXT PRIMARY KEY,
    orden_id INTEGER,
    accion TEXT DEFAULT 'orden',  -- 'orden', 'avance', 'descartado'
    fecha_procesado TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 🔄 Flujo Actual

```
Usuario hace clic "🔄 Revisar Correo"
    │
    ├─ 1. Verifica credenciales de Gmail
    ├─ 2. Conecta a IMAP (timeout 30s)
    ├─ 3. Login
    ├─ 4. Selecciona INBOX (readonly)
    ├─ 5. Busca correos (7d → 30d → ALL)
    ├─ 6. Descarga SOLO HEADERS (thread por correo, timeout 12s)
    │      └─ Cada header se guarda en emails_pendientes (Supabase)
    │
    └─ Lista de correos aparece en el buzón
         │
         ├─ "📄 Ver contenido" → "⬇️ Cargar contenido" (descarga RFC822 de ESE correo)
         ├─ "✅ Crear Orden" → crea OT + marca en emails_procesados + limpia emails_pendientes
         ├─ "🔗 Vincular a OT" → vincula como avance + marca + limpia
         └─ "🗑️ Descartar" → marca como descartado + limpia
```

---

## ⚙️ Configuración Requerida

### secrets.toml
```toml
[gmail]
correo = "orion.mantenimientoapp@gmail.com"
password = "xxxx xxxx xxxx xxxx"  # Contraseña de aplicación de 16 caracteres
```

### Supabase
Ejecutar `sql/emails_persistence.sql` en el SQL Editor.

---

## 🐛 Problemas Conocidos Restantes

1. **`contenido_cargado` no se persiste** en `emails_pendientes` — al recargar, los correos muestran "Contenido no cargado" de nuevo (solo se pierde la vista, no los datos)
2. **RLS policies** pueden necesitar ajuste si se usa autenticación por usuario en vez de service key
3. **Correos muy antiguos** (>30 días) no aparecen en la búsqueda por defecto (configurable en la pestaña Comparar)
