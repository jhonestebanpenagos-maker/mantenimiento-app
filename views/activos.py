import streamlit as st
import pandas as pd
import time
import io
import base64
import html as html_module
from datetime import datetime
from PIL import Image
from utils.db import supabase, run_query, render_paginacion
from utils.helpers import mostrar_notificaciones, agregar_notificacion, registrar_accion_critica, error_amigable
from utils.uploads import subir_imagen, mostrar_imagen_cloudinary
from utils.helpers import navegar_a
from utils.qr import generar_qr_activo
from utils.catalogos import AREAS_DATA, CATEGORIAS_ACTIVOS
from pdf_utils import generar_hoja_vida_pdf


CATEGORIAS_LIST = CATEGORIAS_ACTIVOS



def render():
    st.title("📦 ACTIVOS")
    mostrar_notificaciones()

    df_act = pd.DataFrame(run_query("activos"))

    if 'specs_data' not in st.session_state:
        st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
    if 'draft_data' not in st.session_state:
        st.session_state.draft_data = {}

    # ── Manejar navegación desde búsqueda ──
    jump = st.session_state.get('jump_target')
    jump_id = st.session_state.get('jump_id')

    if jump == "activo" and jump_id:
        st.session_state.jump_target = None
        st.session_state.jump_id = None
        activo_sel = df_act[df_act['id'] == int(jump_id)] if not df_act.empty else pd.DataFrame()
        if not activo_sel.empty:
            _render_ficha_activo(activo_sel.iloc[0])
            st.markdown("---")
            if st.button("📋 Ver lista completa de activos", use_container_width=True):
                st.rerun()
            return
        else:
            st.error(f"Activo #{jump_id} no encontrado.")
            st.markdown("---")

    # ── Búsqueda rápida integrada ──
    _render_busqueda_rapida()

    # ── Navegación con tabs ──
    tab_lista, tab_jerarquia, tab_nuevo, tab_edit = st.tabs([
        "📋 Lista", "🏗️ Jerarquía", "➕ Nuevo", "✏️ Editar / QR"
    ])

    with tab_lista:
        _render_lista(df_act)

    with tab_jerarquia:
        _render_jerarquia(df_act)

    with tab_nuevo:
        _render_nuevo(df_act)

    with tab_edit:
        _render_edit(df_act)


# ==============================================================================
# 📋 LISTA DE ACTIVOS
# ==============================================================================
def _render_lista(df_act):
    if not df_act.empty:
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        col_kpi1.metric("Total Activos", len(df_act))
        col_kpi2.metric("Áreas Activas", df_act['area'].nunique())
        col_kpi3.metric("Categorías", df_act['categoria'].nunique())
        con_foto = df_act['foto_url'].notnull().sum()
        col_kpi4.metric("Con Fotografía", f"{con_foto}/{len(df_act)}")

        st.markdown("---")
        st.markdown("#### 🔍 Explorador de Activos")
        c_fil1, c_fil2, c_fil3, c_fil4 = st.columns([2, 1, 1, 1])
        search_term = c_fil1.text_input("Buscar por nombre", placeholder="Escribe y presiona Enter...")
        area_opts = ["Todas"] + sorted(AREAS_DATA.keys())
        filtro_area = c_fil2.selectbox("Filtrar Área", area_opts)
        sub_opts = ["Todas"] + (sorted(AREAS_DATA[filtro_area]) if filtro_area != "Todas" else [])
        filtro_sub = c_fil3.selectbox("Filtrar Sub-área", sub_opts)
        cat_opts = ["Todas"] + CATEGORIAS_LIST
        filtro_cat = c_fil4.selectbox("Filtrar Categoría", cat_opts)

        df_filtered = df_act.copy()
        if search_term:
            df_filtered = df_filtered[df_filtered['nombre'].str.contains(search_term, case=False, na=False)]
        if filtro_area != "Todas":
            df_filtered = df_filtered[df_filtered['area'] == filtro_area]
        if filtro_sub != "Todas":
            df_filtered = df_filtered[df_filtered['ubicacion'].str.contains(rf"\[{filtro_sub}\]", regex=True, na=False)]
        if filtro_cat != "Todas":
            df_filtered = df_filtered[df_filtered['categoria'] == filtro_cat]

        if not df_filtered.empty:
            st.markdown(f"###### 🧬 Resultados: {len(df_filtered)}")

            # Lightbox CSS + JS (una sola vez)
            st.markdown("""
            <style>
            .lb-overlay{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:9999;justify-content:center;align-items:center;cursor:pointer;backdrop-filter:blur(4px);}
            .lb-overlay:target{display:flex;}
            .lb-overlay img{max-width:90%;max-height:90%;border-radius:10px;box-shadow:0 0 40px rgba(0,0,0,0.5);}
            .lb-close{position:absolute;top:20px;right:30px;color:#fff;font-size:2rem;text-decoration:none;font-weight:bold;cursor:pointer;z-index:10000;}
            .lb-close:hover{color:#F59E0B;}
            .lb-caption{text-align:center;color:#D1D5DB;font-size:0.95rem;margin-top:12px;}
            </style>
            <script>
            document.addEventListener('keydown',function(e){if(e.key==='Escape'){var o=document.querySelector('.lb-overlay:target');if(o)window.location='#';}});
            </script>
            """, unsafe_allow_html=True)

            # Renderizar como tarjetas HTML con lightbox
            cards = []
            for _, row in df_filtered.iterrows():
                act_id = str(row["id"])
                foto_url = row.get("foto_url", "")
                qr_url = row.get("qr_url", "")
                nombre_escaped = html_module.escape(str(row["nombre"]))

                # Foto con lightbox
                if isinstance(foto_url, str) and foto_url.startswith("http"):
                    foto = (
                        f'<a href="#lb-{act_id}" style="display:block;cursor:pointer;">'
                        f'<img src="{foto_url}" style="width:100%;height:160px;object-fit:cover;border-radius:6px;transition:transform 0.2s;" '
                        f'onmouseover="this.style.transform=\'scale(1.02)\'" onmouseout="this.style.transform=\'none\'" />'
                        f'</a>'
                    )
                    # Modal de foto
                    foto_modal = (
                        f'<div id="lb-{act_id}" class="lb-overlay">'
                        f'<a class="lb-close" href="#">&times;</a>'
                        f'<div style="text-align:center;">'
                        f'<img src="{foto_url}" style="max-width:90vw;max-height:80vh;border-radius:10px;" />'
                        f'<div class="lb-caption">📷 {nombre_escaped}</div>'
                        f'</div></div>'
                    )
                else:
                    foto = '<div style="width:100%;height:160px;background:#1F2937;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#6B7280;font-size:2rem;">📷</div>'
                    foto_modal = ""

                # QR con lightbox
                if isinstance(qr_url, str) and qr_url.startswith("http"):
                    qr = (
                        f'<a href="#lb-qr-{act_id}" style="display:block;cursor:pointer;">'
                        f'<img src="{qr_url}" style="width:60px;height:60px;border-radius:4px;transition:transform 0.2s;" '
                        f'onmouseover="this.style.transform=\'scale(1.1)\'" onmouseout="this.style.transform=\'none\'" />'
                        f'</a>'
                    )
                    qr_modal = (
                        f'<div id="lb-qr-{act_id}" class="lb-overlay">'
                        f'<a class="lb-close" href="#">&times;</a>'
                        f'<div style="text-align:center;">'
                        f'<img src="{qr_url}" style="max-width:50vw;max-height:60vh;border-radius:10px;" />'
                        f'<div class="lb-caption">QR — {nombre_escaped}</div>'
                        f'</div></div>'
                    )
                else:
                    qr = ""
                    qr_modal = ""

                cat = html_module.escape(str(row.get("categoria", "N/A")))
                area = html_module.escape(str(row.get("area", "")))
                ubic = html_module.escape(str(row.get("ubicacion", "")))
                card = (
                    '<div style="background:#1F2937;border:1px solid #374151;border-radius:10px;overflow:hidden;">'
                    + foto
                    + '<div style="padding:12px;">'
                    + '<div style="display:flex;justify-content:space-between;align-items:start;">'
                    + '<div>'
                    + '<div style="color:#F3F4F6;font-weight:600;font-size:0.95rem;">' + nombre_escaped + '</div>'
                    + '<div style="color:#9CA3AF;font-size:0.8rem;margin-top:2px;">ID: ' + act_id + ' · ' + cat + '</div>'
                    + '</div>'
                    + qr
                    + '</div>'
                    + '<div style="margin-top:8px;font-size:0.8rem;color:#6B7280;">📍 ' + area + ' / ' + ubic + '</div>'
                    + '</div></div>'
                    + foto_modal + qr_modal
                )
                cards.append(card)
            grid = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;">' + "".join(cards) + "</div>"
            st.markdown(grid, unsafe_allow_html=True)
        else:
            if search_term or filtro_area != "Todas" or filtro_cat != "Todas":
                st.warning("⚠️ No se encontraron activos con estos filtros.")
    else:
        st.info("Aún no hay activos registrados.")


# ==============================================================================
# 🔍 BÚSQUEDA RÁPIDA INTEGRADA
# ==============================================================================
def _render_busqueda_rapida():
    """Barra de búsqueda rápida dentro de la página de Activos."""
    query = st.text_input(
        "🔍 Buscar activo",
        placeholder="Nombre, categoría o ubicación...",
        key="activos_search_input",
        label_visibility="collapsed"
    )
    if query and len(query.strip()) >= 2:
        query = query.strip()
        try:
            res_nom = supabase.table("activos").select("id, nombre, categoria, area, ubicacion, foto_url") \
                .ilike("nombre", f"%{query}%").limit(10).execute()
            res_cat = supabase.table("activos").select("id, nombre, categoria, area, ubicacion, foto_url") \
                .ilike("categoria", f"%{query}%").limit(10).execute()
            res_ubi = supabase.table("activos").select("id, nombre, categoria, area, ubicacion, foto_url") \
                .ilike("ubicacion", f"%{query}%").limit(10).execute()

            todos = {}
            for res in [res_nom, res_cat, res_ubi]:
                if res.data:
                    for item in res.data:
                        todos[item['id']] = item

            resultados = list(todos.values())
            if resultados:
                st.success(f"🔍 **{len(resultados)}** activo(s) encontrado(s)")
                cols = st.columns(min(len(resultados), 4))
                for i, a in enumerate(resultados[:8]):
                    with cols[i % 4]:
                        foto = a.get('foto_url', '')
                        if foto and isinstance(foto, str) and len(foto) > 10:
                            if not mostrar_imagen_cloudinary(foto, use_container_width=True):
                                st.markdown("🔧", unsafe_allow_html=True)
                        else:
                            st.markdown("<div style='text-align:center;font-size:2rem;padding:15px;background:#1F2937;border-radius:6px;'>🔧</div>", unsafe_allow_html=True)
                        st.caption(f"**{a['nombre']}**")
                        st.caption(f"📍 {a.get('area', 'N/A')}")
                        if st.button("Ver ficha", key=f"search_act_{a['id']}", use_container_width=True):
                            st.session_state.jump_target = "activo"
                            st.session_state.jump_id = a['id']
                            st.rerun()
                st.markdown("---")
            else:
                st.warning(f"🔍 Sin resultados para \"{query}\"")
        except Exception as e:
            st.caption(f"Error en búsqueda: {e}")


# ==============================================================================
# 🏗️ JERARQUÍA DE ACTIVOS (integrada)
# ==============================================================================
def _render_jerarquia(df_act):
    """Vista de jerarquía de la planta: Área → Sub-área → Equipo."""
    import re as re_module

    df_ordenes = run_query("ordenes")

    if df_act.empty:
        st.info("No hay activos registrados. Ve a la pestaña **Nuevo** para crear el primero.")
        return

    # Calcular métricas por ubicación
    mapa_ordenes_abiertas = {}
    if not df_ordenes.empty:
        abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta']
        mapa_ordenes_abiertas = abiertas.groupby('activo_id').size().to_dict()

    # KPIs generales
    total_activos = len(df_act)
    total_areas = len(AREAS_DATA)
    total_subs = sum(len(v) for v in AREAS_DATA.values())
    con_ordenes = len([a for a in df_act['id'] if a in mapa_ordenes_abiertas])

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🏢 Áreas", total_areas)
    k2.metric("📍 Sub-áreas", total_subs)
    k3.metric("🔧 Activos", total_activos)
    k4.metric("⚠️ Con OTs Abiertas", con_ordenes)

    st.markdown("---")

    # ── NAVEGACIÓN POR ÁREA ──
    for area_nombre, sub_areas in sorted(AREAS_DATA.items()):
        activos_area = df_act[df_act['area'] == area_nombre]
        n_activos = len(activos_area)
        ots_area = sum(1 for _, a in activos_area.iterrows() if a['id'] in mapa_ordenes_abiertas)

        area_icon = "🏭" if area_nombre == "Producción" else "🏢" if area_nombre == "Administración" else "📦" if area_nombre == "Ventas" else "🚚"

        with st.expander(f"{area_icon} {area_nombre}  —  {n_activos} activos  {'⚠️ ' + str(ots_area) + ' OTs' if ots_area > 0 else '✅'}", expanded=False):
            for sub_area in sorted(sub_areas):
                activos_sub = activos_area[
                    activos_area['ubicacion'].str.contains(
                        rf"\[{re_module.escape(sub_area)}\]", regex=False, na=False
                    )
                ]

                if activos_sub.empty:
                    st.markdown(f"""
                    <div style="padding:6px 12px;margin:2px 0;color:#6B7280;font-size:0.85rem;">
                        📍 {sub_area} <span style="font-size:0.75rem;">(vacía)</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    n_sub = len(activos_sub)
                    ots_sub = sum(1 for _, a in activos_sub.iterrows() if a['id'] in mapa_ordenes_abiertas)
                    badge = f"🔴 {ots_sub} OTs" if ots_sub > 0 else f"🟢 {n_sub} activos"

                    with st.expander(f"📍 {sub_area}  —  {badge}", expanded=False):
                        for _, activo in activos_sub.iterrows():
                            oid = activo['id']
                            tiene_ots = oid in mapa_ordenes_abiertas
                            n_ots = mapa_ordenes_abiertas.get(oid, 0)

                            icono_estado = "🔴" if tiene_ots else "🟢"
                            foto = activo.get('foto_url', '')

                            col_foto, col_info = st.columns([1, 4])
                            with col_foto:
                                if foto and isinstance(foto, str) and len(foto) > 10:
                                    if not mostrar_imagen_cloudinary(foto, use_container_width=True):
                                        st.caption("📷")
                                else:
                                    st.markdown("<div style='text-align:center;font-size:2rem;padding:20px;'>🔧</div>", unsafe_allow_html=True)

                            with col_info:
                                st.markdown(f"""
                                <div style="background:rgba(30,41,59,0.5);border-radius:8px;padding:12px;margin-bottom:8px;">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="color:#E5E7EB;font-weight:700;font-size:1rem;">{icono_estado} {activo['nombre']}</span>
                                        <span style="font-size:0.75rem;color:#9CA3AF;">ID: {oid}</span>
                                    </div>
                                    <div style="display:flex;gap:15px;margin-top:6px;font-size:0.8rem;color:#9CA3AF;">
                                        <span>🔧 {activo.get('categoria', 'N/A')}</span>
                                        <span>📍 {activo.get('ubicacion', 'N/A')}</span>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                                detalles = activo.get('detalles')
                                if detalles and isinstance(detalles, dict) and len(detalles) > 0:
                                    with st.expander("⚙️ Especificaciones"):
                                        for k, v in detalles.items():
                                            st.markdown(f"**{k}:** {v}")

                                if st.button(f"📋 Ver ficha", key=f"jer_act_{oid}", type="primary", use_container_width=True):
                                    navegar_a("Inventario Activos", jump_target="activo", jump_id=oid)
                                if st.button(f"🛠️ Ver OTs", key=f"jer_ot_{oid}", type="secondary", use_container_width=True):
                                    navegar_a("Ordenes de Trabajo", jump_target="ordenes_por_activo", jump_id=oid)

    # ── Activos sin área asignada ──
    activos_sin_area = df_act[~df_act['area'].isin(AREAS_DATA.keys())]
    if not activos_sin_area.empty:
        with st.expander(f"⚠️ Activos sin área asignada  —  {len(activos_sin_area)}", expanded=False):
            for _, act in activos_sin_area.iterrows():
                st.markdown(f"- **{act['nombre']}** (ID: {act['id']}) — Área: {act.get('area', 'N/A')}")


# ==============================================================================
# 🔍 FICHA DETALLE DE ACTIVO
# ==============================================================================
def _render_ficha_activo(activo):
    """Renderiza la vista detalle de un activo con sus órdenes relacionadas."""
    nombre = html_module.escape(str(activo.get('nombre', 'Sin nombre')))
    st.title(f"🔧 {nombre}")

    # Breadcrumb
    area = html_module.escape(str(activo.get('area', 'N/A')))
    ubic = html_module.escape(str(activo.get('ubicacion', 'N/A')))
    st.caption(f"📦 Inventario > {area} > {ubic} > {nombre}")

    # ── Foto + Datos principales ──
    col_foto, col_datos = st.columns([1, 2])

    with col_foto:
        url_foto = activo.get('foto_url')
        if url_foto and isinstance(url_foto, str) and len(url_foto) > 10:
            if not mostrar_imagen_cloudinary(url_foto, use_container_width=True, caption="Fotografía"):
                st.info("📷 Foto no disponible")
        else:
            st.markdown("<div style='text-align:center;font-size:4rem;padding:40px;background:#1F2937;border-radius:10px;'>🔧</div>", unsafe_allow_html=True)

        # QR
        url_qr = activo.get('qr_url')
        if url_qr and isinstance(url_qr, str) and len(url_qr) > 10:
            st.image(url_qr, width=150, caption="Código QR")

    with col_datos:
        st.markdown(f"""
        <div style="background:rgba(30,41,59,0.6);border-radius:10px;padding:20px;">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                <div>
                    <div style="color:#9CA3AF;font-size:0.8rem;text-transform:uppercase;">ID</div>
                    <div style="color:#E5E7EB;font-weight:600;">#{activo['id']}</div>
                </div>
                <div>
                    <div style="color:#9CA3AF;font-size:0.8rem;text-transform:uppercase;">Categoría</div>
                    <div style="color:#E5E7EB;font-weight:600;">{html_module.escape(str(activo.get('categoria', 'N/A')))}</div>
                </div>
                <div>
                    <div style="color:#9CA3AF;font-size:0.8rem;text-transform:uppercase;">Área</div>
                    <div style="color:#E5E7EB;font-weight:600;">{area}</div>
                </div>
                <div>
                    <div style="color:#9CA3AF;font-size:0.8rem;text-transform:uppercase;">Ubicación</div>
                    <div style="color:#E5E7EB;font-weight:600;">{ubic}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Especificaciones
        detalles = activo.get('detalles')
        if detalles and isinstance(detalles, dict) and len(detalles) > 0:
            st.markdown("#### ⚙️ Especificaciones")
            for k, v in detalles.items():
                st.markdown(f"**{html_module.escape(str(k))}:** {html_module.escape(str(v))}")

    st.markdown("---")

    # ── Órdenes relacionadas ──
    st.markdown("#### 🛠️ Órdenes de Trabajo Relacionadas")
    try:
        res_ordenes = supabase.table("ordenes").select("*") \
            .eq("activo_id", int(activo['id'])) \
            .order("fecha_creacion", desc=True).limit(10).execute()

        if res_ordenes.data:
            # KPIs rápidos
            total = len(res_ordenes.data)
            abiertas = sum(1 for o in res_ordenes.data if o['estado'] == 'Abierta')
            concluidas = sum(1 for o in res_ordenes.data if o['estado'] == 'Concluida')

            k1, k2, k3 = st.columns(3)
            k1.metric("Total OTs", total)
            k2.metric("🔨 Abiertas", abiertas)
            k3.metric("✅ Concluidas", concluidas)

            # Tabla de órdenes
            for orden in res_ordenes.data:
                icono = "✅" if orden['estado'] == 'Concluida' else "🔨" if orden['estado'] == 'Abierta' else "🧐"
                fecha = (orden.get('fecha_creacion', '') or '')[:10]
                desc = (orden.get('descripcion', '') or '')[:60]

                col_info, col_btn = st.columns([4, 1])
                with col_info:
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.03);border-left:3px solid {'#10B981' if orden['estado'] == 'Concluida' else '#F59E0B'};padding:8px 12px;border-radius:0 6px 6px 0;margin-bottom:4px;">
                        <div style="display:flex;justify-content:space-between;font-size:0.85rem;">
                            <span style="color:#E5E7EB;font-weight:600;">{icono} OT #{orden['id']}</span>
                            <span style="color:#9CA3AF;">{fecha}</span>
                        </div>
                        <div style="color:#9CA3AF;font-size:0.8rem;">{desc}{'...' if len(orden.get('descripcion', '') or '') > 60 else ''}</div>
                        <div style="font-size:0.75rem;color:#6B7280;">{orden.get('estado', '?')} · {orden.get('criticidad', '?')} · {orden.get('tipo_mantenimiento', '?')}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_btn:
                    if st.button("⚙️ Gestionar", key=f"ficha_ot_{orden['id']}", type="secondary", use_container_width=True):
                        navegar_a("Ordenes de Trabajo", jump_target="orden", jump_id=orden['id'])

            # Link para ver todas
            if st.button("📋 Ver todas las órdenes de este activo", key="ver_todas_ot_ficha"):
                navegar_a("Ordenes de Trabajo", jump_target="ordenes_por_activo", jump_id=int(activo['id']))
        else:
            st.info("Este activo no tiene órdenes de trabajo registradas.")
            if st.button("➕ Crear orden para este activo", type="primary"):
                navegar_a("Ordenes de Trabajo", jump_target="crear_para_activo", jump_id=int(activo['id']))
    except Exception as e:
        st.error("No se pudieron cargar las órdenes.")
        print(f"Error cargando OTs del activo: {e}")

    # ── Botón para editar ──
    st.markdown("---")
    if st.button("✏️ Editar este activo", use_container_width=True):
        navegar_a("Inventario Activos")


# ==============================================================================
# ➕ NUEVO ACTIVO
# ==============================================================================
def _render_nuevo(df_act):
    if 'activo_creado_info' in st.session_state and st.session_state.activo_creado_info is not None:
        _render_activo_creado()
        return

    st.markdown("### Registrar Nuevo Activo")
    draft = st.session_state.get('draft_data', {})

    def get_idx(opts, val):
        try:
            return list(opts).index(val)
        except (ValueError, TypeError):
            return 0

    # ── PASO 1: Ubicación ──
    st.markdown("##### 📍 Ubicación")
    c_loc1, c_loc2 = st.columns(2)
    keys_areas = sorted(AREAS_DATA.keys())
    idx_area_def = keys_areas.index(draft.get('area')) if draft.get('area') in keys_areas else 0
    area_principal = c_loc1.selectbox("Área Principal", keys_areas, index=idx_area_def, key="new_asset_area_out")

    sub_areas = sorted(AREAS_DATA[area_principal])
    d_sub_prev = ""
    if draft.get('ubicacion'):
        parts = draft['ubicacion'].split('] ', 1)
        d_sub_prev = parts[0].replace('[', '')
    idx_sub_def = sub_areas.index(d_sub_prev) if d_sub_prev in sub_areas else 0
    sub_area = c_loc2.selectbox("Sub-área", sub_areas, index=idx_sub_def, key="new_asset_sub_out")

    st.markdown("")

    # ── PASO 2: Datos del activo ──
    st.markdown("##### 📝 Datos del Activo")
    c1, c2 = st.columns(2)
    nom = c1.text_input("Nombre del Activo", value=draft.get('nombre', ''), key="new_asset_name")
    d_det_prev = ""
    if draft.get('ubicacion'):
        parts = draft['ubicacion'].split('] ', 1)
        if len(parts) > 1:
            d_det_prev = parts[1]
    ubic_detalle = c2.text_input("Ubicación Exacta / Detalle (Opcional)", value=d_det_prev, key="new_asset_detail")
    cat = c1.selectbox("Categoría", CATEGORIAS_LIST, index=get_idx(CATEGORIAS_LIST, draft.get('categoria')), key="new_asset_cat")

    st.markdown("---")

    # ── PASO 3: Especificaciones ──
    st.markdown("##### ⚙️ Especificaciones")
    edited_df = st.data_editor(st.session_state.specs_data, num_rows="dynamic", use_container_width=True, key="new_asset_specs")

    st.markdown("---")

    # ── PASO 4: Fotografía (fuera del form para drag-and-drop) ──
    st.markdown("##### 📸 Fotografía (Obligatorio)")

    if draft.get('foto_url'):
        mostrar_imagen_cloudinary(draft['foto_url'], width=120, caption="Foto guardada (Draft)")
        st.caption("Sube una nueva imagen para reemplazarla, o deja la actual.")

    foto_archivo = st.file_uploader(
        "Arrastra y suelta la imagen aquí, o haz clic para seleccionar",
        type=["jpg", "png", "jpeg"],
        key="new_asset_photo",
    )

    if foto_archivo is not None:
        st.session_state.draft_data['foto_bytes'] = foto_archivo.getvalue()
        try:
            img_bytes = foto_archivo.getvalue()
            b64 = base64
            b64_str = b64.b64encode(img_bytes).decode()
            nombre_lower = foto_archivo.name.lower() if hasattr(foto_archivo, 'name') else ""
            if nombre_lower.endswith(".png"):
                mime = "image/png"
            elif nombre_lower.endswith((".jpg", ".jpeg")):
                mime = "image/jpeg"
            else:
                mime = "image/png"
            st.markdown(
                f'<div style="text-align:center;">'
                f'<img src="data:{mime};base64,{b64_str}" '
                f'style="max-width:200px;height:auto;border-radius:8px;" />'
                f'<p style="color:#10B981;font-size:0.85rem;margin-top:4px;">✅ Imagen lista para guardar</p>'
                f'</div>',
                unsafe_allow_html=True
            )
        except Exception:
            st.warning("⚠️ No se pudo previsualizar, pero la foto se guardará correctamente.")
        st.success("Foto cargada correctamente.")
    elif draft.get('foto_bytes') is not None:
        st.image(draft['foto_bytes'], width=200, caption="Foto del draft")

    st.markdown("---")

    # ── Botón de guardar ──
    if st.button("💾 GUARDAR ACTIVO", type="primary", use_container_width=True, key="btn_save_new_asset"):
        foto_final = foto_archivo
        if foto_final is None and draft.get('foto_bytes') is not None:
            foto_final = io.BytesIO(draft['foto_bytes'])
            foto_final.name = "foto_draft.jpg"
        _guardar_nuevo_activo(nom, cat, area_principal, sub_area, ubic_detalle, foto_final, edited_df, draft)


def _guardar_nuevo_activo(nom, cat, area_principal, sub_area, ubic_detalle, foto_archivo, edited_df, draft):
    final_url = None
    foto_bytes_local = None

    if foto_archivo:
        with st.spinner("Subiendo foto a Cloudinary..."):
            # Obtener bytes del archivo (UploadedFile o BytesIO)
            try:
                foto_bytes_local = foto_archivo.getvalue() if hasattr(foto_archivo, 'getvalue') else foto_archivo.read()
            except Exception:
                foto_bytes_local = None
            final_url = subir_imagen(foto_archivo)
    elif draft.get('foto_url'):
        final_url = draft['foto_url']

    if not nom or not final_url:
        agregar_notificacion('error', '⚠️ El Nombre y la Foto son obligatorios.')
        return

    try:
        detalles_json = {
            row["Componente/Dato"]: row["Valor"]
            for i, row in edited_df.iterrows()
            if row["Componente/Dato"] and row["Valor"]
        }
        ubic_final = f"[{sub_area}] {ubic_detalle}" if ubic_detalle else f"[{sub_area}]"
        res = supabase.table("activos").insert({
            "nombre": nom, "area": area_principal, "ubicacion": ubic_final,
            "categoria": cat, "foto_url": final_url, "detalles": detalles_json
        }).execute()
        if res.data:
            nid = res.data[0]['id']
            qr = generar_qr_activo(nid, nom)
            supabase.table("activos").update({"qr_url": qr}).eq("id", nid).execute()
            st.cache_data.clear()
            st.session_state.draft_data = {}
            st.session_state.activo_creado_info = {
                "id": nid, "nombre": nom, "area": area_principal,
                "ubicacion": ubic_final, "categoria": cat,
                "foto_url": final_url, "foto_bytes": foto_bytes_local,
                "detalles": detalles_json, "qr_url": qr
            }
            st.rerun()
    except Exception as e:
        agregar_notificacion('error', f'Error guardando en base de datos: {e}')


def _render_activo_creado():
    info = st.session_state.activo_creado_info
    st.markdown(f"""
        <div style="background-color:rgba(6,78,59,0.5);border:1px solid #10B981;border-radius:10px;padding:20px;margin-bottom:20px;">
            <h2 style="color:#10B981;text-align:center;margin:0;">✨ ACTIVO REGISTRADO</h2>
            <p style="text-align:center;color:#D1FAE5;">Verifique los datos a continuación</p>
        </div>
    """, unsafe_allow_html=True)

    c_foto, c_datos, c_qr = st.columns([1, 1.5, 1])
    with c_foto:
        st.markdown("#### 🖼️ Foto")
        foto_nube = info.get('foto_url')
        foto_local = info.get('foto_bytes')
        # Prioridad 1: URL de Cloudinary (con fallback a bytes)
        if foto_nube and isinstance(foto_nube, str) and len(foto_nube) > 10:
            if not mostrar_imagen_cloudinary(foto_nube, use_container_width=True, caption="Fotografía"):
                # Fallback a bytes locales
                if foto_local and len(foto_local) > 0:
                    try:
                        st.image(io.BytesIO(foto_local), use_container_width=True, caption="Previsualización")
                    except Exception:
                        st.warning("No se pudo cargar la imagen.")
                else:
                    st.warning("No se pudo cargar la imagen.")
        # Prioridad 2: Solo bytes locales
        elif foto_local and len(foto_local) > 0:
            try:
                st.image(io.BytesIO(foto_local), use_container_width=True, caption="Previsualización")
            except Exception:
                st.warning("No se pudo cargar la vista previa local.")
        else:
            st.info("ℹ️ Sin imagen disponible.")
    with c_datos:
        st.markdown(f"### {info['nombre']}")
        st.markdown(f"**📍 Ubicación:** {info['area']} / {info['ubicacion']}")
        st.markdown(f"**🔧 Categoría:** {info['categoria']}")
        st.markdown("---")
        detalles = info['detalles']
        if detalles and isinstance(detalles, dict) and len(detalles) > 0:
            st.table(pd.DataFrame(list(detalles.items()), columns=["Característica", "Dato"]))
    with c_qr:
        if info.get('qr_url'):
            st.image(info['qr_url'], caption="QR Asignado", width=180)

    st.markdown("---")
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("✅ FINALIZAR Y NUEVO", type="primary", use_container_width=True):
            del st.session_state['activo_creado_info']
            st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
            st.session_state.draft_data = {}
            st.rerun()
    with b2:
        if st.button("✏️ EDITAR (CORREGIR)", use_container_width=True):
            supabase.table("activos").delete().eq("id", info['id']).execute()
            st.cache_data.clear()
            st.session_state.draft_data = info
            if info['detalles']:
                st.session_state.specs_data = pd.DataFrame(
                    list(info['detalles'].items()), columns=["Componente/Dato", "Valor"]
                )
            del st.session_state['activo_creado_info']
            st.rerun()
    with b3:
        if st.button("🗑️ DESHACER", type="secondary", use_container_width=True):
            supabase.table("activos").delete().eq("id", info['id']).execute()
            st.cache_data.clear()
            del st.session_state['activo_creado_info']
            st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
            st.session_state.draft_data = {}
            agregar_notificacion('warning', 'Registro cancelado.')
            st.rerun()


# ==============================================================================
# ✏️ EDITAR / QR
# ==============================================================================
def _render_edit(df_act):
    if not df_act.empty:
        all_assets = df_act['nombre'].values
        sel_asset = st.selectbox("🔍 Buscar Activo para Ver o Editar", all_assets)
        dat = df_act[df_act['nombre'] == sel_asset].iloc[0]
        id_suffix = dat['id']

        st.markdown("---")
        st.subheader(f"Editando: {dat['nombre']}")

        c1, c2 = st.columns(2)
        current_area_idx = list(sorted(AREAS_DATA.keys())).index(dat['area']) if dat['area'] in AREAS_DATA else 0
        edit_area = c1.selectbox("Área", sorted(AREAS_DATA.keys()), index=current_area_idx, key=f"edit_area_{id_suffix}")

        curr_sub, curr_det = "", ""
        if dat['ubicacion']:
            parts = dat['ubicacion'].split('] ', 1)
            curr_sub = parts[0].replace('[', '')
            curr_det = parts[1] if len(parts) > 1 else ""

        sub_areas_edit = sorted(AREAS_DATA[edit_area])
        curr_sub_idx = sub_areas_edit.index(curr_sub) if curr_sub in sub_areas_edit else 0
        edit_sub = c2.selectbox("Sub-área", sub_areas_edit, index=curr_sub_idx, key=f"edit_sub_{id_suffix}")
        edit_nom = c1.text_input("Nombre", value=dat['nombre'], key=f"edit_nom_{id_suffix}")
        edit_det = c2.text_input("Ubicación Detalle", value=curr_det, key=f"edit_det_{id_suffix}")
        curr_cat_idx = CATEGORIAS_LIST.index(dat['categoria']) if dat['categoria'] in CATEGORIAS_LIST else 0
        edit_cat = c1.selectbox("Categoría", CATEGORIAS_LIST, index=curr_cat_idx, key=f"edit_cat_{id_suffix}")

        st.markdown("---")
        nueva_foto_temp = st.file_uploader("Subir nueva foto", type=["jpg", "png"], key=f"edit_up_{id_suffix}")

        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            st.markdown("#### 🖼️ Visualización")
            if nueva_foto_temp:
                try:
                    img_bytes = nueva_foto_temp.getvalue()
                    b64 = base64
                    b64_str = b64.b64encode(img_bytes).decode()
                    # Detectar tipo de imagen
                    nombre_lower = nueva_foto_temp.name.lower() if hasattr(nueva_foto_temp, 'name') else ""
                    if nombre_lower.endswith(".png"):
                        mime = "image/png"
                    elif nombre_lower.endswith((".jpg", ".jpeg")):
                        mime = "image/jpeg"
                    else:
                        mime = "image/png"
                    st.markdown(
                        f'<div style="text-align:center;">'
                        f'<img src="data:{mime};base64,{b64_str}" '
                        f'style="max-width:100%;height:auto;border-radius:8px;" />'
                        f'<p style="color:#10B981;font-size:0.85rem;margin-top:4px;">✅ Nueva imagen (Sin guardar)</p>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                except Exception:
                    st.warning("⚠️ No se pudo previsualizar, pero la foto se guardará correctamente.")
            else:
                url_db = dat.get('foto_url')
                if url_db and isinstance(url_db, str) and len(url_db.strip()) > 10:
                    if not mostrar_imagen_cloudinary(url_db, use_container_width=True, caption="Imagen actual"):
                        # Mostrar la URL para diagnóstico y un fallback visual
                        st.warning("⚠️ No se pudo cargar la imagen desde Cloudinary.")
                        with st.expander("🔍 Diagnóstico"):
                            st.code(url_db, language="text")
                            st.caption("Posibles causas: URL expirada, restricción de acceso, o problema de red.")
                else:
                    st.info("Sin imagen asignada.")
        with col_f2:
            st.markdown("#### 🔄 Estado de Carga")
            if nueva_foto_temp:
                st.toast("✅ Foto lista para actualizar.")
            else:
                st.caption("Selecciona un archivo arriba si deseas cambiar la foto actual.")

        edit_foto_file = nueva_foto_temp

        st.markdown("---")
        st.markdown("#### ⚙️ Editar Especificaciones")
        current_specs_df = pd.DataFrame(columns=["Componente/Dato", "Valor"])
        if dat.get('detalles') and isinstance(dat['detalles'], dict):
            current_specs_df = pd.DataFrame(list(dat['detalles'].items()), columns=["Componente/Dato", "Valor"])
        edited_specs = st.data_editor(
            current_specs_df, num_rows="dynamic", use_container_width=True,
            column_config={
                "Componente/Dato": st.column_config.TextColumn("Característica"),
                "Valor": st.column_config.TextColumn("Valor")
            },
            key=f"editor_edit_{id_suffix}"
        )

        st.markdown("<br>", unsafe_allow_html=True)
        bc1, bc2 = st.columns([2, 1])
        with bc1:
            if st.button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True, key=f"btn_save_{id_suffix}"):
                _guardar_edicion_activo(dat, edit_nom, edit_area, edit_sub, edit_det, edit_cat,
                                         edit_foto_file, edited_specs, id_suffix)
        with bc2:
            _render_zona_peligro_activo(dat, id_suffix)

        st.markdown("---")
        if dat.get('qr_url'):
            st.caption("Código QR del Activo")
            st.image(dat['qr_url'], width=150)
    else:
        st.info("No hay activos registrados para editar.")


def _guardar_edicion_activo(dat, edit_nom, edit_area, edit_sub, edit_det, edit_cat,
                              edit_foto_file, edited_specs, id_suffix):
    if not edit_nom:
        agregar_notificacion("error", "El nombre no puede estar vacío")
        return
    try:
        with st.spinner("Actualizando activo..."):
            final_edit_url = dat['foto_url']
            if edit_foto_file:
                final_edit_url = subir_imagen(edit_foto_file)
            final_edit_ubic = f"[{edit_sub}] {edit_det}" if edit_det else f"[{edit_sub}]"
            final_specs_json = {
                row["Componente/Dato"]: row["Valor"]
                for i, row in edited_specs.iterrows()
                if row["Componente/Dato"] and row["Valor"]
            }
            supabase.table("activos").update({
                "nombre": edit_nom, "area": edit_area, "ubicacion": final_edit_ubic,
                "categoria": edit_cat, "foto_url": final_edit_url, "detalles": final_specs_json
            }).eq("id", dat['id']).execute()
            st.cache_data.clear()
            agregar_notificacion("success", f"Activo '{edit_nom}' actualizado correctamente")
            time.sleep(1.5)
            st.rerun()
    except Exception as e:
        error_amigable(e, "actualizar activo")


def _render_zona_peligro_activo(dat, id_suffix):
    with st.expander("🗑️ Zona de Peligro", expanded=True):
        st.warning("Acciones críticas.")
        ids_planes = ids_solic = ids_activas = ids_historial = []

        if dat.get('id'):
            res = supabase.table("planes_mantenimiento").select("id").eq("activo_id", dat['id']).execute()
            ids_planes = [str(x['id']) for x in res.data]
            res = supabase.table("solicitudes").select("id").eq("activo_id", dat['id']).execute()
            ids_solic = [str(x['id']) for x in res.data]
            res = supabase.table("ordenes").select("id, estado").eq("activo_id", dat['id']).execute()
            ids_activas = [str(o['id']) for o in res.data if o['estado'] in ['Abierta', 'Por Validar']]
            ids_historial = [str(o['id']) for o in res.data if o['estado'] not in ['Abierta', 'Por Validar']]

        bloqueo_total = ids_planes or ids_activas or ids_solic

        if bloqueo_total:
            st.markdown("""
            <div style="background-color:rgba(239,68,68,0.1);border-left:4px solid #EF4444;padding:10px;margin-bottom:10px;">
                <strong style="color:#EF4444;">🛑 NO SE PUEDE BORRAR</strong>
                <p style="font-size:0.85em;margin:0;">Hay tareas pendientes activas.</p>
            </div>
            """, unsafe_allow_html=True)
            if ids_planes:
                st.caption(f"📅 Planes ({len(ids_planes)})")
            if ids_activas:
                st.caption(f"🛠️ Órdenes Activas ({len(ids_activas)})")
            if ids_solic:
                st.caption(f"📬 Solicitudes ({len(ids_solic)}) — Gestionar en Buzón")
        else:
            if ids_historial:
                st.markdown(f"""
                <div style="background-color:rgba(245,158,11,0.1);border-left:4px solid #F59E0B;padding:10px;margin-bottom:10px;">
                    <strong style="color:#F59E0B;">⚠️ TIENE HISTORIAL</strong>
                    <p style="font-size:0.85em;margin:0;">Este equipo tiene <b>{len(ids_historial)}</b> órdenes cerradas.</p>
                </div>
                """, unsafe_allow_html=True)
                try:
                    if 'df_users_cache' not in st.session_state:
                        st.session_state.df_users_cache = run_query("usuarios")
                    data_hist = supabase.table("ordenes").select("*").in_("id", ids_historial) \
                        .order("fecha_creacion", desc=True).execute()
                    if data_hist.data:
                        pdf_bytes = generar_hoja_vida_pdf(dat, data_hist.data, st.session_state.df_users_cache)
                        st.download_button(
                            label="📄 DESCARGAR HOJA DE VIDA (PDF)",
                            data=pdf_bytes,
                            file_name=f"Hoja_Vida_{dat['nombre']}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                except Exception as e:
                    error_amigable(e, "generar PDF")
            else:
                st.toast("✅ Equipo limpio (Sin historial).")

            st.markdown("---")
            if st.button("🗑️ CONFIRMAR ELIMINACIÓN", type="secondary",
                         use_container_width=True, key=f"fin_del_{id_suffix}"):
                try:
                    if ids_historial:
                        supabase.table("ordenes").delete().in_("id", ids_historial).execute()
                    supabase.table("activos").delete().eq("id", dat['id']).execute()
                    st.cache_data.clear()
                    registrar_accion_critica("ELIMINAR_ACTIVO", st.session_state.get('usuario', '?'),
                                             f"Activo: {dat['nombre']} (ID: {dat['id']}) — {len(ids_historial)} OTs eliminadas")
                    agregar_notificacion("delete", "Activo eliminado correctamente.")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    error_amigable(e, "eliminar activo")
