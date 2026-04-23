# 🔍 AUDIT UX — ORIÓN Mantenimiento Inteligente
## Fecha original: 2026-04-22
## Última actualización: 2026-04-24

---

## 1. MAPA DE NAVEGACIÓN ACTUALIZADO

```
                        ┌──────────────────────────────────────────────┐
                        │              SIDEBAR (Menu fijo)             │
                        │  🔍 Búsqueda │ 📊 Tablero │ 🏗️ Jerarquía   │
                        │  📦 Inventario │ 🛠️ Órdenes │ 🔩 Repuestos  │
                        │  👤 Usuarios  │  ⬅️ Volver (sidebar)        │
                        └──────────────┬───────────────────────────────┘
                                       │
          ┌────────────────────────────┼─────────────────────────────┐
          │                            │                             │
    ┌─────▼─────┐            ┌────────▼────────┐          ┌────────▼────────┐
    │  BÚSQUEDA │            │    TABLERO      │          │   JERARQUÍA     │
    │  ⬅️Volver │            │  ⬅️ Volver      │          │  ⬅️ Volver      │
    │ "Ver ficha├───►Inv ✓  │  KPIs aislados  │          │ "Ver ficha" ├──►Inv ✓
    │ "Gestion" ├───►Ord ✓  │  Charts sin     │          │ "Ver OTs"   ├──►Ord ✓
    │ "Ver rep" ├───►Rep ✓  │  navegación     │          │                 │
    └───────────┘            └─────────────────┘          └─────────────────┘
          │
    ┌─────▼─────────────────────────────────────────────────────────┐
    │                     ÓRDENES (7 tabs)                         │
    │  ⬅️ Volver inline │ Historial de navegación ✓                │
    │                                                              │
    │ Crear Orden:                                                 │
    │   📎 Uploader unificado (correo + archivo) ✓                 │
    │   📧 Parseo automático .msg/.eml ✓                           │
    │   Layout: Selectores → Archivo → Form(descripción) ✓         │
    │                                                              │
    │ Kanban "Gestionar" ───► Gestión Global ✓                    │
    │ Interceptor "Volver" ──► usa volver_atras() ✓               │
    └──────────────────────────────────────────────────────────────┘
```

### Leyenda
- ✅ = Navegación funciona correctamente
- ⬅️ = Botón de volver inline implementado
- 🔄 = Corregido en sesión 2026-04-24

---

## 2. PROBLEMAS CRÍTICOS DE NAVEGACIÓN

### ✅ 2.1 — "Ver detalle" desde Búsqueda → Activo se selecciona correctamente
**Archivo:** `views/busqueda.py`
**Estado:** ✅ CORREGIDO (2026-04-24)
**Solución:** Usa `navegar_a("Inventario Activos", jump_target="activo", jump_id=a['id'])` que pasa por el sistema de historial. Al llegar, `views/activos.py` detecta el jump y renderiza `_render_ficha_activo()` directamente.

### ✅ 2.2 — "Ver ficha" desde Jerarquía → Activo se selecciona correctamente
**Archivo:** `views/activos.py` (_render_jerarquia)
**Estado:** ✅ CORREGIDO (ya funcionaba, verificado)
**Solución:** Usa `navegar_a()` con jump_target="activo".

### ✅ 2.3 — "Ver repuestos" desde Búsqueda → Repuesto se selecciona correctamente
**Archivo:** `views/busqueda.py`
**Estado:** ✅ CORREGIDO (ya funcionaba, verificado)
**Solución:** Usa `navegar_a("Repuestos", jump_target="repuesto", jump_id=r['id'])`.

### ✅ 2.4 — Interceptor de Órdenes: "Volver" usa historial
**Archivo:** `views/ordenes.py`
**Estado:** ✅ CORREGIDO (2026-04-24)
**Solución:** Botón hardcodeado reemplazado por `render_back_button()` que usa `volver_atras()` del historial de navegación. Ya no va siempre a Inventario.

### 🔴 2.5 — Tablero de Mando: CERO links a otros módulos
**Archivo:** `views/dashboard.py`
**Estado:** 🔴 SIN CAMBIOS
**Problema:** Los KPIs, gráficos y métricas siguen siendo estáticos. No se puede clickear en una orden del "Top 10" para gestionarla.

### ✅ 2.6 — Inventario de Activos: Se puede ver Órdenes desde un activo
**Archivo:** `views/activos.py` (_render_ficha_activo)
**Estado:** ✅ CORREGIDO (ya existía, verificado)
**Solución:** La ficha del activo muestra órdenes relacionadas con botón "⚙️ Gestionar" que navega a la orden. También hay "📋 Ver todas las órdenes de este activo".

### ✅ 2.7 — Botón de volver inline implementado
**Estado:** ✅ CORREGIDO (2026-04-24)
**Solución:** Nuevo componente `utils/nav_button.py` → `render_back_button()`. Se muestra arriba del contenido en todas las páginas con label dinámico (ej: "⬅️ Volver a 🔍 Búsqueda"). Integrado en: Búsqueda, Dashboard, Activos, Órdenes, Repuestos, Usuarios.

### ✅ 2.8 — Vista detalle de Activo (Ficha) implementada
**Archivo:** `views/activos.py` (_render_ficha_activo)
**Estado:** ✅ CORREGIDO (ya existía, verificado)
**Solución:** Vista de solo-lectura con foto, datos principales, especificaciones, QR, órdenes relacionadas, KPIs de OTs, y botones de navegación cross-link.

---

## 3. PROBLEMAS DE USABILIDAD

### ✅ 3.1 — Navegación rota por session_state directo
**Estado:** ✅ CORREGIDO (2026-04-24)
**Problema:** Varias vistas hacían `st.session_state.jump_target = X; st.rerun()` directamente, sin pasar por `navegar_a()`. Esto rompía el historial de navegación.
**Solución:** Reemplazado por `navegar_a()` en:
- `views/activos.py` búsqueda rápida (1 caso)
- `views/ordenes.py` ordenes_por_activo (4 casos)
- `views/ordenes.py` kanban → gestionar (ya usaba navegar_a, verificado)

### 🟡 3.2 — Ordenes tiene 7 tabs en una fila
**Estado:** 🟡 SIN CAMBIOS
**Problema:** Las 7 tabs se comprimen en pantallas pequeñas.

### 🟡 3.3 — Búsqueda Global: mínimo 2 caracteres, sin sugerencias
**Estado:** 🟡 SIN CAMBIOS
**Problema:** No hay autocompletado ni sugerencias mientras escribes.

### 🟡 3.4 — Bitácora en Gestión Global: contenedor con scroll fijo de 500px
**Estado:** 🟡 SIN CAMBIOS
**Archivo:** `views/ordenes.py`

### 🟡 3.5 — Tablero: gráficos se apilan verticalmente, mucho scroll
**Estado:** 🟡 SIN CAMBIOS

### 🟡 3.6 — Time tracker y Costos están en expanders ocultos
**Estado:** 🟡 SIN CAMBIOS

### ✅ 3.7 — Activo nuevo no aparecía en listados de órdenes
**Estado:** ✅ CORREGIDO (2026-04-24)
**Problema:** Las escrituras en `activos.py` usaban `supabase.table().insert/update/delete` directamente, sin pasar por `db_insert/db_update/db_delete`. Nunca se llamaba `invalidate_cache()`, así que `run_query('activos')` devolvía datos viejos con TTL de 5 minutos.
**Solución:** 6 llamadas directas reemplazadas por los helpers con invalidación automática.

### ✅ 3.8 — DuplicateWidgetID al ingresar a orden en curso
**Estado:** ✅ CORREGIDO (2026-04-24)
**Problema:** `render_back_button()` se llamaba dos veces en el mismo ciclo de render (en `render()` y en `_render_interceptor()`).
**Solución:** Llamadas mutuamente excluyentes — solo en la sección de tabs (ruta normal) O en el interceptor (ruta de enfoque).

---

## 4. NUEVAS FUNCIONALIDADES (2026-04-24)

### ✅ 4.1 — Parseo automático de correos electrónicos
**Archivos nuevos:** `utils/email_parser.py`
**Dependencia nueva:** `extract-msg>=0.41.0` en `requirements.txt`
**Descripción:** Al subir un archivo .msg (Outlook) o .eml en el formulario de crear orden:
- Se parsea automáticamente (remitente, asunto, fecha, cuerpo)
- Se rellena el campo Descripción con el contenido formateado
- Se muestra preview del correo (De, Asunto, cuerpo expandible)
- Detecta adjuntos del correo y los lista
- El archivo .msg/.eml también se sube como adjunto a la bitácora

### ✅ 4.2 — Uploader unificado (correo + archivo)
**Archivo:** `views/ordenes.py` (_render_archivo_unificado)
**Descripción:** Un solo campo "📎 Adjunto" que detecta automáticamente si es correo o archivo normal:
- Si es .msg/.eml → parsea con callback, rellena descripción, muestra preview
- Si es PDF/Excel/foto → lo marca como adjunto normal
- Integrado en: Crear orden directa + Crear orden para activo específico

### ✅ 4.3 — Layout reestructurado en 3 pasos
**Descripción:** Formulario de crear orden dividido en:
1. Selectores (Activo, Tipo, Criticidad)
2. Uploader unificado (correo/archivo)
3. Form (Descripción + Técnico + Submit)
Esto permite que el uploader quede visualmente entre Tipo y Descripción.

---

## 5. SUGERENCIAS RESTANTES

### Prioridad Alta (pendientes)
1. ~~Sistema de navegación con contexto~~ ✅ Implementado
2. ~~Foco automático al navegar~~ ✅ Implementado
3. **Links desde Tablero** — Hacer clickeables los tops, técnicos, KPIs (🔴 pendiente)
4. ~~Vista detalle de Activo~~ ✅ Implementado
5. ~~Cross-links Activos ↔ Órdenes~~ ✅ Implementado

### Prioridad Media (pendientes)
6. ~~Breadcrumbs~~ ✅ Implementado en ficha de activo
7. **Reducir tabs de Órdenes** — Agrupar en secciones lógicas (🟡 pendiente)
8. **Resumen ejecutivo en Tablero** — 4 KPIs + 1 gráfico arriba (🟡 pendiente)
9. **Búsqueda con sugerencias** — Autocompletado mientras escribes (🟡 pendiente)
10. **Historial de navegación** — "Últimos vistos" en sidebar (🟡 pendiente, ya existe parcialmente)

### Prioridad Baja (pendientes)
11. **Keyboard shortcuts** — Ctrl+K para búsqueda global
12. **Modo compacto** — Toggle para pantallas pequeñas
13. **Exportar vista actual** — PDF/Excel de lo que se está viendo

---

## 6. ESTADÍSTICAS DE LA SESIÓN 2026-04-24

| Métrica | Valor |
|---------|-------|
| Commits realizados | 8 |
| Archivos creados | 2 (nav_button.py, email_parser.py) |
| Archivos modificados | 8 |
| Problemas corregidos | 8 |
| Nuevas funcionalidades | 3 |
| Problemas restantes | 8 de 21 originales |
