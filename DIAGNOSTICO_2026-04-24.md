# 🔍 DIAGNÓSTICO COMPLETO — ORIÓN Mantenimiento Inteligente
## Fecha: 2026-04-24
## Versión analizada: Última en `main` (post-sesión de mejoras 2026-04-22/24)

---

## 📊 RESUMEN EJECUTIVO

| Aspecto | Estado | Puntuación |
|---------|--------|------------|
| Arquitectura general | 🟡 Buena con deudas técnicas | 7/10 |
| Seguridad | 🟡 Aceptable, mejoras necesarias | 6/10 |
| UX / Navegación | 🟢 Buena tras mejoras recientes | 8/10 |
| Rendimiento | 🟡 Problemas de caché y queries | 5/10 |
| Mantenibilidad | 🟡 Archivos monolíticos | 6/10 |
| Funcionalidad | 🟢 Completa y bien pensada | 8/10 |
| **PROMEDIO** | | **6.7/10** |

---

## 1. 🏗️ ARQUITECTURA Y ESTRUCTURA

### ✅ Lo que está BIEN
- **Separación en módulos**: `views/`, `utils/`, `config.py`, `auth.py` — estructura limpia
- **Sistema de caché con invalidación**: `db.py` tiene `db_insert/update/delete` que invalidan automáticamente
- **Navegación con historial**: `navegar_a()` / `volver_atras()` funciona correctamente
- **Temas soportados**: Selector con persistencia en archivo local
- **Bot de Telegram separado**: `bot_telegram.py` corre independiente con Flask keep-alive

### 🔴 PROBLEMAS CRÍTICOS

#### 1.1 — `ordenes.py` es un archivo MONOLÍTICO (~900+ líneas)
**Riesgo:** Mantenibilidad, merge conflicts, difícil de testear
**Detalle:** Contiene 7 tabs, interceptor, kanban, buzón, calidad, gestión global, crear, preventivos, calendario — todo en un solo archivo
**Solución propuesta:** Dividir en sub-módulos:
```
views/ordenes/
  __init__.py        → render() principal
  kanban.py          → _render_kanban()
  calidad.py         → _render_calidad()
  gestion_global.py  → _render_gestion_global()
  crear.py           → _render_crear_directa() + _render_crear_para_activo()
  preventivos.py     → _render_preventivos() + calendario
  buzón.py           → _render_buzon()
  mis_gestiones.py   → _render_mis_gestiones()
  interceptor.py     → _render_interceptor()
  helpers.py         → _generar_adjunto_html(), _render_archivo_unificado()
```

#### 1.2 — `charts.py` tiene doble decorador `@st.cache_data`
**Archivo:** `utils/charts.py` línea ~157
**Problema:** `_calcular_tendencia_semanal` tiene `@st.cache_data` duplicado
```python
@st.cache_data(ttl=300, show_spinner=False)
@st.cache_data(ttl=300, show_spinner=False)  # ← DUPLICADO
def _calcular_tendencia_semanal(...):
```
**Solución:** Eliminar uno de los dos decoradores

#### 1.3 — `semaforo_tecnicos()` NO navega al técnico correcto
**Archivo:** `utils/charts.py` función `semaforo_tecnicos()`
**Problema:** El botón "Ver órdenes" hace `jump_target="ordenes_por_activo"` con `jump_id=None`, lo que no filtra por técnico
**Solución:** Implementar filtro por técnico en la vista de órdenes, o al menos navegar a "Mis Gestiones" con contexto del técnico seleccionado

#### 1.4 — `mostrar_tops_ordenes()` usa `st.session_state` directo en vez de `navegar_a()`
**Archivo:** `utils/charts.py` líneas en `mostrar_tops_ordenes()`
**Problema:** Hace `st.session_state.current_page = ...; st.rerun()` directamente, saltándose el historial de navegación
**Solución:** Reemplazar por `navegar_a("Ordenes de Trabajo", jump_target="orden", jump_id=item['id'])`

---

## 2. 🔒 SEGURIDAD

### ✅ Lo que está BIEN
- **bcrypt para passwords** con migración automática desde SHA-256
- **Política de contraseñas**: mínimo 8 chars, mayúscula, minúscula, dígito
- **Bloqueo por intentos fallidos**: 3 intentos → 5 minutos de bloqueo
- **Sesiones con expiración**: máximo 8 horas
- **Auditoría de acciones críticas**: login, eliminaciones, cambios de rol
- **Mensajes genéricos en login**: no revela si el usuario existe

### 🔴 PROBLEMAS CRÍTICOS

#### 2.1 — Token de Telegram visible en `notificar_telegram()`
**Archivo:** `utils/notifications.py`
**Problema:** Se accede a `st.secrets["telegram"]["bot_token"]` y se parsea con split. Si hay un error, el token podría aparecer en logs
**Solución:** Envolver en try/except y nunca logear el token

#### 2.2 — No hay CSRF protection en formularios Streamlit
**Riesgo:** Bajo (Streamlit maneja esto internamente), pero los formularios críticos (eliminar, cambiar rol) no tienen confirmación adicional más allá de un botón
**Solución:** Agregar campo de confirmación "Escriba ELIMINAR para confirmar" en acciones destructivas

#### 2.3 — `supabase.table().execute()` directo en `bot_telegram.py`
**Archivo:** `bot_telegram.py`
**Problema:** El bot de Telegram usa las credenciales de Supabase directamente sin las capas de validación de `db.py`
**Solución:** Compartir la capa de acceso a datos o al menos usar las mismas credenciales con validación

#### 2.4 — El bot de Telegram no valida permisos por rol
**Archivo:** `bot_telegram.py`
**Problema:** Cualquier usuario de Telegram puede crear solicitudes sin autenticación
**Riesgo:** Medio — alguien podría spamme solicitudes al buzón
**Solución:** Implementar whitelist de chat_ids autorizados, o vincular chat_id de Telegram con usuario del sistema

#### 2.5 — Archivo `.tema_actual` se escribe en el directorio del proyecto
**Archivo:** `config.py`
**Problema:** Si el directorio no tiene permisos de escritura, falla silenciosamente. También podría ser un vector si alguien modifica el archivo
**Solución:** Usar `st.session_state` como primario (ya lo hace) y considerar directorio de datos del usuario

### 🟡 MEJORAS SUGERIDAS

#### 2.6 — Rate limiting en endpoints públicos (QR)
**Problema:** El acceso QR (`?id_activo_qr=X`) no tiene rate limiting. Alguien podría escanear IDs secuencialmente
**Solución:** Agregar throttling o verificar que el ID existe en un rango válido

#### 2.7 — Logs de auditoría solo en archivo local
**Problema:** Si el servidor se reinicia, se pierden. No hay backup
**Solución:** Enviar logs críticos también a Supabase (tabla `audit_log`)

---

## 3. 🚀 RENDIMIENTO

### 🔴 PROBLEMAS CRÍTICOS

#### 3.1 — `_cargar_datos_dashboard()` carga 5 tablas completas
**Archivo:** `views/dashboard.py`
**Problema:** Cada carga del tablero descarga TODAS las órdenes, TODOS los usuarios, TODAS las solicitudes, TODOS los activos y TODOS los planes. Con miles de registros, esto será lento
**Solución:**
- Usar queries paginadas o agregaciones en el servidor (Supabase RPC)
- Calcular KPIs directamente en SQL en vez de en Python
- Separar carga de datos del dashboard en componentes lazy-load

#### 3.2 — `run_query()` descarga tablas completas sin límite
**Archivo:** `utils/db.py`
**Problema:** `run_query("ordenes")` trae TODAS las órdenes de la base de datos. No hay paginación por defecto
**Solución:** Agregar `limit()` por defecto o hacer obligatorio el uso de `run_query_paginated()` para tablas grandes

#### 3.3 — `charts.py` recalcula datos en cada render a pesar del caché
**Problema:** Las funciones `_calcular_kpis`, `_calcular_datos_tecnicos`, `_calcular_semaforo` usan `_df_hash(df)` que solo retorna `len(df)`. Si dos tablas tienen el mismo número de filas pero datos diferentes, el caché retornaría datos incorrectos
**Solución:** Usar un hash real del DataFrame (por ejemplo, hash del tuple de valores) o incluir timestamp de última actualización

#### 3.4 — El calendario de preventivos itera todos los planes en Python
**Archivo:** `views/ordenes.py` → `_render_calendario_preventivo()`
**Problema:** Para cada plan, calcula fechas manualmente con while loops. Con muchos planes, es O(n*m) donde m es el número de instancias por plan
**Solución:** Pre-calcular solo las fechas del mes actual, no todas las instancias históricas

#### 3.5 — Carga de `df_users` en múltiples vistas simultáneamente
**Problema:** `run_query("usuarios")` se llama en: `app.py`, `dashboard.py`, `ordenes.py`, `activos.py`, `repuestos.py`, `usuarios.py`. Aunque hay caché, el TTL de 5 minutos significa que se recalcula frecuentemente
**Solución:** Centralizar la carga de datos de usuario en `app.py` y pasar como parámetro, o usar `@st.cache_resource` para datos que cambian raramente

### 🟡 MEJORAS SUGERIDAS

#### 3.6 — `mostrar_imagen_cloudinary()` tiene 4 intentos secuenciales
**Problema:** Si la imagen de Cloudinary falla, hace 4 intentos HTTP (st.image, requests, URL limpia, HTML). Cada uno puede esperar hasta 15 segundos
**Solución:** Reducir timeouts y usar el intento HTML como primera opción (carga desde el navegador del usuario, no desde el servidor)

#### 3.7 — Generación de Excel en el tablero es bloqueante
**Problema:** `generar_excel_cached()` se llama inline en el render del dashboard. Si hay muchos datos, bloquea la UI
**Solución:** Mover a un botón que genere bajo demanda, o pre-generar en background

---

## 4. 🎨 UX Y NAVEGACIÓN

### ✅ Lo que está BIEN
- **Sistema de historial de navegación**: funciona correctamente con `navegar_a()` / `volver_atras()`
- **Botón de volver inline**: implementado en todas las vistas con label dinámico
- **Kanban visual**: 4 columnas con filtros por estado, criticidad y tipo
- **Búsqueda global**: busca en 3 entidades simultáneamente
- **Últimos accesos**: sidebar muestra items recientes
- **Sugerencia automática de técnico**: basada en carga de trabajo
- **Calendario preventivo**: visual con semáforo de estados

### 🔴 PROBLEMAS

#### 4.1 — Tablero de Mando: CERO links a otros módulos
**Archivo:** `views/dashboard.py`
**Estado:** 🔴 SIN CAMBIOS desde auditoría anterior
**Problema:** Los KPIs, gráficos y métricas del tablero son estáticos. No se puede clickear en una orden del "Top 10" para gestionarla directamente
**Nota:** `mostrar_tops_ordenes()` SÍ tiene botones "⚙️" pero usan `st.session_state` directo (ver 1.4)
**Solución:** Hacer TODOS los elementos clickeables:
- KPI "OT en Ejecución" → navega a Órdenes filtradas por "Abierta"
- Top 10 más antiguas → click navega a la orden
- Técnico en semáforo → click navega a sus órdenes
- Gráfico de barras por técnico → click filtra por técnico

#### 4.2 — Órdenes tiene 7 tabs en una fila
**Estado:** 🟡 SIN CAMBIOS
**Problema:** En pantallas pequeñas, las 7 tabs se comprimen y son difíciles de leer
**Solución:** Agrupar en secciones lógicas:
- **Trabajo**: Mis Gestiones, Kanban, Crear
- **Supervisión**: Buzón, Calidad, Global
- **Programación**: Preventivos

#### 4.3 — Búsqueda: mínimo 2 caracteres, sin sugerencias
**Estado:** 🟡 SIN CAMBIOS
**Problema:** No hay autocompletado ni sugerencias mientras escribes
**Solución:** Implementar debounce + sugerencias en tiempo real después de 1 carácter

#### 4.4 — Bitácora en Gestión Global: contenedor con scroll fijo de 500px
**Estado:** 🟡 SIN CAMBIOS
**Problema:** En pantallas pequeñas, la bitácora queda muy comprimida
**Solución:** Usar `height="stretch"` o calcular dinámicamente

#### 4.5 — El login no tiene "Recordarme"
**Problema:** Cada vez que se cierra el navegador, hay que volver a hacer login
**Solución:** Implementar token persistente en cookies/localStorage con expiración configurable

#### 4.6 — No hay indicador de carga global
**Problema:** Al navegar entre páginas, no hay feedback visual de que se están cargando datos
**Solución:** Usar `st.spinner()` consistente en todas las vistas, o un skeleton loading

#### 4.7 — Los formularios no tienen validación en tiempo real
**Problema:** Solo se validan al enviar. El usuario no ve errores hasta que presiona el botón
**Solución:** Agregar validación inline con `st.text_input` y feedback inmediato

---

## 5. 🧪 CALIDAD DE CÓDIGO

### 🔴 PROBLEMAS

#### 5.1 — Imports circulares potenciales
**Ejemplo:** `utils/helpers.py` importa `from utils.db import supabase` dentro de funciones, no al inicio del módulo
**Problema:** Si `db.py` falla al importar, los errores se propagan de forma confusa
**Solución:** Hacer todos los imports al inicio del archivo, usar lazy loading solo si es absolutamente necesario

#### 5.2 — Variables no utilizadas y código muerto
**Ejemplos:**
- `views/ordenes.py` `_render_kanban`: variable `df_canceladas` calculada pero siempre vacía (no hay lógica para filtrar)
- `utils/charts.py`: función `_df_hash` usa `len(df)` que no es un hash real
- `bot_telegram.py`: variable `activo_id` en `start()` se usa sin validación de tipo

#### 5.3 — Manejo inconsistente de errores
**Problema:** Algunas vistas usan `error_amigable(e)`, otras usan `st.error()` directamente, otras hacen `print()` silencioso
**Solución:** Estandarizar: siempre usar `error_amigable()` para errores de usuario, y `_logger.error()` para debugging interno

#### 5.4 — `time.sleep()` en el flujo de UI
**Ejemplos:**
- `auth.py`: `time.sleep(1)` durante el login
- `ordenes.py`: múltiples `time.sleep(1)` y `time.sleep(1.5)` después de acciones
- `activos.py`: `time.sleep(1.5)` después de guardar
**Problema:** Bloquea la UI sin feedback. El usuario no sabe si algo está procesando
**Solución:** Eliminar sleeps innecesarios. Usar `st.spinner()` cuando hay operaciones lentas reales

#### 5.5 — F-strings con HTML embebido
**Problema:** Todo el HTML está embebido en f-strings de Python. Dificulta:
- Testing de la UI
- Cambios de diseño
- Reutilización de componentes
**Solución:** Crear funciones helper para componentes HTML comunes (tarjetas, badges, KPI cards)

---

## 6. 📦 DEPENDENCIAS Y COMPATIBILIDAD

### 🟡 ALERTAS

#### 6.1 — `fpdf==1.7.2` es legacy
**Problema:** FPDF1 no tiene soporte activo. FPDF2 es el sucesor
**Solución:** Migrar a `fpdf2>=2.7.0`

#### 6.2 — `supabase==1.2.0` es antiguo
**Problema:** La librería de Supabase para Python ha tenido múltiples actualizaciones con mejoras de rendimiento y seguridad
**Solución:** Actualizar a la última versión compatible

#### 6.3 — `runtime.txt` especifica Python 3.11
**Problema:** Python 3.12+ tiene mejoras de rendimiento significativas
**Solución:** Evaluar migración a Python 3.12

#### 6.4 — No hay `pyproject.toml` ni gestión de dependencias moderna
**Problema:** Solo `requirements.txt` sin hashes ni versiones exactas para todas las dependencias
**Solución:** Agregar hashes o usar `pip-tools` / `poetry` para reproducibilidad

---

## 7. 🔧 FUNCIONALIDAD FALTANTE

### Prioridad ALTA
1. **Links desde Tablero** — Los tops, KPIs y gráficos deben ser clickeables (🔴 pendiente)
2. **Exportar cualquier vista a PDF/Excel** — Solo el tablero tiene exportación Excel
3. **Notificaciones push** — Solo Telegram, sin notificaciones in-app persistentes
4. **Dashboard por rol** — Técnicos ven solo sus órdenes, Admin ve todo

### Prioridad MEDIA
5. **Filtros avanzados en Órdenes** — Por fecha, por técnico, por activo, rango de fechas
6. **Mas acciones masivas** — Cambiar estado de múltiples órdenes a la vez
7. **Historial de cambios** — Quién cambió qué y cuándo (tabla `audit_log` en BD)
8. **Adjuntar múltiples archivos** — Actualmente solo 1 por entrada de bitácora
9. **Dashboard de repuestos** — KPIs de rotación, valor de inventario, tendencias

### Prioridad BAJA
10. **Keyboard shortcuts** — Ctrl+K para búsqueda global
11. **Modo compacto** — Toggle para pantallas pequeñas
12. **Dark/Light mode automático** — Según preferencias del OS
13. **API REST** — Para integraciones con otros sistemas
14. **PWA** — Progressive Web App para acceso offline

---

## 8. 📋 PLAN DE MEJORAS RECOMENDADO

### Fase 1 — Estabilidad (1-2 días)
- [ ] Eliminar doble decorador en `charts.py`
- [ ] Corregir navegación en `mostrar_tops_ordenes()` → usar `navegar_a()`
- [ ] Corregir `semaforo_tecnicos()` para navegar correctamente
- [ ] Agregar validación de tipo en `bot_telegram.py` para `activo_id`
- [ ] Eliminar `time.sleep()` innecesarios

### Fase 2 — Seguridad (2-3 días)
- [ ] Rate limiting en acceso QR
- [ ] Confirmación "Escriba ELIMINAR" en acciones destructivas
- [ ] Whitelist de chat_ids en bot de Telegram
- [ ] Logs de auditoría a Supabase (no solo archivo local)
- [ ] Token de sesión en cookie persistente con expiración

### Fase 3 — Rendimiento (3-5 días)
- [ ] Agregar `limit()` por defecto en `run_query()`
- [ ] Calcular KPIs del dashboard en SQL (Supabase RPC)
- [ ] Corregir `_df_hash()` para usar hash real del DataFrame
- [ ] Lazy-load de componentes del dashboard
- [ ] Optimizar calendario preventivo (solo mes actual)

### Fase 4 — UX (5-7 días)
- [ ] Hacer Tablero de Mando completamente interactivo
- [ ] Reorganizar tabs de Órdenes en secciones
- [ ] Implementar autocompletado en búsquedas
- [ ] Agregar filtros avanzados en Órdenes
- [ ] Exportar cualquier vista a PDF/Excel

### Fase 5 — Arquitectura (7-10 días)
- [ ] Dividir `ordenes.py` en sub-módulos
- [ ] Extraer componentes HTML reutilizables
- [ ] Migrar a `fpdf2`
- [ ] Actualizar `supabase` a última versión
- [ ] Agregar `pyproject.toml` con dependencias pinnadas

---

## 9. 📊 CÓDIGO VS AUDITORÍA ANTERIOR

| Problema de auditoría 2026-04-22 | Estado actual |
|----------------------------------|---------------|
| 2.1 — Navegación Búsqueda → Activo | ✅ Corregido |
| 2.2 — Jerarquía → Ficha activo | ✅ Corregido |
| 2.3 — Búsqueda → Repuesto | ✅ Corregido |
| 2.4 — Interceptor Órdenes volver | ✅ Corregido |
| 2.5 — Tablero sin links | 🔴 **SIN CAMBIOS** |
| 2.6 — Activos → Órdenes | ✅ Corregido |
| 2.7 — Botón volver inline | ✅ Corregido |
| 2.8 — Vista detalle activo | ✅ Corregido |
| 3.1 — session_state directo | ✅ Corregido |
| 3.2 — 7 tabs Órdenes | 🟡 **SIN CAMBIOS** |
| 3.3 — Búsqueda sin sugerencias | 🟡 **SIN CAMBIOS** |
| 3.4 — Bitácora scroll fijo | 🟡 **SIN CAMBIOS** |
| 3.5 — Gráficos apilan vertical | 🟡 **SIN CAMBIOS** |
| 3.6 — Time tracker oculto | 🟡 **SIN CAMBIOS** |
| 3.7 — Cache stale en activos | ✅ Corregido |
| 3.8 — DuplicateWidgetID | ✅ Corregido |

**Resumen:** 8 de 16 problemas corregidos, 8 pendientes (todos de prioridad media-baja)

---

## 10. 🎯 CONCLUSIÓN

La aplicación ORIÓN está **funcionalmente completa** y bien pensada para un sistema de mantenimiento industrial. Las mejoras de la sesión anterior (navegación, caché, email parser, firma) elevaron significativamente la calidad.

**Las áreas más críticas ahora son:**
1. **Rendimiento** — Las queries sin límite y el dashboard que carga todo serán problemas reales con más datos
2. **Tablero interactivo** — Es la mejora de UX más impactante pendiente
3. **Mantenibilidad** — `ordenes.py` necesita dividirse antes de agregar más funcionalidad

**La seguridad es aceptable** para una app corporativa interna, pero necesita hardening antes de exposición pública.

---

*Diagnóstico generado automáticamente por análisis de código completo.*
*Próxima revisión sugerida: después de implementar Fase 1 y 2.*
