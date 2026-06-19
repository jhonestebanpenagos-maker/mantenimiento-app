import streamlit as st
import pandas as pd
import time
import io
import base64
from datetime import datetime
from utils.db import supabase, run_query, run_query_filtered, render_paginacion, db_insert, db_update, db_delete, invalidate_cache
from utils.helpers import mostrar_notificaciones, agregar_notificacion, registrar_accion_critica, error_amigable
from utils.uploads import subir_imagen, mostrar_imagen_cloudinary
from utils.helpers import navegar_a
from utils.nav_button import render_back_button
from utils.qr import generar_qr_activo
from utils.catalogos import AREAS_DATA, CATEGORIAS_ACTIVOS
from pdf_utils import generar_hoja_vida_pdf

CATEGORIAS_LIST = CATEGORIAS_ACTIVOS

def render():
    st.title("📦 ACTIVOS")
    render_back_button()
    mostrar_notificaciones()

    # Usamos la caché optimizada de la Fase 2
    df_act = run_query("activos")

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
# 📋 LISTA DE ACTIVOS (MODERNIZADA CON COMPONENTES NATIVOS)
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

            # Renderizado en cuadrícula usando st.columns y st.container (100% Nativo)
            items_por_fila = 4
            for i in range(0, len(df_filtered), items_por_fila):
                cols = st.columns(items_por_fila)
                for j, (_, row) in enumerate(df_filtered.iloc[i:i+items_por_fila].iterrows()):
                    with cols[j]:
                        with st.container(border=True):
                            # Imagen (Streamlit ya integra visor fullscreen al hacer clic)
                            foto_url = row.get("foto_url", "")
                            if isinstance(foto_url, str) and foto_url.startswith("http"):
                                st.image(foto_url, use_container_width=True)
                            else:
                                st.markdown("<div style='text-align:center;font-size:3rem;padding:20px;color:#6B7280;'>📷</div>", unsafe_allow_html=True)
                            
                            st.markdown(f"**{row['nombre']}**")
                            st.caption(f"ID: {row['id']} · {row.get('categoria', 'N/A')}")
                            st.caption(f"📍 {row.get('area', '')} / {row.get('ubicacion', '')}")
                            
                            # Botón de acción directo
                            if st.button("📋 Ver Ficha", key=f"btn_lista_{row['id']}", use_container_width=True):
                                navegar_a("Inventario Activos", jump_target="activo", jump_id=row['id'])
        else:
            st.warning("⚠️ No se encontraron activos con estos filtros.")
    else:
        st.info("Aún no hay activos registrados.")

# ==============================================================================
# 🔍 BÚSQUEDA RÁPIDA INTEGRADA
# ==============================================================================
def _render_busqueda_rapida():
    query = st.text_input(
        "🔍 Buscar activo rápidamente...",
        placeholder="Nombre, categoría o ubicación...",
        key="activos_search_input",
        label_visibility="collapsed"
    )
    if query and len(query.strip()) >= 2:
        query = query.strip()
        try:
            # Optimizamos las búsquedas con RPC o caché
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
                        with st.container(border=True):
                            foto = a.get('foto_url', '')
                            if foto and isinstance(foto, str) and len(foto) > 10:
                                st.image(foto, use_container_width=True)
                            else:
                                st.markdown("<div style='text-align:center;font-size:2rem;padding:10px;'>🔧</div>", unsafe_allow_html=True)
                            st.markdown(f"**{a['nombre']}**")
                            st.caption(f"📍 {a.get('area', 'N/A')}")
                            if st.button("Ver", key=f"search_act_{a['id']}", use_container_width=True):
                                navegar_a("Inventario Activos", jump_target="activo", jump_id=a['id'])
                st.markdown("---")
            else:
                st.warning(f"🔍 Sin resultados para \"{query}\"")
        except Exception as e:
            st.caption(f"Error en búsqueda: {e}")

# ==============================================================================
# 🏗️ JERARQUÍA DE ACTIVOS (NATIVA)
# ==============================================================================
def _render_jerarquia(df_act):
    import re as re_module
    df_ordenes = run_query_filtered("ordenes", select_fields="id, activo_id, estado", filters={"estado": "Abierta"})

    if df_act.empty:
        st.info("No hay activos registrados. Ve a la pestaña **Nuevo** para crear el primero.")
        return

    mapa_ordenes_abiertas = {}
    if not df_ordenes.empty:
        mapa_ordenes_abiertas = df_ordenes.groupby('activo_id').size().to_dict()

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

    for area_nombre, sub_areas in sorted(AREAS_DATA.items()):
        activos_area = df_act[df_act['area'] == area_nombre]
        n_activos = len(activos_area)
        ots_area = sum(1 for _, a in activos_area.iterrows() if a['id'] in mapa_ordenes_abiertas)

        area_icon = "🏭" if area_nombre == "Producción" else "🏢" if area_nombre == "Administración" else "📦" if area_nombre == "Ventas" else "🚚"

        with st.expander(f"{area_icon} {area_nombre}  —  {n_activos} activos  {'⚠️ ' + str(ots_area) + ' OTs' if ots_area > 0 else '✅'}"):
            for sub_area in sorted(sub_areas):
                activos_sub = activos_area[
                    activos_area['ubicacion'].str.contains(rf"\[{re_module.escape(sub_area)}\]", regex=False, na=False)
                ]

                if activos_sub.empty:
                    st.caption(f"📍 {sub_area} (vacía)")
                else:
                    n_sub = len(activos_sub)
                    ots_sub = sum(1 for _, a in activos_sub.iterrows() if a['id'] in mapa_ordenes_abiertas)
                    badge = f"🔴 {ots_sub} OTs pendientes" if ots_sub > 0 else f"🟢 {n_sub} activos listos"

                    with st.expander(f"📍 {sub_area}  —  {badge}"):
                        for _, activo in activos_sub.iterrows():
                            oid = activo['id']
                            tiene_ots = oid in mapa_ordenes_abiertas
                            
                            with st.container(border=True):
                                col_foto, col_info, col_btns = st.columns([1, 3, 1.5])
                                with col_foto:
                                    foto = activo.get('foto_url', '')
                                    if foto and len(foto) > 10:
                                        st.image(foto, use_container_width=True)
                                    else:
                                        st.markdown("<div style='text-align:center;font-size:2rem;padding:10px;'>🔧</div>", unsafe_allow_html=True)
                                
                                with col_info:
                                    icono_estado = "🔴" if tiene_ots else "🟢"
                                    st.markdown(f"**{icono_estado} {activo['nombre']}** (ID: {oid})")
                                    st.caption(f"🔧 {activo.get('categoria', 'N/A')} | 📍 {activo.get('ubicacion', 'N/A')}")
                                    
                                    detalles = activo.get('detalles')
                                    if detalles and isinstance(detalles, dict) and len(detalles) > 0:
                                        st.caption("⚙️ Contiene Especificaciones Técnicas")
                                
                                with col_btns:
                                    if st.button("📋 Ficha", key=f"jer_act_{oid}", use_container_width=True):
                                        navegar_a("Inventario Activos", jump_target="activo", jump_id=oid)
                                    if st.button("🛠️ Ver OTs", key=f"jer_ot_{oid}", use_container_width=True, type="primary" if tiene_ots else "secondary"):
                                        navegar_a("Ordenes de Trabajo", jump_target="ordenes_por_activo", jump_id=oid)

    activos_sin_area = df_act[~df_act['area'].isin(AREAS_DATA.keys())]
    if not activos_sin_area.empty:
        with st.expander(f"⚠️ Activos sin área asignada  —  {len(activos_sin_area)}", expanded=False):
            for _, act in activos_sin_area.iterrows():
                st.markdown(f"- **{act['nombre']}** (ID: {act['id']}) — Área: {act.get('area', 'N/A')}")

# ==============================================================================
# 🔍 FICHA DETALLE DE ACTIVO (NATIVA)
# ==============================================================================
def _render_ficha_activo(activo):
    st.title(f"🔧 {activo.get('nombre', 'Sin nombre')}")
    st.caption(f"📦 Inventario > {activo.get('area', 'N/A')} > {activo.get('ubicacion', 'N/A')} > {activo.get('nombre', '')}")

    col_foto, col_datos = st.columns([1, 2])

    with col_foto:
        url_foto = activo.get('foto_url')
        if url_foto and len(url_foto) > 10:
            st.image(url_foto, use_container_width=True, caption="Fotografía del Equipo")
        else:
            st.info("📷 Foto no disponible")

        url_qr = activo.get('qr_url')
        if url_qr and len(url_qr) > 10:
            with st.expander("Ver Código QR"):
                st.image(url_qr, width=150)

    with col_datos:
        with st.container(border=True):
            # Usamos 2 columnas en lugar de 4 y texto estándar para que no se corte en pantallas pequeñas
            c1, c2 = st.columns(2)
            
            with c1:
                st.caption("🆔 ID del Equipo")
                st.markdown(f"#### #{activo['id']}")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                st.caption("🏢 Área Asignada")
                st.markdown(f"**{activo.get('area', 'N/A')}**")
                
            with c2:
                st.caption("🔧 Categoría")
                st.markdown(f"**{activo.get('categoria', 'N/A')}**")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                st.caption("📍 Ubicación Específica")
                st.markdown(f"**{activo.get('ubicacion', 'N/A')}**")

        detalles = activo.get('detalles')
        if detalles and isinstance(detalles, dict) and len(detalles) > 0:
            with st.container(border=True):
                st.markdown("#### ⚙️ Especificaciones Técnicas")
                for k, v in detalles.items():
                    st.markdown(f"**{k}:** {v}")

    st.markdown("---")
    st.markdown("#### 🛠️ Órdenes de Trabajo Relacionadas")
    try:
        res_ordenes = supabase.table("ordenes").select("*").eq("activo_id", int(activo['id'])).order("fecha_creacion", desc=True).limit(10).execute()

        if res_ordenes.data:
            total = len(res_ordenes.data)
            abiertas = sum(1 for o in res_ordenes.data if o['estado'] == 'Abierta')
            concluidas = sum(1 for o in res_ordenes.data if o['estado'] == 'Concluida')

            k1, k2, k3 = st.columns(3)
            k1.metric("Total Histórico", total)
            k2.metric("🔨 En Ejecución", abiertas)
            k3.metric("✅ Concluidas", concluidas)

            for orden in res_ordenes.data:
                with st.container(border=True):
                    c_info, c_btn = st.columns([4, 1])
                    with c_info:
                        icono = "✅" if orden['estado'] == 'Concluida' else "🔨" if orden['estado'] == 'Abierta' else "🧐"
                        fecha = (orden.get('fecha_creacion', '') or '')[:10]
                        st.markdown(f"**{icono} OT #{orden['id']}** — {fecha}")
                        st.caption(f"{orden.get('estado', '?')} · {orden.get('criticidad', '?')} · {orden.get('descripcion', '')[:80]}...")
                    with c_btn:
                        if st.button("Gestionar", key=f"ficha_ot_{orden['id']}", use_container_width=True):
                            navegar_a("Ordenes de Trabajo", jump_target="orden", jump_id=orden['id'])

            if st.button("📋 Ver Historial Completo", key="ver_todas_ot_ficha"):
                navegar_a("Ordenes de Trabajo", jump_target="ordenes_por_activo", jump_id=int(activo['id']))
        else:
            st.info("Este equipo no tiene incidencias ni mantenimientos registrados en el historial.")
            if st.button("➕ Crear nueva Orden", type="primary"):
                navegar_a("Ordenes de Trabajo", jump_target="crear_para_activo", jump_id=int(activo['id']))
    except Exception as e:
        st.error("No se pudieron cargar las órdenes.")

    st.markdown("---")
    if st.button("✏️ Editar información del activo", use_container_width=True):
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

    st.markdown("##### 📍 Ubicación")
    c_loc1, c_loc2 = st.columns(2)
    keys_areas = sorted(AREAS_DATA.keys())
    area_principal = c_loc1.selectbox("Área Principal", keys_areas, index=get_idx(keys_areas, draft.get('area')), key="new_asset_area_out")

    sub_areas = sorted(AREAS_DATA[area_principal])
    d_sub_prev = draft['ubicacion'].split('] ', 1)[0].replace('[', '') if draft.get('ubicacion') else ""
    sub_area = c_loc2.selectbox("Sub-área", sub_areas, index=get_idx(sub_areas, d_sub_prev), key="new_asset_sub_out")

    st.markdown("##### 📝 Datos del Activo")
    c1, c2 = st.columns(2)
    nom = c1.text_input("Nombre del Equipo", value=draft.get('nombre', ''), key="new_asset_name")
    d_det_prev = draft['ubicacion'].split('] ', 1)[1] if draft.get('ubicacion') and len(draft['ubicacion'].split('] ', 1)) > 1 else ""
    ubic_detalle = c2.text_input("Ubicación Exacta / Referencia (Opcional)", value=d_det_prev, key="new_asset_detail")
    cat = c1.selectbox("Categoría", CATEGORIAS_LIST, index=get_idx(CATEGORIAS_LIST, draft.get('categoria')), key="new_asset_cat")

    st.markdown("---")
    st.markdown("##### ⚙️ Especificaciones Técnicas (Opcional)")
    edited_df = st.data_editor(st.session_state.specs_data, num_rows="dynamic", use_container_width=True, key="new_asset_specs")

    st.markdown("---")
    st.markdown("##### 📸 Fotografía (Obligatorio)")

    if draft.get('foto_url'):
        st.image(draft['foto_url'], width=120, caption="Foto guardada (Borrador)")

    foto_archivo = st.file_uploader("Arrastra y suelta la imagen aquí", type=["jpg", "png", "jpeg"], key="new_asset_photo")

    if foto_archivo is not None:
        foto_bytes = foto_archivo.getvalue()
        st.session_state.draft_data['foto_bytes'] = foto_bytes
        st.success("✅ Imagen cargada temporalmente.")
        st.image(foto_bytes, width=250)

    st.markdown("---")
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
        with st.spinner("Procesando imagen en la nube..."):
            try:
                foto_bytes_local = foto_archivo.getvalue() if hasattr(foto_archivo, 'getvalue') else foto_archivo.read()
            except Exception:
                foto_bytes_local = None
            final_url = subir_imagen(foto_archivo)
    elif draft.get('foto_url'):
        final_url = draft['foto_url']

    if not nom or not final_url:
        st.error('⚠️ El Nombre y la Fotografía son datos obligatorios.')
        return

    try:
        detalles_json = {row["Componente/Dato"]: row["Valor"] for i, row in edited_df.iterrows() if row["Componente/Dato"] and row["Valor"]}
        ubic_final = f"[{sub_area}] {ubic_detalle}" if ubic_detalle else f"[{sub_area}]"
        
        res = db_insert("activos", {
            "nombre": nom, "area": area_principal, "ubicacion": ubic_final,
            "categoria": cat, "foto_url": final_url, "detalles": detalles_json
        })
        
        if res.data:
            nid = res.data[0]['id']
            qr = generar_qr_activo(nid, nom)
            db_update("activos", {"qr_url": qr}, "id", nid)
            st.session_state.draft_data = {}
            st.session_state.activo_creado_info = {
                "id": nid, "nombre": nom, "area": area_principal,
                "ubicacion": ubic_final, "categoria": cat,
                "foto_url": final_url, "foto_bytes": foto_bytes_local,
                "detalles": detalles_json, "qr_url": qr
            }
            st.rerun()
    except Exception as e:
        error_amigable(e, "guardar activo en la base de datos")

def _render_activo_creado():
    info = st.session_state.activo_creado_info
    st.success("✨ ¡ACTIVO REGISTRADO EXITOSAMENTE!")
    
    with st.container(border=True):
        c_foto, c_datos, c_qr = st.columns([1, 1.5, 1])
        with c_foto:
            st.caption("📷 Fotografía")
            # OPTIMIZACIÓN: Usar memoria local prioritaria para no esperar a la nube
            foto_local = info.get('foto_bytes')
            foto_nube = info.get('foto_url')
            
            if foto_local:
                st.image(foto_local, use_container_width=True)
            elif foto_nube and len(foto_nube) > 10:
                st.image(foto_nube, use_container_width=True)
            else:
                st.info("ℹ️ Sin imagen disponible.")
                
        with c_datos:
            st.markdown(f"### {info['nombre']}")
            st.markdown(f"**📍 Ubicación:** {info['area']} / {info['ubicacion']}")
            st.markdown(f"**🔧 Categoría:** {info['categoria']}")
            if info.get('detalles'):
                st.table(pd.DataFrame(list(info['detalles'].items()), columns=["Característica", "Dato"]))
                
        with c_qr:
            st.caption("🏷️ Código QR")
            if info.get('qr_url'):
                # Forzar un tamaño de 150px evita que el QR se vuelva invisible al estirarse
                st.image(info['qr_url'], width=150)

    b1, b2, b3 = st.columns(3)
    if b1.button("✅ FINALIZAR Y CREAR OTRO", type="primary", use_container_width=True):
        del st.session_state['activo_creado_info']
        st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
        st.session_state.draft_data = {}
        st.rerun()
    if b2.button("✏️ EDITAR (CORREGIR)", use_container_width=True):
        db_delete("activos", "id", info['id'])
        st.session_state.draft_data = info
        if info['detalles']:
            st.session_state.specs_data = pd.DataFrame(list(info['detalles'].items()), columns=["Componente/Dato", "Valor"])
        del st.session_state['activo_creado_info']
        st.rerun()
    if b3.button("🗑️ DESHACER REGISTRO", use_container_width=True):
        db_delete("activos", "id", info['id'])
        del st.session_state['activo_creado_info']
        st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
        st.session_state.draft_data = {}
        st.toast("Registro cancelado y eliminado de la BD.")
        st.rerun()

# ==============================================================================
# ✏️ EDITAR / QR (ZONA DE PELIGRO NATIVA)
# ==============================================================================
def _render_edit(df_act):
    if not df_act.empty:
        all_assets = df_act['nombre'].values
        sel_asset = st.selectbox("🔍 Buscar Equipo para Modificar", all_assets)
        dat = df_act[df_act['nombre'] == sel_asset].iloc[0]
        id_suffix = dat['id']

        st.markdown("---")
        st.subheader(f"Editando: {dat['nombre']}")

        with st.container(border=True):
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
            edit_det = c2.text_input("Referencia Específica", value=curr_det, key=f"edit_det_{id_suffix}")
            curr_cat_idx = CATEGORIAS_LIST.index(dat['categoria']) if dat['categoria'] in CATEGORIAS_LIST else 0
            edit_cat = c1.selectbox("Categoría", CATEGORIAS_LIST, index=curr_cat_idx, key=f"edit_cat_{id_suffix}")

        nueva_foto_temp = st.file_uploader("Subir nueva fotografía para reemplazar la actual", type=["jpg", "png"], key=f"edit_up_{id_suffix}")
        
        if nueva_foto_temp:
            st.success("✅ Imagen lista para reemplazar al guardar cambios.")
        else:
            url_db = dat.get('foto_url')
            if url_db and len(url_db) > 10:
                with st.expander("Ver Imagen Actual"):
                    st.image(url_db, width=300)

        st.markdown("#### ⚙️ Editar Especificaciones")
        current_specs_df = pd.DataFrame(list(dat['detalles'].items()), columns=["Componente/Dato", "Valor"]) if dat.get('detalles') else pd.DataFrame(columns=["Componente/Dato", "Valor"])
        edited_specs = st.data_editor(current_specs_df, num_rows="dynamic", use_container_width=True, key=f"editor_edit_{id_suffix}")

        st.markdown("<br>", unsafe_allow_html=True)
        bc1, bc2 = st.columns([2, 1])
        with bc1:
            if st.button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True, key=f"btn_save_{id_suffix}"):
                _guardar_edicion_activo(dat, edit_nom, edit_area, edit_sub, edit_det, edit_cat, edit_foto_file=nueva_foto_temp, edited_specs=edited_specs, id_suffix=id_suffix)
        with bc2:
            _render_zona_peligro_activo(dat, id_suffix)
    else:
        st.info("No hay activos registrados para editar.")

def _guardar_edicion_activo(dat, edit_nom, edit_area, edit_sub, edit_det, edit_cat, edit_foto_file, edited_specs, id_suffix):
    if not edit_nom:
        st.error("El nombre no puede estar vacío")
        return
    try:
        with st.spinner("Actualizando datos del equipo..."):
            final_edit_url = dat['foto_url']
            if edit_foto_file:
                final_edit_url = subir_imagen(edit_foto_file)
            final_edit_ubic = f"[{edit_sub}] {edit_det}" if edit_det else f"[{edit_sub}]"
            final_specs_json = {row["Componente/Dato"]: row["Valor"] for i, row in edited_specs.iterrows() if row["Componente/Dato"] and row["Valor"]}
            
            db_update("activos", {
                "nombre": edit_nom, "area": edit_area, "ubicacion": final_edit_ubic,
                "categoria": edit_cat, "foto_url": final_edit_url, "detalles": final_specs_json
            }, "id", dat['id'])
            st.toast(f"✅ Activo '{edit_nom}' actualizado correctamente")
            time.sleep(0.5)
            st.rerun()
    except Exception as e:
        error_amigable(e, "actualizar activo")

def _render_zona_peligro_activo(dat, id_suffix):
    with st.expander("⚠️ Zona de Peligro (Eliminar Activo)"):
        ids_planes = ids_solic = ids_activas = ids_historial = []

        if dat.get('id'):
            ids_planes = [str(x['id']) for x in supabase.table("planes_mantenimiento").select("id").eq("activo_id", dat['id']).execute().data]
            ids_solic = [str(x['id']) for x in supabase.table("solicitudes").select("id").eq("activo_id", dat['id']).execute().data]
            res_ots = supabase.table("ordenes").select("id, estado").eq("activo_id", dat['id']).execute().data
            ids_activas = [str(o['id']) for o in res_ots if o['estado'] in ['Abierta', 'Por Validar']]
            ids_historial = [str(o['id']) for o in res_ots if o['estado'] not in ['Abierta', 'Por Validar']]

        bloqueo_total = ids_planes or ids_activas or ids_solic

        if bloqueo_total:
            st.error("🛑 **NO SE PUEDE BORRAR:** Hay tareas pendientes activas para este equipo.")
            if ids_planes: st.caption(f"📅 Planes de mantenimiento asociados: {len(ids_planes)}")
            if ids_activas: st.caption(f"🛠️ Órdenes Abiertas/Por Validar: {len(ids_activas)}")
            if ids_solic: st.caption(f"📬 Solicitudes de buzón sin atender: {len(ids_solic)}")
        else:
            if ids_historial:
                st.warning(f"⚠️ **TIENE HISTORIAL:** Este equipo tiene {len(ids_historial)} órdenes cerradas en el registro.")
                try:
                    df_users_cache = run_query("usuarios")
                    data_hist = supabase.table("ordenes").select("*").in_("id", ids_historial).order("fecha_creacion", desc=True).execute().data
                    if data_hist:
                        pdf_bytes = generar_hoja_vida_pdf(dat, data_hist, df_users_cache)
                        st.download_button("📄 DESCARGAR HOJA DE VIDA PARA RESPALDO", data=pdf_bytes, file_name=f"Respaldo_{dat['nombre']}.pdf", mime="application/pdf", use_container_width=True)
                except Exception as e:
                    pass
            else:
                st.success("✅ Equipo limpio (No tiene mantenimientos previos).")

            st.markdown("---")
            confirm_del = st.text_input("Escribe ELIMINAR para proceder", key=f"conf_del_{id_suffix}")
            if st.button("🗑️ ELIMINAR DEFINITIVAMENTE", use_container_width=True, disabled=(confirm_del.strip().upper() != "ELIMINAR")):
                if ids_historial:
                    supabase.table("ordenes").delete().in_("id", ids_historial).execute()
                    invalidate_cache("ordenes")
                db_delete("activos", "id", dat['id'])
                st.toast("✅ Activo eliminado con éxito.")
                time.sleep(0.5)
                st.rerun()
