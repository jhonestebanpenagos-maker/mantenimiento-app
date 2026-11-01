# 🍎 Auditoría y corrección de compatibilidad — Safari / iOS (iPhone, iPad)

**Fecha:** 2026-11-01
**Alcance:** Toda la interfaz visible de ORIÓN (CSS de los 4 temas, HTML inyectado con
`st.markdown`, iframes de `components.html`, visor de PDF, carga de fotos).
**Principio aplicado:** *corregir sin perder funcionalidad* — todos los cambios son
aditivos/degradación elegante; ninguna lógica de negocio fue modificada.

---

## 📊 Resumen de problemas encontrados y corregidos

| # | Problema | Dónde se manifiesta en Safari/iOS | Severidad | Estado |
|---|----------|-----------------------------------|-----------|--------|
| 1 | Títulos con gradiente podían quedar **invisibles** (texto transparente sin respaldo) | Pantalla de login, QR, todos los `h1/h2/h3` | 🔴 Alta | ✅ Corregido |
| 2 | `backdrop-filter` sin prefijo `-webkit-` (tarjetas sin efecto glass/rotas) | `.card-style` en los temas | 🟡 Media | ✅ Corregido |
| 3 | **Auto-zoom de iOS** al enfocar inputs < 16px (layout roto, sidebar desplazado) | Login, formularios de órdenes, búsqueda | 🔴 Alta | ✅ Corregido |
| 4 | PDF dentro de `<iframe>` **no renderiza en iOS Safari** (visor de documentos en blanco) | Visor de PDF de órdenes/activos | 🔴 Alta | ✅ Corregido |
| 5 | Correo HTML con tablas/imágenes anchas → **scroll horizontal infinito** en iPhone | Vista original del correo (Buzón, Correo, Bitácora) | 🟡 Media | ✅ Corregido |
| 6 | Scroll de contenedores sin momentum táctil (`-webkit-overflow-scrolling`) | Correos, tablas, divs con overflow | 🟢 Baja | ✅ Corregido |
| 7 | Estados `:hover` con `transform` se quedan **"pegados"** al tocar en iOS | Botones principales, pills de navegación, descargas | 🟡 Media | ✅ Corregido |
| 8 | Destello azul / retardo de doble tap al tocar botones y enlaces | Toda la app | 🟢 Baja | ✅ Corregido |
| 9 | Contenido tapado por el **notch / Dynamic Island** en iPhone | Pantallas en móvil | 🟡 Media | ✅ Corregido |
| 10 | Fotos de iPhone **giradas 90°** (EXIF ignorado por OpenCV / generación PDF) | Evidencias fotográficas, lectura de QR | 🟡 Media | ✅ Corregido |
| 11 | Palabras/URLs largas provocaban scroll horizontal | Markdown, captions | 🟢 Baja | ✅ Corregido |

---

## 🔧 Detalle técnico de cada corrección

### 1. Títulos con gradiente invisibles en WebKit 🔴
**Archivo:** `styles.css` (bloque "TEXTOS Y TARJETAS")

**Problema:** Los títulos usaban:
```css
h1, h2, h3 {
    background: linear-gradient(...);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;  /* ← texto sin color de relleno */
}
```
Si WebKit no pinta el recorte del gradiente sobre el texto (versiones antiguas de iOS,
iOS con "Aumentar contraste" activo, o contextos con stacking degradado), el texto
queda con relleno transparente **y desaparece por completo**. Es el fallo clásico de
"la app se ve en blanco en el iPhone".

**Corrección:**
- Se usa `background-image` + `background-clip: text` (estándar) además del prefijo.
- Se agrega `color: var(--pro-orange)` como color de respaldo visible.
- `@supports not ((-webkit-background-clip: text) or (background-clip: text))` → si el
  navegador no soporta el recorte, el título se pinta en naranja sólido.
- `@media (prefers-contrast: more)` → si el usuario activó "Aumentar contraste" en iOS,
  el título se pinta sólido (más legible y nunca invisible).

### 2. `backdrop-filter` sin prefijo WebKit 🟡
**Archivos:** `styles.css`, `styles_opcion_a.css`, `styles_opcion_b.css`

Safari exige `-webkit-backdrop-filter` (necesario hasta Safari 18). Se agregó el
prefijo **antes** del estándar; en Chrome/Edge/Firefox el comportamiento no cambia.

### 3. Auto-zoom de iOS al enfocar campos 🔴
**Archivos:** los 4 CSS (sección 6.1 nueva)

iOS Safari hace zoom automático cuando un input tiene `font-size < 16px`. Al hacer
zoom, el layout de Streamlit se desborda (el sidebar flotante tapa contenido, los
botones quedan fuera de pantalla) y la app "no funciona". Se fuerza `font-size: 16px`
en `input, textarea, select` **solo en pantallas ≤ 768px** (en escritorio nada cambia).

### 4. Visor de PDF en blanco en iOS 🔴
**Archivo:** `pdf_utils.py` → `render_pdf_viewer()`

**Problema:** el visor usaba `<iframe src="https://docs.google.com/gview?...">`.
iOS Safari no renderiza PDFs dentro de iframes y el visor embebido de Google falla
intermitentemente (bloqueo de embedding, URLs no codificadas).

**Corrección — cadena de degradación elegante (sin JS):**
1. `<object type="application/pdf">` → visor nativo (Chrome, Edge, Firefox, Safari desktop).
2. Si el navegador no puede renderizarlo (iOS), el contenido *fallback* del `<object>`
   muestra el visor embebido de Google (ahora con la URL **codificada** con `urllib.parse.quote`).
3. Si tampoco carga, un **botón "Abrir / Descargar PDF"** siempre visible (en iOS abre
   el visor nativo QuickLook).
4. Se mantiene el enlace "Abrir en pestaña nueva" y el expander "¿No se ve el documento?".

### 5–6. Visores de correo HTML 🟡
**Archivos:** `utils/email_audit.py`, `utils/email_unified.py`, `utils/email_monitor.py`

Los correos se muestran dentro de un `components.html` (iframe propio): el CSS de la
app no les llega. Se agregó dentro del iframe:
- `-webkit-overflow-scrolling: touch` → scroll con momentum en iOS.
- `overflow-wrap/word-break` → textos largos no desbordan.
- `<style>img,table{max-width:100%}</style>` → tablas/imágenes anchas de correos
  (Outlook) no generan scroll horizontal infinito.

### 7. Estados `:hover` pegados en táctiles 🟡
**Archivos:** los 4 CSS (sección 6.4 nueva)

En iOS, al tocar un botón con `:hover { transform: translateY(-2px) / scale(1.02) }`
la transformación se queda aplicada. Con `@media (hover: none)` se neutraliza
**solo el `transform`** en dispositivos táctiles; los colores de hover se conservan
(retroalimentación visual al tocar) y en escritorio/Chrome nada cambia.

### 8. Destello azul y doble tap 🟢
**Archivos:** los 4 CSS (sección 6.3 nueva)

`-webkit-tap-highlight-color: transparent` + `touch-action: manipulation` eliminan el
destello azul de iOS y el retardo de ~300 ms del doble tap en botones/enlaces.

### 9. Área segura del notch 🟡
**Archivos:** los 4 CSS (sección 6.5 nueva)

`padding: max(valor-original, env(safe-area-inset-*))` en `.block-container` (solo
móvil). En dispositivos sin notch no hay ningún cambio visual (el `max` elige el valor
original); en iPhone con notch el contenido deja de quedar bajo la cámara/isla.

### 10. Fotos de iPhone giradas 90° 🟡
**Archivos:** `utils/uploads.py` (`_normalizar_imagen_exif()` nueva), `utils/qr.py`

Las fotos de iPhone se guardan horizontales + etiqueta EXIF de orientación. OpenCV
(`leer_qr_imagen`), los PDF generados y varios visores ignoran EXIF → evidencias
giradas. Se hornea la rotación en los píxeles **una sola vez, antes de subir a
Cloudinary**, para que todo lo downstream quede correcto.

Seguridad de la transformación (verificado con pruebas):
- ✅ Rotación aplicada cuando hay etiqueta EXIF (probado con Orientation=6).
- ✅ GIFs animados quedan **intactos byte a byte** (no se aplana la animación).
- ✅ Bytes corruptos / formatos no soportados → se devuelven sin modificar (fallback).
- ✅ Si no hay etiqueta de orientación, los bytes originales se conservan.
- ✅ `leer_qr_imagen` mantiene su decodificación original como fallback si Pillow falla.

### 11. Scroll horizontal por textos largos 🟢
**Archivos:** los 4 CSS (sección 6.6 nueva) → `overflow-wrap: break-word` en contenedores
de markdown/caption.

---

## 🧪 Cómo verificar en un iPhone real

1. Desplegar los cambios y abrir la app en **Safari de iPhone**.
2. **Login:** enfocar el campo "Usuario" → ya **no** debe hacer zoom la pantalla.
3. **Títulos:** "ORIÓN", "ACCESO DE USUARIOS" y títulos de sección deben verse con
   degradado naranja→verde (o naranja sólido si el sistema tiene "Aumentar contraste").
4. **Tarjetas:** fondo glass con blur visible en la ficha del activo.
5. **PDF:** abrir un documento adjunto → debe mostrarse el PDF o, como mínimo, el botón
   rojo "Abrir / Descargar PDF" que abre el visor nativo de iOS.
6. **Correo:** abrir "Vista original" de un correo con tablas anchas → debe hacer scroll
   suave sin desbordarse horizontalmente.
7. **Fotos:** subir una foto tomada con el iPhone en vertical → debe verse vertical en la
   ficha del activo, en el QR y en los PDF.
8. **Botones:** tocar un botón → no debe quedar "encogido/levantado" después del toque.
9. **Notch:** en una app con Safari a pantalla completa, el último botón no debe quedar
   bajo la barra inferior de Safari.

---

## ⚠️ Limitaciones conocidas (no son bugs del código, son límites de la plataforma)

1. **iOS recarga la pestaña al volver de segundo plano.**
   Si el técnico cambia a la cámara/foto y vuelve a Safari después de un rato, iOS puede
   recargar la pestaña: Streamlit crea una sesión nueva y el usuario vuelve al login
   (se pierde lo no guardado en el formulario). Esto es comportamiento agresivo de
   gestión de memoria de Safari, no una incompatibilidad del CSS.
   *Recomendaciones:*
   - Indicar a los usuarios **"Agregar a pantalla de inicio"** (iOS mantiene mejor las
     PWA instaladas).
   - Guardar borradores frecuentemente (la app ya tiene borradores en Activos).
   - *Mejora futura:* persistir la sesión con un token de restauración validado en BD
     (el campo `session_token` de `auth.py` ya está reservado para eso).

2. **Compatibilidad mínima:** las reglas usan `gap` en flexbox (HTML inline de
   calendario/kanban), `env(safe-area-inset-*)` y `@media (hover: none)` → requieren
   **Safari 14.1+ / iOS 14.5+** (2021). Cualquier iPhone/iPad soportado por Apple en
   2026 cumple holgadamente.

3. **`flex gap` en HTML inline:** los bloques flex (`preventivos.py`, `kanban.py`,
   `charts.py`, etc.) usan `gap` con estilos inline. En Safari 14.1+ funciona sin
   cambios; para soportar iOS 14.0-14.4 habría que reescribir cada bloque con márgenes
   (alto riesgo de romper el layout actual, bajo beneficio) → **se decidió no tocar**.

4. **Color de la barra de direcciones (`theme-color`):** Streamlit controla el `<head>`
   de la página; no es posible inyectar `<meta name="theme-color">` desde el código
   Python. Solo afecta estética.

---

## 📁 Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `styles.css` | Títulos con fallback + prefijos + secciones 6.1–6.6 Safari/iOS |
| `styles_opcion_claro.css` | Secciones 6.1–6.6 Safari/iOS |
| `styles_opcion_a.css` | `-webkit-backdrop-filter` + secciones 6.1–6.6 |
| `styles_opcion_b.css` | `-webkit-backdrop-filter` + secciones 6.1–6.6 |
| `pdf_utils.py` | `render_pdf_viewer()` con `<object>` + fallbacks + URL codificada |
| `utils/uploads.py` | `_normalizar_imagen_exif()` + aplicación en `subir_imagen` / `subir_archivo_generico` |
| `utils/qr.py` | Corrección EXIF antes de decodificar QR (fallback al método original) |
| `utils/email_audit.py` | Scroll táctil + límite de ancho en visor de correo |
| `utils/email_unified.py` | Ídem |
| `utils/email_monitor.py` | Ídem |

**Verificaciones ejecutadas:** `py_compile` de los 6 archivos Python (sin errores),
balance de llaves de los 4 CSS, y pruebas unitarias del normalizador EXIF
(rotación aplicada ✔, GIF intacto ✔, bytes corruptos sin modificar ✔).

---

# 🔄 SEGUNDA RONDA — Rendimiento del Tablero + Sidebar en iPhone (2026-11-01)

Problemas reportados tras el primer despliegue: **(1)** el Tablero de Mando tardaba
demasiado en cargar; **(2)** el sidebar no funcionaba en Safari de iPhone.

## Problema 1 — Tablero lento 🔴

Causas encontradas y corregidas:

| Causa | Corrección | Archivo |
|-------|------------|---------|
| 5 consultas Supabase **secuenciales** en el primer render (~2-4 s) | Carga **en paralelo** con `ThreadPoolExecutor` y TTL 300→600 s | `views/dashboard.py` |
| Chequeo SLA con **envíos de Telegram síncronos** (hasta 10 s cada uno) que se repetía en cada recarga de pestaña (iOS crea sesión nueva) | Throttle de proceso: 1 chequeo cada 10 min + tope de 10 envíos por chequeo | `utils/notifications.py` |
| Generación del Excel en **cada rerun** (cada clic re-ejecuta el script y `@st.cache_data` recalculaba el hash de 3 DataFrames grandes) | Memorización por sesión con clave barata: se regenera solo cuando los datos cambian | `views/dashboard.py` |

Estimación: el primer render pasa de ~6-10 s a ~2-3 s (dominado por la latencia de
Supabase y el render de los ~10 gráficos Plotly en el navegador).

## Problema 2 — Sidebar no funciona en iPhone 🔴

**Causa raíz (CSS):** la regla heredada forzaba
`[data-testid="stHeader"], .stApp > header { z-index: 0 !important }`. La cabecera de
Streamlit contiene el botón "Open sidebar" (hamburguesa). Con `z-index: 0`, la
cabecera quedaba **debajo del contenido** — en móvil, `.block-container` tiene poco
`padding-top` (1.5rem) y el contenido se superpone a la zona de la cabecera → los
taps de iOS caían en el contenido y **el botón jamás recibía el toque**. En escritorio
funcionaba porque el contenido no se superpone al botón.

**Corrección (en `styles.css` y `styles_opcion_claro.css`):**
- Cabecera elevada a `z-index: 1000000` pero con `pointer-events: none` → nunca
  bloquea el contenido; solo sus botones (`pointer-events: auto`) reciben toques.
- Drawer del sidebar en móvil a `z-index: 1000001` + scroll táctil + botones
  tocables (regla 6.7 en los 4 temas).

**Verificación en iPhone:** tocar la hamburguesa debe abrir el sidebar; los botones del
menú deben navegar; el ✕ debe cerrarlo. Si el síntoma persiste, indicar si (a) el
botón hamburguesa no responde, (b) abre pero detrás del contenido, o (c) abre y los
botones del menú no navegan — cada caso tiene un diagnóstico distinto.
