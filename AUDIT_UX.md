# 🔍 AUDIT UX — ORIÓN Mantenimiento Inteligente
## Fecha: 2026-04-22

---

## 1. MAPA DE NAVEGACIÓN ACTUAL

```
                        ┌──────────────────────────────────────────────┐
                        │              SIDEBAR (Menu fijo)             │
                        │  🔍 Búsqueda │ 📊 Tablero │ 🏗️ Jerarquía   │
                        │  📦 Inventario │ 🛠️ Órdenes │ 🔩 Repuestos  │
                        │  👤 Usuarios                                        │
                        └──────────────┬───────────────────────────────┘
                                       │
          ┌────────────────────────────┼─────────────────────────────┐
          │                            │                             │
    ┌─────▼─────┐            ┌────────▼────────┐          ┌────────▼────────┐
    │  BÚSQUEDA │            │    TABLERO      │          │   JERARQUÍA     │
    │           │            │  (sin links!)   │          │                 │
    │ "Ver det" ├───►Inv ✗  │  KPIs aislados  │          │ "Ver ficha" ├──►Inv ✗
    │ "Gestion" ├───►Ord ✓  │  Charts sin     │          │                 │
    │ "Ver rep" ├───►Rep ✗  │  navegación     │          │                 │
    └───────────┘            └─────────────────┘          └─────────────────┘
          │
    ┌─────▼─────────────────────────────────────────────────────────┐
    │                     ÓRDENES (7 tabs)                         │
    │ Mis Gestiones │ Kanban │ Buzón │ Calidad │ Gestión │ Crear │ Prev │
    │       │                                                      │
    │ Kanban "Gestionar" ───► Gestión Global ✓                    │
    │ Interceptor "Volver" ──► Inventario (hardcoded!) ✗           │
    │ Gestión Global ────────► Bitácora inline ✓                   │
    └──────────────────────────────────────────────────────────────┘
```

### Leyenda
- ✅ = Navegación funciona correctamente
- ✗ = Dead end / pierde contexto / no funciona

---

## 2. PROBLEMAS CRÍTICOS DE NAVEGACIÓN

### 🔴 2.1 — "Ver detalle" desde Búsqueda → Activo NO se selecciona
**Archivo:** `views/busqueda.py:65-66`
**Problema:** Al hacer clic en "Ver detalle" de un activo encontrado, navega a "Inventario Activos" pero aterriza en la tab "LISTA DE ACTIVOS" sin mostrar el activo específico.
**Impacto:** El usuario busca algo, le da clic, y llega a una lista genérica. No sabe qué pasó.

### 🔴 2.2 — "Ver ficha" desde Jerarquía → Activo NO se selecciona
**Archivo:** `views/jerarquia.py:116-117`
**Problema:** Idem arriba. Cambia a Inventario pero no focaliza el activo.

### 🔴 2.3 — "Ver repuestos" desde Búsqueda → Repuesto NO se selecciona
**Archivo:** `views/busqueda.py:134-135`
**Problema:** Cambia a Repuestos sin filtro ni foco en el repuesto buscado.

### 🔴 2.4 — Interceptor de Órdenes: "Volver" siempre va a Inventario
**Archivo:** `views/ordenes.py:75-78`
**Problema:** El botón "⬅️ VOLVER A EDICIÓN DE ACTIVO" siempre va a Inventario, incluso si el usuario llegó desde Kanban o Gestión Global.

### 🔴 2.5 — Tablero de Mando: CERO links a otros módulos
**Archivo:** `views/dashboard.py`
**Problema:** Los KPIs, gráficos y métricas son completamente estáticos. No se puede clickear en una orden del "Top 10 más antiguas" para gestionarla. No se puede clickear en un técnico del semáforo para ver sus órdenes. Los charts son decorativos.

### 🔴 2.6 — Inventario de Activos: No se puede ver las Órdenes de un activo
**Archivo:** `views/activos.py`
**Problema:** No hay ningún link desde un activo hacia sus órdenes de trabajo. El usuario tiene que ir manualmente a Órdenes y filtrar.

### 🟡 2.7 — No hay "breadcrumbs" ni historial de navegación
**Problema:** El usuario no sabe dónde está ni cómo volver. Solo tiene el sidebar.

### 🟡 2.8 — No hay modo "detalle" para Activos
**Problema:** Para ver un activo, hay que ir a la tab "EDITAR / QR", buscarlo por nombre en un dropdown, y recién ahí ver sus datos. No hay una vista de solo-lectura tipo ficha.

---

## 3. PROBLEMAS DE USABILIDAD

### 🟡 3.1 — Ordenes tiene 7 tabs en una fila
**Problema:** Las 7 tabs se comprimen en pantallas pequeñas y los nombres se cortan. Es difícil encontrar lo que buscas.

### 🟡 3.2 — Formulario de nuevo activo: draft_data no se limpia bien
**Problema:** Si el usuario empieza a crear un activo y cambia de tab, los datos quedan. Pero si refresca la página, se pierden. Comportamiento inconsistente.

### 🟡 3.3 — Búsqueda Global: mínimo 2 caracteres, sin sugerencias
**Problema:** No hay autocompletado ni sugerencias mientras escribes. Tampoco recuerda búsquedas recientes.

### 🟡 3.4 — Bitácora en Gestión Global: contenedor con scroll fijo de 500px
**Archivo:** `views/ordenes.py:825`
**Problema:** `st.container(height=500)` crea un scroll interno que es confuso en Streamlit (el scroll de la página y el del container se mezclan).

### 🟡 3.5 — Tablero: gráficos se apilan verticalmente, mucho scroll
**Problema:** El dashboard tiene 6+ secciones de gráficos que requieren mucho scroll. No hay resumen ejecutivo compacto arriba.

### 🟡 3.6 — Time tracker y Costos están en expanders ocultos
**Problema:** Funcionalidades importantes (cuánto tiempo trabajaste, cuánto costó) están escondidas dentro de "Mis Gestiones" y requieren expandir varias secciones para verlas.

---

## 4. SUGERENCIAS DE MEJORA

### Prioridad Alta
1. **Sistema de navegación con contexto** — Guardar de dónde vino el usuario para volver correctamente
2. **Foco automático al navegar** — Al llegar desde búsqueda/jerarquía, abrir la tab correcta y seleccionar el item
3. **Links desde Tablero** — Hacer clickeables los tops, técnicos, KPIs
4. **Vista detalle de Activo** — Nueva tab "🔍 Ficha" con todos los datos + órdenes relacionadas
5. **Cross-links Activos ↔ Órdenes** — Desde activo ver sus OTs, desde OT ver ficha del activo

### Prioridad Media
6. **Breadcrumbs** — Mostrar "Inicio > Inventario > Activo #42" arriba
7. **Reducir tabs de Órdenes** — Agrupar en secciones lógicas
8. **Resumen ejecutivo en Tablero** — 4 KPIs + 1 gráfico arriba, detalles abajo
9. **Búsqueda con sugerencias** — Autocompletado mientras escribes
10. **Historial de navegación** — "Últimos vistos" en sidebar

### Prioridad Baja
11. **Keyboard shortcuts** — Ctrl+K para búsqueda global
12. **Modo compacto** — Toggle para pantallas pequeñas
13. **Exportar vista actual** — PDF/Excel de lo que se está viendo
