import streamlit as st
import pandas as pd
import time
from datetime import datetime
from utils.db import supabase, run_query
from utils.helpers import mostrar_notificaciones, agregar_notificacion, registrar_accion_critica
from utils.uploads import subir_imagen
from utils.qr import generar_qr_activo
from pdf_utils import generar_hoja_vida_pdf


AREAS_DATA = {
    "Producción": [
        "Agua Cristal", "B&B", "Calderas", "Cuarto de Lubricación", "Equipos Auxiliares",
        "Laboratorio Fisico Quimico", "Laboratorio Microbiológico", "Linea 1", "Linea 2",
        "Linea 3", "Linea 10", "Linea 8 Jugos", "Oficinas Técnicas", "Pasillo Técnico",
        "Ptap", "Ptar", "Sala de Jarabe Simple", "Sala de Jarabe Terminado",
        "Sala de Jarabes Jugos", "Sub Estación Eléctrica", "Taller de Mantenimiento"
    ],
    "Administración": ["Administración", "Auditorio", "Casino", "Portería Vehicular", "Servicios Generales"],
    "Ventas": ["Bodega Carrera 8va", "Bodega Publicidad", "Dispensadores", "Ventas"],
    "Logística": ["Almacen Materia Prima", "Almacén Producto Terminado", "Lavadero de Vehiculos",
                   "Punto de Canje", "Taller de Reparación de Estibas", "Taller Vehicular"]
}

CATEGORIAS_LIST = sorted([
    "Aire Acondicionado", "CCTV", "Control de Acceso", "Eléctrico", "Estanterías",
    "Extraccion", "Hidrosanitario", "Infraestructura", "Mecánico", "Muelles",
    "Red Contra Incendio", "Refrigeración Industrial", "Ventilacion"
])


def render():
    st.title("INVENTARIO DE ACTIVOS")
    mostrar_notificaciones()

    df_act = pd.DataFrame(run_query("activos"))

    if 'specs_data' not in st.session_state:
        st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
    if 'draft_data' not in st.session_state:
        st.session_state.draft_data = {}

    tab_lista, tab_nuevo, tab_edit = st.tabs(["📋 LISTA DE ACTIVOS", "➕ NUEVO ACTIVO", "✏️ EDITAR / QR"])

    with tab_lista:
        _render_lista(df_act)

    with tab_nuevo:
        _render_nuevo(df_act)

    with tab_edit:
        _render_edit(df_act)


# ==============================================================================
# 📋 LISTA DE ACTIVOS
# ==============================================================================
def _render_lista(df_act):
    if not df_act.empty:
        @st.dialog("📸 Detalle Visual del Activo")
        def mostrar_visor(nombre, foto, qr):
            st.subheader(nombre)
            st.markdown("---")
            c_zoom1, c_zoom2 = st.columns(2)
            with c_zoom1:
                st.markdown("**Fotografía Real**")
                if foto and isinstance(foto, str):
                    st.image(foto, use_container_width=True)
                else:
                    st.warning("Sin foto")
            with c_zoom2:
                st.markdown("**Código QR**")
                if qr:
                    st.image(qr, width=250)
                else:
                    st.warning("Sin QR")
            st.caption("Presione 'Esc' o la 'X' para cerrar.")

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

        @st.fragment
        def fragmento_tabla_estable(dataframe_filtrado):
            if not dataframe_filtrado.empty:
                st.markdown(f"###### 🧬 Resultados: {len(dataframe_filtrado)}")
                st.info("👆 **Haga clic en una fila** para ver Foto y QR.")
                if 'last_viewed_id' not in st.session_state:
                    st.session_state.last_viewed_id = None
                altura_final = min(max(len(dataframe_filtrado) * 35 + 38, 100), 600)
                event = st.dataframe(
                    dataframe_filtrado[['id', 'foto_url', 'nombre', 'categoria', 'area', 'ubicacion', 'qr_url']],
                    column_config={
                        "foto_url": st.column_config.ImageColumn("Foto", width="small"),
                        "qr_url": st.column_config.ImageColumn("QR", width="small"),
                        "id": st.column_config.NumberColumn("ID", format="%d", width="small"),
                        "nombre": st.column_config.TextColumn("Nombre", width="medium"),
                        "categoria": st.column_config.TextColumn("Categoría", width="small"),
                        "area": st.column_config.TextColumn("Área", width="small"),
                        "ubicacion": st.column_config.TextColumn("Ubicación", width="medium"),
                    },
                    use_container_width=True, hide_index=True, height=altura_final,
                    selection_mode="single-row", on_select="rerun", key="tabla_maestra_activos"
                )
                if len(event.selection.rows) > 0:
                    idx = event.selection.rows[0]
                    sel_data = dataframe_filtrado.iloc[idx]
                    sel_id = sel_data['id']
                    if st.session_state.last_viewed_id != sel_id:
                        st.session_state.last_viewed_id = sel_id
                        mostrar_visor(sel_data['nombre'], sel_data['foto_url'], sel_data['qr_url'])
                else:
                    st.session_state.last_viewed_id = None
            else:
                if search_term or filtro_area != "Todas" or filtro_cat != "Todas":
                    st.warning("⚠️ No se encontraron activos con estos filtros.")

        fragmento_tabla_estable(df_filtered)
    else:
        st.info("Aún no hay activos registrados.")


# ==============================================================================
# ➕ NUEVO ACTIVO
# ==============================================================================
def _render_nuevo(df_act):
    if 'activo_creado_info' in st.session_state and st.session_state.activo_creado_info is not None:
        _render_activo_creado()
        return

    st.markdown("### Registrar Nuevo Activo")
    draft = st.session_state.get('draft_data', {})

    st.info("📍 Paso 1: Definir Ubicación")
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

    st.write("")
    with st.form("form_crear_activo", clear_on_submit=False):
        st.markdown("📝 **Paso 2: Detalles del Activo**")
        c1, c2 = st.columns(2)

        def get_idx(opts, val):
            try:
                return list(opts).index(val)
            except:
                return 0

        nom = c1.text_input("Nombre del Activo", value=draft.get('nombre', ''))
        d_det_prev = ""
        if draft.get('ubicacion'):
            parts = draft['ubicacion'].split('] ', 1)
            if len(parts) > 1:
                d_det_prev = parts[1]
        ubic_detalle = c2.text_input("Ubicación Exacta / Detalle (Opcional)", value=d_det_prev)
        cat = c1.selectbox("Categoría", CATEGORIAS_LIST, index=get_idx(CATEGORIAS_LIST, draft.get('categoria')))

        st.markdown("---")
        st.markdown("#### 📸 Fotografía (Obligatorio)")
        if draft.get('foto_url'):
            st.image(draft['foto_url'], width=100, caption="Foto actual (Draft)")
        foto_archivo = st.file_uploader("Subir imagen", type=["jpg", "png", "jpeg"])

        st.markdown("---")
        st.markdown("#### ⚙️ Especificaciones")
        edited_df = st.data_editor(st.session_state.specs_data, num_rows="dynamic", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        enviado = st.form_submit_button("💾 GUARDAR ACTIVO", type="primary", use_container_width=True)

    if enviado:
        _guardar_nuevo_activo(nom, cat, area_principal, sub_area, ubic_detalle, foto_archivo, edited_df, draft)


def _guardar_nuevo_activo(nom, cat, area_principal, sub_area, ubic_detalle, foto_archivo, edited_df, draft):
    final_url = None
    if foto_archivo:
        with st.spinner("Subiendo foto a Cloudinary..."):
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
            img_local = foto_archivo.getvalue() if foto_archivo else None
            st.session_state.activo_creado_info = {
                "id": nid, "nombre": nom, "area": area_principal,
                "ubicacion": ubic_final, "categoria": cat,
                "foto_url": final_url, "foto_bytes": img_local,
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
        foto_local = info.get('foto_bytes')
        foto_nube = info.get('foto_url')
        if foto_local is not None:
            try:
                st.image(foto_local, use_container_width=True, caption="Previsualización")
            except:
                st.warning("No se pudo cargar la vista previa local.")
        elif pd.notna(foto_nube) and isinstance(foto_nube, str) and len(foto_nube) > 10:
            try:
                st.image(foto_nube, use_container_width=True)
            except:
                st.error("Error al cargar imagen desde la nube.")
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
                st.image(nueva_foto_temp, use_container_width=True, caption="Nueva imagen (Sin guardar)")
            else:
                url_db = dat.get('foto_url')
                if pd.notna(url_db) and isinstance(url_db, str) and len(url_db.strip()) > 10:
                    try:
                        st.image(url_db, use_container_width=True, caption="Imagen actual")
                    except:
                        st.error("Error al cargar la imagen desde la nube.")
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
        st.error(f"Error al actualizar: {e}")


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
                    st.error(f"Error generando PDF: {e}")
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
                    st.error(f"Error técnico: {e}")
