import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime
from utils.db import supabase, run_query
from utils.helpers import mostrar_notificaciones, agregar_notificacion, error_amigable
from utils.nav_button import render_back_button
from utils.uploads import subir_imagen
from utils.notifications import notificar_telegram
from utils.catalogos import CATEGORIAS_REPUESTOS


CATEGORIAS_REP = CATEGORIAS_REPUESTOS


def render():
    st.title("🔩 GESTIÓN DE REPUESTOS")
    render_back_button()
    mostrar_notificaciones()

    df_rep = run_query("repuestos")
    df_ord = run_query("ordenes")
    df_mov = run_query("movimientos_repuestos")
    df_users = run_query("usuarios")

    # ── Manejar navegación desde búsqueda ──
    jump = st.session_state.get('jump_target')
    jump_id = st.session_state.get('jump_id')

    if jump == "repuesto" and jump_id:
        st.session_state.jump_target = None
        st.session_state.jump_id = None
        # Forzar filtro por este repuesto
        st.session_state.repuesto_focus = int(jump_id)

    tab_stock, tab_nuevo, tab_movimientos, tab_alertas = st.tabs([
        "📋 STOCK ACTUAL", "➕ NUEVO REPUESTO", "🔄 MOVIMIENTOS", "🚨 ALERTAS DE STOCK"
    ])

    with tab_stock:
        _render_stock(df_rep)

    with tab_nuevo:
        _render_nuevo_repuesto()

    with tab_movimientos:
        _render_movimientos(df_rep, df_ord, df_mov, df_users)

    with tab_alertas:
        _render_alertas(df_rep, df_users)


# ==============================================================================
# 📋 STOCK ACTUAL
# ==============================================================================
def _render_stock(df_rep):
    if df_rep.empty:
        st.info("No hay repuestos registrados aún.")
        return

    # ── Si hay un repuesto en foco desde búsqueda, mostrarlo primero ──
    focus_id = st.session_state.pop('repuesto_focus', None)
    if focus_id is not None:
        rep_focus = df_rep[df_rep['id'] == focus_id]
        if not rep_focus.empty:
            r = rep_focus.iloc[0]
            stock = r.get('stock_actual', 0)
            minimo = r.get('stock_minimo', 0)
            icono = "🔴" if stock == 0 else "🟡" if stock <= minimo else "🟢"

            st.markdown(f"""
            <div style="background:rgba(59,130,246,0.1);border:1px solid #3B82F6;border-radius:10px;padding:20px;margin-bottom:20px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="color:#60A5FA;font-size:0.8rem;text-transform:uppercase;">Repuesto Seleccionado</div>
                        <div style="color:#E5E7EB;font-size:1.3rem;font-weight:700;margin:4px 0;">{icono} {r['nombre']}</div>
                        <div style="color:#9CA3AF;font-size:0.85rem;">Ref: {r.get('referencia', 'N/A')} · {r.get('categoria', 'N/A')} · {r.get('ubicacion', 'N/A')}</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="color:#9CA3AF;font-size:0.75rem;">Stock</div>
                        <div style="color:{'#10B981' if stock > minimo else '#EF4444' if stock == 0 else '#F59E0B'};font-size:2rem;font-weight:800;">{stock}</div>
                        <div style="color:#6B7280;font-size:0.7rem;">mín: {minimo} {r.get('unidad', '')}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")

    total_rep = len(df_rep)
    bajo_stock = len(df_rep[df_rep['stock_actual'] <= df_rep['stock_minimo']])
    sin_stock = len(df_rep[df_rep['stock_actual'] == 0])
    valor_items = df_rep['stock_actual'].sum()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🔩 Total Repuestos", total_rep)
    k2.metric("📦 Unidades Totales", int(valor_items))
    k3.metric("⚠️ Bajo Stock", bajo_stock, delta_color="inverse")
    k4.metric("🚨 Sin Stock", sin_stock, delta_color="inverse")

    st.markdown("---")
    cf1, cf2 = st.columns(2)
    filtro_cat_r = cf1.selectbox("Filtrar Categoría", ["Todas"] + CATEGORIAS_REP)
    filtro_stock = cf2.selectbox("Filtrar Estado Stock", ["Todos", "OK", "Bajo Stock", "Sin Stock"])

    df_rep_f = df_rep.copy()
    if filtro_cat_r != "Todas":
        df_rep_f = df_rep_f[df_rep_f['categoria'] == filtro_cat_r]
    if filtro_stock == "OK":
        df_rep_f = df_rep_f[df_rep_f['stock_actual'] > df_rep_f['stock_minimo']]
    elif filtro_stock == "Bajo Stock":
        df_rep_f = df_rep_f[(df_rep_f['stock_actual'] <= df_rep_f['stock_minimo']) & (df_rep_f['stock_actual'] > 0)]
    elif filtro_stock == "Sin Stock":
        df_rep_f = df_rep_f[df_rep_f['stock_actual'] == 0]

    def estado_stock(row):
        if row['stock_actual'] == 0: return "🔴 Sin Stock"
        elif row['stock_actual'] <= row['stock_minimo']: return "🟡 Bajo Stock"
        else: return "🟢 OK"

    df_rep_f['Estado'] = df_rep_f.apply(estado_stock, axis=1)
    st.dataframe(
        df_rep_f[['id', 'foto_url', 'nombre', 'referencia', 'categoria',
                   'stock_actual', 'stock_minimo', 'unidad', 'ubicacion', 'Estado']],
        column_config={
            "foto_url": st.column_config.ImageColumn("Foto", width="small"),
            "id": st.column_config.NumberColumn("ID", format="%d", width="small"),
            "nombre": st.column_config.TextColumn("Nombre", width="medium"),
            "referencia": st.column_config.TextColumn("Referencia"),
            "categoria": st.column_config.TextColumn("Categoría"),
            "stock_actual": st.column_config.NumberColumn("Stock", format="%d"),
            "stock_minimo": st.column_config.NumberColumn("Mínimo", format="%d"),
            "unidad": st.column_config.TextColumn("Unidad"),
            "ubicacion": st.column_config.TextColumn("Ubicación"),
            "Estado": st.column_config.TextColumn("Estado")
        },
        hide_index=True, use_container_width=True, height=400
    )

    st.markdown("---")
    st.markdown("#### 📊 Nivel de Stock por Repuesto")
    df_grafica = df_rep_f.sort_values('stock_actual', ascending=True).tail(15)
    fig_stock = go.Figure()
    fig_stock.add_trace(go.Bar(name='Stock Actual', y=df_grafica['nombre'], x=df_grafica['stock_actual'],
                                orientation='h', marker=dict(color='#10B981'),
                                text=df_grafica['stock_actual'], textposition='inside'))
    fig_stock.add_trace(go.Bar(name='Stock Mínimo', y=df_grafica['nombre'], x=df_grafica['stock_minimo'],
                                orientation='h', marker=dict(color='#F59E0B', opacity=0.5),
                                text=df_grafica['stock_minimo'], textposition='inside'))
    fig_stock.update_layout(barmode='overlay', paper_bgcolor='rgba(0,0,0,0)',
                             plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'), height=400,
                             margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=-0.15),
                             xaxis=dict(title="Unidades"), yaxis=dict(title=None))
    st.plotly_chart(fig_stock, use_container_width=True)


# ==============================================================================
# ➕ NUEVO REPUESTO
# ==============================================================================
def _render_nuevo_repuesto():
    st.markdown("### Registrar Nuevo Repuesto")
    with st.form("form_nuevo_repuesto", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nom_r = c1.text_input("Nombre del Repuesto")
        ref_r = c2.text_input("Referencia / Código", placeholder="Ej: SKF-6205")
        cat_r = c1.selectbox("Categoría", CATEGORIAS_REP)
        ubic_r = c2.text_input("Ubicación en bodega", placeholder="Ej: Estante A, Gaveta 3")
        c3, c4, c5 = st.columns(3)
        stock_i = c3.number_input("Stock Inicial", min_value=0, value=0)
        stock_m = c4.number_input("Stock Mínimo", min_value=0, value=1)
        unidad = c5.selectbox("Unidad", ["Unidad", "Par", "Caja", "Litro", "Galón", "Metro", "Kilogramo", "Rollo"])
        foto_r = st.file_uploader("Foto del repuesto (Opcional)", type=["jpg", "png", "jpeg"])

        if st.form_submit_button("💾 GUARDAR REPUESTO", type="primary", use_container_width=True):
            if not nom_r:
                agregar_notificacion('error', 'El nombre es obligatorio.')
            else:
                try:
                    url_foto_r = None
                    if foto_r:
                        with st.spinner("Subiendo foto..."):
                            url_foto_r = subir_imagen(foto_r, "orion_repuestos")
                    supabase.table("repuestos").insert({
                        "nombre": nom_r, "referencia": ref_r, "categoria": cat_r,
                        "ubicacion": ubic_r, "stock_actual": int(stock_i),
                        "stock_minimo": int(stock_m), "unidad": unidad, "foto_url": url_foto_r
                    }).execute()
                    st.cache_data.clear()
                    agregar_notificacion('success', f'Repuesto {nom_r} registrado correctamente.')
                    st.rerun()
                except Exception as e:
                    error_amigable(e)


# ==============================================================================
# 🔄 MOVIMIENTOS
# ==============================================================================
def _render_movimientos(df_rep, df_ord, df_mov, df_users):
    st.markdown("### 🔄 Registrar Entrada o Salida")
    if df_rep.empty:
        st.warning("Primero registra repuestos en la pestaña anterior.")
        return

    rep_dict = dict(zip(df_rep['nombre'], df_rep['id']))
    ord_dict = {}
    if not df_ord.empty:
        df_ord_ab = df_ord[df_ord['estado'] == 'Abierta']
        ord_dict = {f"OT #{r['id']} — {r['descripcion'][:40]}": r['id']
                     for _, r in df_ord_ab.iterrows()}

    with st.form("form_movimiento", clear_on_submit=True):
        c1, c2 = st.columns(2)
        rep_sel = c1.selectbox("Repuesto", list(rep_dict.keys()))
        tipo_mov = c2.selectbox("Tipo", ["Salida", "Entrada"])
        cantidad = c1.number_input("Cantidad", min_value=1, value=1)
        orden_sel = None
        if tipo_mov == "Salida" and ord_dict:
            orden_sel = c2.selectbox("Vincular a Orden (Opcional)", ["Sin vincular"] + list(ord_dict.keys()))
        observacion = st.text_input("Observación", placeholder="Ej: Cambio por desgaste en línea 1")

        if st.form_submit_button("✅ REGISTRAR MOVIMIENTO", type="primary", use_container_width=True):
            try:
                rep_id = int(rep_dict[rep_sel])
                rep_actual = df_rep[df_rep['id'] == rep_id].iloc[0]
                stock_hoy = int(rep_actual['stock_actual'])
                if tipo_mov == "Salida" and cantidad > stock_hoy:
                    agregar_notificacion('error', f'Stock insuficiente. Disponible: {stock_hoy} {rep_actual["unidad"]}')
                else:
                    nuevo_stock = stock_hoy - cantidad if tipo_mov == "Salida" else stock_hoy + cantidad
                    id_orden_mov = None
                    if tipo_mov == "Salida" and orden_sel and orden_sel != "Sin vincular":
                        id_orden_mov = int(ord_dict[orden_sel])
                    supabase.table("movimientos_repuestos").insert({
                        "repuesto_id": rep_id, "orden_id": id_orden_mov, "tipo": tipo_mov,
                        "cantidad": int(cantidad), "usuario_text": st.session_state.get('usuario', ''),
                        "observacion": observacion, "fecha": datetime.now().isoformat()
                    }).execute()
                    supabase.table("repuestos").update({"stock_actual": nuevo_stock}).eq("id", rep_id).execute()
                    stock_min = int(rep_actual['stock_minimo'])
                    if nuevo_stock <= stock_min:
                        _notificar_stock_bajo(rep_sel, nuevo_stock, rep_actual['unidad'], stock_min, df_users)
                    st.cache_data.clear()
                    agregar_notificacion('success', f'{tipo_mov} de {cantidad} {rep_actual["unidad"]} de {rep_sel} registrada.')
                    st.rerun()
            except Exception as e:
                error_amigable(e)

    st.markdown("---")
    st.markdown("#### 📜 Historial de Movimientos")
    if not df_mov.empty:
        df_mov_vis = df_mov.copy()
        rep_map = dict(zip(df_rep['id'], df_rep['nombre']))
        df_mov_vis['Repuesto'] = df_mov_vis['repuesto_id'].map(rep_map).fillna('N/A')
        df_mov_vis = df_mov_vis.sort_values('fecha', ascending=False).head(50)
        st.dataframe(
            df_mov_vis[['fecha', 'tipo', 'Repuesto', 'cantidad', 'orden_id', 'usuario_text', 'observacion']],
            column_config={
                "fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YY HH:mm"),
                "tipo": st.column_config.TextColumn("Tipo"),
                "Repuesto": st.column_config.TextColumn("Repuesto"),
                "cantidad": st.column_config.NumberColumn("Cant.", format="%d"),
                "orden_id": st.column_config.NumberColumn("OT #", format="%d"),
                "usuario_text": st.column_config.TextColumn("Usuario"),
                "observacion": st.column_config.TextColumn("Observación")
            },
            hide_index=True, use_container_width=True, height=350
        )
    else:
        st.info("No hay movimientos registrados aún.")


# ==============================================================================
# 🚨 ALERTAS DE STOCK
# ==============================================================================
def _render_alertas(df_rep, df_users):
    st.markdown("### 🚨 Repuestos que Requieren Atención")
    if df_rep.empty:
        st.info("No hay repuestos registrados.")
        return

    df_alertas_r = df_rep[df_rep['stock_actual'] <= df_rep['stock_minimo']].copy()
    if df_alertas_r.empty:
        st.toast("✅ Todo el inventario está en niveles óptimos.")
        return

    df_alertas_r['Déficit'] = (df_alertas_r['stock_minimo'] - df_alertas_r['stock_actual']).clip(lower=0)
    df_sin = df_alertas_r[df_alertas_r['stock_actual'] == 0]
    df_bajo = df_alertas_r[df_alertas_r['stock_actual'] > 0]

    if not df_sin.empty:
        st.error(f"🔴 {len(df_sin)} repuestos SIN STOCK")
        st.dataframe(df_sin[['nombre', 'referencia', 'categoria', 'stock_actual', 'stock_minimo', 'Déficit', 'ubicacion']],
                     hide_index=True, use_container_width=True)
    if not df_bajo.empty:
        st.warning(f"🟡 {len(df_bajo)} repuestos con STOCK BAJO")
        st.dataframe(df_bajo[['nombre', 'referencia', 'categoria', 'stock_actual', 'stock_minimo', 'Déficit', 'ubicacion']],
                     hide_index=True, use_container_width=True)

    st.markdown("---")
    if st.button("📲 ENVIAR RESUMEN DE ALERTAS POR TELEGRAM", type="primary", use_container_width=True):
        resumen = f"🚨 *RESUMEN DE STOCK — ORIÓN*\n\n"
        resumen += f"🔴 Sin stock: {len(df_sin)} repuestos\n"
        resumen += f"🟡 Bajo stock: {len(df_bajo)} repuestos\n\n"
        for _, r in df_alertas_r.iterrows():
            icono = "🔴" if r['stock_actual'] == 0 else "🟡"
            resumen += f"{icono} {r['nombre']} — Stock: {r['stock_actual']}/{r['stock_minimo']}\n"
        df_admins = df_users[df_users['rol'] == 'Admin'] if not df_users.empty else pd.DataFrame()
        enviados = 0
        for _, adm in df_admins.iterrows():
            if adm.get('chat_id'):
                notificar_telegram(adm['chat_id'], resumen)
                enviados += 1
        if enviados > 0:
            agregar_notificacion('success', f'Resumen enviado a {enviados} administrador(es).')
        else:
            agregar_notificacion('warning', 'No hay admins con chat_id configurado.')
        st.rerun()


# ==============================================================================
# 🛠️ HELPERS
# ==============================================================================
def _notificar_stock_bajo(rep_sel, nuevo_stock, unidad, stock_min, df_users):
    mensaje_tel = (
        f"⚠️ *ALERTA STOCK BAJO*\n\n"
        f"🔩 *Repuesto:* {rep_sel}\n"
        f"📦 *Stock actual:* {nuevo_stock} {unidad}\n"
        f"🔻 *Stock mínimo:* {stock_min}"
    )
    df_admins = df_users[df_users['rol'] == 'Admin'] if not df_users.empty else pd.DataFrame()
    for _, adm in df_admins.iterrows():
        if adm.get('chat_id'):
            notificar_telegram(adm['chat_id'], mensaje_tel)
