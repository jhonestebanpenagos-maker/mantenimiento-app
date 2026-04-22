# ==============================================================================
# utils/charts.py — OPTIMIZADO
# ==============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime


# ==============================================================================
# 🧮 CÁLCULOS CACHEADOS
# ==============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def _calcular_datos_tecnicos(df_ordenes_hash, df_ordenes_data, df_users_data):
    """Cachea el procesamiento de datos por técnico."""
    df_ordenes = pd.DataFrame(df_ordenes_data)
    df_users = pd.DataFrame(df_users_data)

    if df_ordenes.empty or df_users.empty:
        return []

    user_map = dict(zip(df_users['id'].astype(str), df_users['nombre']))
    df = df_ordenes.copy()
    df['tecnico_nombre'] = df['tecnico_asignado'].astype(str).map(user_map).fillna('Sin asignar')

    conteo = df.groupby(['tecnico_nombre', 'estado']).size().reset_index(name='cantidad')
    abiertas = conteo[conteo['estado'] == 'Abierta']
    concluidas = conteo[conteo['estado'] == 'Concluida']

    datos = []
    for tecnico in df['tecnico_nombre'].unique():
        a = abiertas[abiertas['tecnico_nombre'] == tecnico]['cantidad'].sum()
        c = concluidas[concluidas['tecnico.append({'Técnico': tecnico, 'Abiertas': a, 'Concluidas': c, 'Total': a + c})
    return datos


@st.cache_data(ttl=60, show_spinner=False)
def _calcular_kpis(df_ordenes_data, df_act_data, df_planes_data):
    """Cachea todos los cálculos KPI de una vez."""
    df_ordenes = pd.DataFrame(df_ordenes_data_nombre'] == tecnico]['cantidad'].sum()
        datos)
    df_act = pd.DataFrame(df_act_data)

    if df_ordenes.empty:
        return None

    now = datetime.now()
    map_act = dict(zip(df_act['id'], df_act['nombre'])) if not df_act.empty else {}

    # ── Conteos básicos ──
    total = len(df_ordenes)
    df_k = df_ordenes[df_ordenes['estado'] == 'Concluida'].copy()
    concluidas = len(df_k)
    abiertas = len(df_ordenes[df_ordenes['estado'] == 'Abierta'])
    por_validar = len(df_ordenes[df_ordenes['estado'] == 'Por Validar'])

    preventivas = len(df_ordenes[df_ordenes['tipo_mantenimiento'] == 'Preventivo'])
    correctivas = len(df_ordenes[df_ordenes['tipo_mantenimiento'] == 'Correctivo'])
    pct_preventivo = (preventivas / total * 100) if total > 0 else 0

    # ── Backlog ──
    df_abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta'].copy()
    if not df_abiertas.empty:
        df_abiertas['fecha_creacion'] = pd.to_datetime(df_abiertas['fecha_creacion'])
        backlog_horas = ((now - df_abiertas['fecha_creacion']).dt.total_seconds() / 3600).sum()
        backlog_ordenes = len(df_abiertas)
    else:
        backlog_horas = 0
        backlog_ordenes = 0

    # ── MTTR / MTBF (calculado una sola vez) ──
    mttr_prom = mtbf_prom = disponibilidad = tasa_falla = 0
    mttr_por_activo = []
    mtbf_por_activo = []
    disponibilidad_por_activo = []

    if not df_k.empty:
        df_k['fecha_creacion'] = pd.to_datetime(df_k['fecha_creacion'])
        df_k['fecha_cierre'] = pd.to_datetime(df_k['fecha_cierre'])
        df_k['duracion_horas'] = (df_k['fecha_cierre'] - df_k['fecha_creacion']).dt.total_seconds() / 3600
        mttr_prom = df_k['duracion_horas'].mean()

        df_k['Activo'] = df_k['activo_id'].map(map_act).fillna('Desconocido')

        # MTTR por activo
        mttr_df = df_k.groupby('Activo')['duracion_horas'].mean().round(1).reset_index()
        mttr_df.columns = ['Activo', 'MTTR_horas']
        mttr_por_activo = mttr_df.sort_values('MTTR_horas', ascending=False).head(10).to_dict('records')

        # MTBF por activo (solo una vez)
        df_sorted = df_k.sort_values(['activo_id', 'fecha_creacion']).copy()
        df_sorted['Activo'] = df_sorted['activo_id'].map(map_act).fillna('Desconocido')
        df_sorted['tiempo_entre_fallas'] = (
            df_sorted.groupby('activo_id')['fecha_creacion'].diff().dt.total_seconds() / 3600
        )
        mtbf_activo = df_sorted.groupby('Activo')['tiempo_entre_fallas'].mean().reset_index()
        mtbf_activo.columns = ['Activo', 'MTBF']

        mtbf_prom = df_sorted['tiempo_entre_fallas'].mean()

        if not pd.isna(mtbf_prom) and mtbf_prom > 0:
            disponibilidad = (mtbf_prom / (mtbf_prom + mttr_prom)) * 100
            tasa_falla = 1000 / mtbf_prom

        # MTBF top 10
        mtbf_top = mtbf_activo.dropna().sort_values('MTBF', ascending=False).head(10)
        mtbf_por_activo = [
            {'Activo': r['Activo'], 'MTBF_horas': round(r['MTBF'], 1)}
            for _, r in mtbf_top.iterrows()
        ]

        # Disponibilidad por activo
        df_disp = df_k.groupby('Activo')['duracion_horas'].mean().reset_index()
        df_disp.columns = ['Activo', 'MTTR']
        df_disp = df_disp.merge(mtbf_activo, on='Activo', how='left')
        df_disp['Disponibilidad'] = (df_disp['MTBF'] / (df_disp['MTBF'] + df_disp['MTTR']) * 100).round(1)
        df_disp = df_disp.dropna(subset=['Disponibilidad']).sort_values('Disponibilidad', ascending=True).tail(15)
        disponibilidad_por_activo = df_disp.to_dict('records')

    # ── Cumplimiento de planes ──
    cumplimiento_planes = None
    total_planes = 0
    if df_planes_data:
        df_planes = pd.DataFrame(df_planes_data)
        if not df_planes.empty:
            df_planes['ultima_ejecucion'] = pd.to_datetime(df_planes['ultima_ejecucion'])
            df_planes['proxima'] = df_planes['ultima_ejecucion'] + pd.to_timedelta(df_planes['frecuencia_dias'], unit='D')
            vencidos = len(df_planes[df_planes['proxima'] < now])
            total_planes = len(df_planes)
            cumplimiento_planes = ((total_planes - vencidos) / total_planes * 100) if total_planes > 0 else 100

    return {
        'total': total, 'concluidas': concluidas, 'abiertas': abiertas, 'por_validar': por_validar,
        'preventivas': preventivas, 'correctivas': correctivas, 'pct_preventivo': pct_preventivo,
        'backlog_horas': backlog_horas, 'backlog_ordenes': backlog_ordenes,
        'mttr_prom': mttr_prom, 'mtbf_prom': mtbf_prom, 'disponibilidad': disponibilidad,
        'tasa_falla': tasa_falla, 'cumplimiento_planes': cumplimiento_planes, 'total_planes': total_planes,
        'mttr_por_activo': mttr_por_activo, 'mtbf_por_activo': mtbf_por_activo,
        'disponibilidad_por_activo': disponibilidad_por_activo,
    }


@st.cache_data(ttl=60, show_spinner=False)
def _calcular_tops(df_ordenes_data):
    """Cachea cálculos de tops (más antiguas, críticas)."""
    df = pd.DataFrame(df_ordenes_data)
    if df.empty:
        return [], []

    now = datetime.now()
    df['fecha_dt'] = pd.to_datetime(df['fecha_creacion'])
    df_abiertas = df[df['estado'] != 'Concluida'].copy()

    if df_abiertas.empty:
        return [], []

    df_abiertas['dias_abierta'] = (now - df_abiertas['fecha_dt']).dt.days

    top_antiguas = df_abiertas.sort_values('dias_abierta', ascending=False).head(10)
    top_antiguas_list = [
        {'id': r['id'], 'dias': int(r['dias_abierta']), 'desc': (r.get('descripcion', '') or '')[:45]}
        for _, r in top_antiguas.iterrows()
    ]

    top_criticas = df_abiertas[df_abiertas['criticidad'].isin(['Alta', 'Crítica'])].sort_values('fecha_dt').head(10)
    top_criticas_list = [
        {'id': r['id'], 'criticidad': r.get('criticidad', '?'), 'estado': r.get('estado', '?'),
         'desc': (r.get('descripcion', '') or '')[:45]}
        for _, r in top_criticas.iterrows()
    ]

    return top_antiguas_list, top_criticas_list


@st.cache_data(ttl=60, show_spinner=False)
def _calcular_flujo_datos(df_ordenes_data, df_users_data):
    """Cachea datos para gráfico de flujo y tiempos."""
    df = pd.DataFrame(df_ordenes_data)
    df_users = pd.DataFrame(df_users_data)

    if df.empty:
        return pd.DataFrame()

    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}
    now = datetime.now()

    df['Tecnico'] = df['tecnico_asignado'].astype(str).map(map_user).fillna("Sin Asignar")
    df['Inicio'] = pd.to_datetime(df['fecha_creacion'])
    df['Cierre_Calc'] = pd.to_datetime(df['fecha_cierre']).fillna(now)
    df['Dias_Activa'] = ((df['Cierre_Calc'] - df['Inicio']).dt.total_seconds() / 86400).round(1)

    return df[['Tecnico', 'criticidad', 'estado', 'Dias_Activa', 'id', 'descripcion']]


# ==============================================================================
# 📊 GRÁFICOS
# ==============================================================================

def graficar_ordenes_por_tecnico(df_ordenes, df_users):
    """Muestra gráfico compacto de órdenes por técnico."""
    datos = _calcular_datos_tecnicos(
        len(df_ordenes) if hasattr(df_ordenes, '__len__') else 0,
        df_ordenes.to_dict('records') if hasattr(df_ordenes, 'to_dict') else list(df_ordenes),
        df_users.to_dict('records') if hasattr(df_users, 'to_dict') else list(df_users)
    )

    if not datos:
        st.info("No hay datos suficientes para mostrar la carga por técnico.")
        return

    df_final = pd.DataFrame(datos).sort_values('Total', ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Concluidas', y=df_final['Técnico'], x=df_final['Concluidas'],
        orientation='h', marker=dict(color='#10B981', line=dict(width=0)),
        text=df_final['Concluidas'], textposition='inside',
        textfont=dict(color='white', size=12),
        hovertemplate='<b>%{y}</b><br>Concluidas: %{x}<extra></extra>'
    ))
    fig.add_trace(go.Bar(
        name='Abiertas', y=df_final['Técnico'], x=df_final['Abiertas'],
        orientation='h', marker=dict(color='#F59E0B', line=dict(width=0)),
        text=df_final['Abiertas'], textposition='inside',
        textfont=dict(color='white', size=12),
        hovertemplate='<b>%{y}</b><br>Abiertas: %{x}<extra></extra>'
    ))
    fig.update_layout(
        barmode='stack', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white', size=12), height=250,
        margin=dict(l=0, r=0, t=10, b=0), showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5,
                    font=dict(color='white', size=12), bgcolor='rgba(0,0,0,0)'),
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title=None),
        yaxis=dict(title=None, tickfont=dict(size=11))
    )
    fig.update_layout(dragmode=False, hovermode='y unified')
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def graficar_criticidad(df):
    if df.empty:
        return
    conteo = df['criticidad'].value_counts().reset_index()
    conteo.columns = ['Nivel', 'Cantidad']
    conteo['Nivel'] = conteo['Nivel'].astype(str).str.strip()

    orden_oficial = ["Baja", "Media", "Alta", "Crítica"]
    colores = {"Baja": "#10B981", "Media": "#F59E0B", "Alta": "#EA580C", "Crítica": "#EF4444"}
    conteo = conteo[conteo['Nivel'].isin(orden_oficial)]

    fig = px.bar(conteo, x='Nivel', y='Cantidad', color='Nivel',
                 color_discrete_map=colores, text='Cantidad',
                 category_orders={"Nivel": orden_oficial})
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
       :
        return
    conteo = df['tipo_mantenimiento'].value_counts().reset_index()
    conteo.columns = ['Tipo', 'Cantidad']
    colores_torta = ["#3B82F6", "#8B5CF6", "#EC4899"]
    fig = go.Figure(data=[go.Pie(
        labels=conteo['Tipo'], values=conteo['Cantidad'], hole=.5,
        marker=dict(colors=colores_torta, line=dict(color='#111827', width=2)),
        textinfo='label+percent', textfont=dict(color='white')
    )])
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', font=dict(color='white'),
        height=250, showlegend=False, margin=dict(l=0, r=0, t=10, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)


def graficar_estado_barras(df):
    if df.empty:
        return
    conteo = df['estado'].value_counts().reset_index()
    conteo.columns = ['Estado', 'Cantidad']
    colores = {"Abierta": "#F59E0B", "Concluida": "#10B981"}
    fig = px.bar(conteo, x='Cantidad', y='Estado', orientation='h',
                 color='Estado', color_discrete_map=colores, text='Cantidad')
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'), showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=250,
        xaxis=dict(showgrid=False), yaxis=dict(title=None)
    )
    fig.update_traces(textfont_size=14, textposition='inside')
    st.plotly_chart(fig, use_container_width=True)


def graficar_alternativas_visuales(df_ordenes, df_users):
    """Versión optimizada: solo renderiza si hay datos y limita puntos."""
    df_vis = _calcular_flujo_datos(
        df_ordenes.to_dict('records') if hasattr(df_ordenes, 'to_dict') else list(df_ordenes),
        df_users.to_dict('records') if hasattr(df_users, 'to_dict') else list(df_users)
    )

    if df_vis.empty:
        st.info("No hay datos para graficar.")
        return

    # Limitar a 200 puntos máximo para parallel_categories (es muy lento con más)
    df_limitado = df_vis.head(200) if len(df_vis) > 200 else df_vis

    st.markdown("### 🌊 Flujo de Distribución")
    st.caption("Sigue las líneas: Técnico ➔ Criticidad ➔ Estado actual.")
    fig_flow = px.parallel_categories(
        df_limitado, dimensions=['Tecnico', 'criticidad', 'estado'],
        color="Dias_Activa", color_continuous_scale=px.colors.sequential.Inferno,
        labels={'Tecnico': 'Personal', 'criticidad': 'Urgencia', 'estado': 'Situación'}
    )
    fig_flow.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=20, r=20, t=20, b=20),
        font=dict(color='white'), height=350
    )
    st.plotly_chart(fig_flow, use_container_width=True)

    st.markdown("---")
    st.markdown("### 🏎️ Tiempos de Respuesta (La Carrera)")
    st.caption("Cada punto es una Orden. Izquierda = Reciente/Rápido. Derecha = Antiguo/Lento.")

    color_map_crit = {"Alta": "#EF4444",.plotly_chart(fig, use_container_width=True)


def graf font=dict(color='white'), showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=250,
        xaxis=dict(title=None),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
    )
    fig.update_traces(textfont_size=14, textposition='outside', marker_line_width=0)
    sticar_torta_tipo(df):
    if df.empty "Media": "#10B981", "Crítica": "#7F1D1D"}
    fig_race = px.strip(
        df_vis, x="Dias_Activa", y="Tecnico", color="criticidad",
        color_discrete_map=color_map_crit, orientation="h", stripmode="overlay",
        hover_data=["id", "descripcion", "estado"]
    )
    fig_race.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(255,255,255,0.05)',
        font=dict(color='white'), height=300,
        xaxis=dict(title="Días desde creación", showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(title=None)
    )
    fig_race.add_vline(x=7, line_width=1, line_dash="dash", line_color="white",
                       annotation_text="Límite 7 días")
    st.plotly_chart(fig_race, use_container_width=True)


def mostrar_tops_ordenes(df_ordenes):
    top_antiguas, top_criticas = _calcular_tops(
        df_ordenes.to_dict('records') if hasattr(df_ordenes, 'to_dict') else list(df_ordenes)
    )

    if not top_antiguas and not top_criticas:
        st.toast("¡Increíble! No hay órdenes pendientes.")
        return

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🐢 Top 10 Más Antiguas")
        for item in top_antiguas:
            dias = item['dias']
            color_bar = "#EF4444" if dias > 14 else "#F59E0B" if dias > 7 else "#60A5FA"
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.03);border-left:3px solid {color_bar};padding:6px 10px;border-radius:0 4px 4px 0;margin-bottom:3px;">
                    <div style="display:flex;justify-content:space-between;font-size:0.8rem;">
                        <span style="color:#E5E7EB;font-weight:600;">OT #{item['id']}</span>
                        <span style="color:{color_bar};font-weight:700;">{dias} días</span>
                    </div>
                    <div style="color:#9CA3AF;font-size:0.7rem;">{item['desc']}...</div>
                </div>
                """, unsafe_allow_html=True)
            with col_btn:
                if st.button("⚙️", key=f"top_old_{item['id']}", help="Gestionar"):
                    st.session_state.current_page = "Ordenes de Trabajo"
                    st.session_state.jump_target = "orden"
                    st.session_state.jump_id = item['id']
                    st.rerun()

    with c2:
        st.markdown("### 🔥 Top Críticas Pendientes")
        if not top_criticas:
            st.info("No hay órdenes críticas pendientes.")
        else:
            for item in top_criticas:
                crit_icon = "🔴" if item['criticidad'] == 'Crítica' else "🟠"
                col_info, col_btn = st.columns([4, 1])
                with col_info:
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.03);border-left:3px solid #EF4444;padding:6px 10px;border-radius:0 4px 4px 0;margin-bottom:3px;">
                        <div style="display:flex;justify-content:space-between;font-size:0.8rem;">
                            <span style="color:#E5E7EB;font-weight:600;">{crit_icon} OT #{item['id']}</span>
                            <span style="color:#9CA3AF;">{item['estado']}</span>
                        </div>
                        <div style="color:#9CA3AF;font-size:0.7rem;">{item['desc']}...</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_btn:
                    if st.button("⚙️", key=f"top_crit_{item['id']}", help="Gestionar"):
                        st.session_state.current_page = "Ordenes de Trabajo"
                        st.session_state.jump_target = "orden"
                        st.session_state.jump_id = item['id']
                        st.rerun()


# ==============================================================================
# 🏭 KPIs INDUSTRIALES — UN SOLO CÁLCULO CACHEADO
# ==============================================================================
def mostrar_kpis_industriales(df_ordenes, df_act, df_planes=None):
    kpis = _calcular_kpis(
        df_ordenes.to_dict('records') if hasattr(df_ordenes, 'to_dict') else list(df_ordenes),
        df_act.to_dict('records') if hasattr(df_act, 'to_dict') else list(df_act),
        df_planes.to_dict('records') if df_planes is not None and hasattr(df_planes, 'to_dict') else (list(df_planes) if df_planes is not None else None)
    )

    if kpis is None:
        st.info("No hay órdenes suficientes para calcular KPIs.")
        return

    # Desempaquetar
    (total, concluidas, abiertas, por_validar, preventivas, correctivas,
     pct_preventivo, backlog_horas, backlog_ordenes, mttr_prom, mtbf_prom,
     disponibilidad, tasa_falla, cumplimiento_planes, total_planes,
     mttr_por_activo, mtbf_por_activo, disponibilidad_por_activo) = (
        kpis['total'], kpis['concluidas'], kpis['abiertas'], kpis['por_validar'],
        kpis['preventivas'], kpis['correctivas'], kpis['pct_preventivo'],
        kpis['backlog_horas'], kpis['backlog_ordenes'], kpis['mttr_prom'],
        kpis['mtbf_prom'], kpis['disponibilidad'], kpis['tasa_falla'],
        kpis['cumplimiento_planes'], kpis['total_planes'],
        kpis['mttr_por_activo'], kpis['mtbf_por_activo'], kpis['disponibilidad_por_activo']
    )

    # ── Scorecards ──
    st.markdown("### 🏭 Panel de KPIs Industriales")
    st.caption("Indicadores clave de rendimiento del mantenimiento")

    if disponibilidad >= 90:
        disp_color, disp_icono = "#10B981", "🟢"
    elif disponibilidad >= 70:
        disp_color, disp_icono = "#F59E0B", "🟡"
    else:
        disp_color, disp_icono = "#EF4444", "🔴"

    prev_color = "#10B981" if pct_preventivo >= 60 else "#F59E0B" if pct_preventivo >= 30 else "#EF4444"
    backlog_color = "#EF4444" if backlog_horas > 200 else "#F59E0B" if backlog_horas > 50 else "#10B981"

    sc1, sc2, sc3, sc4 = st.columns(4)

    with sc1:
        st.markdown(f"""
        <div style="background:rgba(30,41,59,0.8);border:1px solid {disp_color};border-radius:12px;padding:20px;text-align:center;">
            <div style="font-size:0.8rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:1px;">Disponibilidad</div>
            <div style="font-size:2.5rem;font-weight:800;color:{disp_color};margin:8px 0;">{disp_icono} {disponibilidad:.1f}%</div>
            <div style="font-size:0.75rem;color:#6B7280;">MTBF/(MTBF+MTTR)</div>
        </div>
        """, unsafe_allow_html=True)

    with sc2:
        st.markdown(f"""
        <div style="background:rgba(30,41,59,0.8);border:1px solid {prev_color};border-radius:12px;padding:20px;text-align:center;">
            <div style="font-size:0.8rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:1px;">Mantenimiento Preventivo</div>
            <div style="font-size:2.5rem;font-weight:800;color:{prev_color};margin:8px 0;">{pct_preventivo:.1f}%</div>
            <div style="font-size:0.75rem;color:#6B7280;">{preventivas} prev / {correctivas} corr</div>
        </div>
        """, unsafe_allow_html=True)

    with sc3:
        st.markdown(f"""
        <div style="background:rgba(30,41,59,0.8);border:1px solid {backlog_color};border-radius:12px;padding:20px;text-align:center;">
            <div style="font-size:0.8rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:1px;">Backlog</div>
            <div style="font-size:2.5rem;font-weight:800;color:{backlog_color};margin:8px 0;">{backlog_horas:.0f}h</div>
            <div style="font-size:0.75rem;color:#6B7280;">{backlog_ordenes} órdenes pendientes</div>
        </div>
        """, unsafe_allow_html=True)

    with sc4:
        if cumplimiento_planes is not None:
            comp_color = "#10B981" if cumplimiento_planes >= 90 else "#F59E0B" if cumplimiento_planes >= 70 else "#EF4444"
            st.markdown(f"""
            <div style="background:rgba(30,41,59,0.8);border:1px solid {comp_color};border-radius:12px;padding:20px;text-align:center;">
                <div style="font-size:0.8rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:1px;">Cumplimiento Plan</div>
                <div style="font-size:2.5rem;font-weight:800;color:{comp_color};margin:8px 0;">{cumplimiento_planes:.1f}%</div>
                <div style="font-size:0.75rem;color:#6B7280;">{total_planes} planes configurados</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:rgba(30,41,59,0.8);border:1px solid #6B7280;border-radius:12px;padding:20px;text-align:center;">
                <div style="font-size:0.8rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:1px;">Tasa de Falla</div>
                <div style="font-size:2.5rem;font-weight:800;color:#60A5FA;margin:8px 0;">{tasa_falla:.2f}</div>
                <div style="font-size:0.75rem;color:#6B7280;">fallas por 1000h</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Tabla resumen ──
    st.markdown("#### 📋 Resumen de Indicadores")
    col_tbl1, col_tbl2 = st.columns(2)

    with col_tbl1:
        st.markdown("""
        <div style="background:rgba(30,41,59,0.5);border-radius:10px;padding:15px;">
            <h5 style="color:#F59E0B;margin:0 0 12px 0;">🔧 Fiabilidad</h5>
        """, unsafe_allow_html=True)
        for nombre, valor, desc in [
            ("⏱️ MTTR Promedio", f"{mttr_prom:.1f}h", "Tiempo medio de reparación"),
            ("🔁 MTBF Promedio", f"{mtbf_prom:.1f}h" if not pd.isna(mtbf_prom) and mtbf_prom > 0 else "N/A", "Tiempo medio entre fallas"),
            ("📊 Disponibilidad", f"{disponibilidad:.1f}%", "MTBF/(MTBF+MTTR)"),
            ("💥 Tasa de Falla", f"{tasa_falla:.2f}", "Fallas por 1000 horas"),
        ]:
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                <div><div style="color:#E5E7EB;font-size:0.9rem;">{nombre}</div><div style="color:#6B7280;font-size:0.7rem;">{desc}</div></div>
                <div style="color:#60A5FA;font-weight:700;font-size:1.1rem;">{valor}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_tbl2:
        st.markdown("""
        <div style="background:rgba(30,41,59,0.5);border-radius:10px;padding:15px;">
            <h5 style="color:#10B981;margin:0 0 12px 0;">📈 Gestión</h5>
        """, unsafe_allow_html=True)
        for nombre, valor, desc in [
            ("🛡️ % Preventivo", f"{pct_preventivo:.1f}%", f"{preventivas} preventivas de {total} total"),
            ("📋 Órdenes Totales", str(total), f"{concluidas} concluidas, {abiertas} abiertas"),
            ("⏳ Backlog", f"{backlog_horas:.0f}h", f"{backlog_ordenes} órdenes sin cerrar"),
            ("📐 Cumplimiento", f"{cumplimiento_planes:.1f}%" if cumplimiento_planes is not None else "N/A", f"{total_planes} planes de mantenimiento"),
        ]:
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                <div><div style="color:#E5E7EB;font-size:0.9rem;">{nombre}</div><div style="color:#6B7280;font-size:0.7rem;">{desc}</div></div>
                <div style="color:#60A5FA;font-weight:700;font-size:1.1rem;">{valor}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # ── Gráficos MTTR/MTBF (usando datos ya cacheados) ──
    if mttr_por_activo or mtbf_por_activo:
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.markdown("<span class='chart-header'>⏱️ MTTR — Top 10 más lentos</span>", unsafe_allow_html=True)
            st.caption("Menos horas = más fácil de reparar")
            if mttr_por_activo:
                df_mttr = pd.DataFrame(mttr_por_activo)
                fig_mttr = px.bar(df_mttr, x='MTTR_horas', y='Activo', orientation='h',
                                  color='MTTR_horas', color_continuous_scale='Reds', text='MTTR_horas')
                fig_mttr.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                       font=dict(color='white'), height=300, showlegend=False,
                                       coloraxis_showscale=False, margin=dict(l=0, r=0, t=10, b=0),
                                       yaxis=dict(title=None), xaxis=dict(title="Horas promedio"))
                fig_mttr.update_traces(texttemplate='%{text}h', textposition='outside')
                st.plotly_chart(fig_mttr, use_container_width=True)

        with col_g2:
            st.markdown("<span class='chart-header'>🔁 MTBF — Top 10 más confiables</span>", unsafe_allow_html=True)
            st.caption("Más horas = equipo más confiable")
            if mtbf_por_activo:
                df_mtbf = pd.DataFrame(mtbf_por_activo)
                fig_mtbf = px.bar(df_mtbf, x='MTBF_horas', y='Activo', orientation='h',
                                  color='MTBF_horas', color_continuous_scale='Greens', text='MTBF_horas')
                fig_mtbf.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                       font=dict(color='white'), height=300, showlegend=False,
                                       coloraxis_showscale=False, margin=dict(l=0, r=0, t=10, b=0),
                                       yaxis=dict(title=None), xaxis=dict(title="Horas promedio"))
                fig_mtbf.update_traces(texttemplate='%{text}h', textposition='outside')
                st.plotly_chart(fig_mtbf, use_container_width=True)

        st.markdown("---")

        # ── Disponibilidad por activo ──
        st.markdown("<span class='chart-header'>📊 Disponibilidad por Activo</span>", unsafe_allow_html=True)
        st.caption("Verde = alta disponibilidad | Rojo = necesita atención")

        if disponibilidad_por_activo:
            df_disp = pd.DataFrame(disponibilidad_por_activo)
            fig_disp = go.Figure()
            colores_disp = ['#10B981' if d >= 90 else '#F59E0B' if d >= 70 else '#EF4444' for d in df_disp['Disponibilidad']]
            fig_disp.add_trace(go.Bar(
                y=df_disp['Activo'], x=df_disp['Disponibilidad'], orientation='h',
                marker=dict(color=colores_disp),
                text=[f"{d:.1f}%" for d in df_disp['Disponibilidad']],
                textposition='outside', textfont=dict(color='white', size=11)
            ))
            fig_disp.add_vline(x=90, line_dash="dash", line_color="#10B981", annotation_text="Meta: 90%")
            fig_disp.add_vline(x=70, line_dash="dash", line_color="#F59E0B", annotation_text="Mínimo: 70%")
            fig_disp.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'), height=max(250, len(df_disp) * 30),
                margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
                xaxis=dict(title="% Disponibilidad", range=[0, 105], showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
                yaxis=dict(title=None)
            )
            st.plotly_chart(fig_disp, use_container_width=True)

        st.markdown("---")

        # ── Composición ──
        st.markdown("### 🧩 Composición del Mantenimiento")
        col_comp1, col_comp2 = st.columns(2)

        with col_comp1:
            st.markdown("<span class='chart-header'>🛡️ Preventivo vs Correctivo</span>", unsafe_allow_html=True)
            conteo_tipo = pd.DataFrame({
                'Tipo': ['Preventivo', 'Correctivo'],
                'Cantidad': [preventivas, correctivas]
            })
            colores_tipo = {"Preventivo": "#10B981", "Correctivo": "#EF4444"}
            fig_comp = go.Figure(data=[go.Pie(
                labels=conteo_tipo['Tipo'], values=conteo_tipo['Cantidad'], hole=.55,
                marker=dict(colors=[colores_tipo.get(t, '#6B7280') for t in conteo_tipo['Tipo']],
                           line=dict(color='#111827', width=2)),
                textinfo='label+percent', textfont=dict(color='white', size=12)
            )])
            fig_comp.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', font=dict(color='white'),
                height=280, showlegend=True,
                legend=dict(font=dict(color='white')),
                margin=dict(l=0, r=0, t=10, b=10)
            )
            st.plotly_chart(fig_comp, use_container_width=True)

        with col_comp2:
            st.markdown("<span class='chart-header'>📊 Score de Madurez</span>", unsafe_allow_html=True)
            st.caption("¿Qué tan maduro es tu mantenimiento?")

            if pct_preventivo >= 70:
                nivel, color_nivel, emoji_nivel = "EXCELENTE", "#10B981", "🏆"
            elif pct_preventivo >= 50:
                nivel, color_nivel, emoji_nivel = "BUENO", "#3B82F6", "👍"
            elif pct_preventivo >= 30:
                nivel, color_nivel, emoji_nivel = "EN DESARROLLO", "#F59E0B", "📈"
            else:
                nivel, color_nivel, emoji_nivel = "REACTIVO", "#EF4444", "⚠️"

            st.markdown(f"""
            <div style="text-align:center;padding:20px;">
                <div style="font-size:3rem;margin-bottom:10px;">{emoji_nivel}</div>
                <div style="font-size:1.5rem;font-weight:800;color:{color_nivel};">{nivel}</div>
                <div style="color:#9CA3AF;margin-top:5px;">{pct_preventivo:.1f}% Preventivo</div>
                <div style="margin-top:15px;background:rgba(255,255,255,0.1);border-radius:10px;height:12px;overflow:hidden;">
                    <div style="background:{color_nivel};width:{min(pct_preventivo, 100)}%;height:12px;border-radius:10px;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#6B7280;margin-top:4px;">
                    <span>0%</span><span>Meta: 70%</span><span>100%</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    else:
        st.info("Sin órdenes concluidas para calcular KPIs industriales.")


# ==============================================================================
# 🚦 SEMÁFORO DE CARGA DE TÉCNICOS
# ==============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def _calcular_semaforo(df_ordenes_data, df_users_data):
    """Cachea los datos del semáforo de técnicos."""
    df_ordenes = pd.DataFrame(df_ordenes_data)
    df_users = pd.DataFrame(df_users_data)

    if df_ordenes.empty or df_users.empty:
        return []

    LIMITE_OCUPADO = 3
    LIMITE_SOBRECARGADO = 6

    abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta']
    conteo = abiertas.groupby('tecnico_asignado').size().reset_index(name='ordenes_abiertas')
    conteo['tecnico_asignado'] = conteo['tecnico_asignado'].astype(str)

    resultado = []
    for _, user in df_users.iterrows():
        uid = str(user['id'])
        fila = conteo[conteo['tecnico_asignado'] == uid]
        n = int(fila['ordenes_abiertas'].values[0]) if not fila.empty else 0

        if n == 0:
            color, estado, icono, barra = "#10B981", "LIBRE", "🟢", 0
        elif n <= LIMITE_OCUPADO:
            color, estado, icono, barra = "#F59E0B", "OCUPADO", "🟡", 40
        elif n <= LIMITE_SOBRECARGADO:
            color, estado, icono, barra = "#EA580C", "CARGADO", "🟠", 70
        else:
            color, estado, icono, barra = "#EF4444", "CRÍTICO", "🔴", 100

        resultado.append({
            'id': uid, 'nombre': user['nombre'], 'rol': user['rol'],
            'ordenes': n, 'color': color, 'estado': estado,
            'icono': icono, 'barra': barra
        })
    return resultado


def semaforo_tecnicos(df_ordenes, df_users):
    datos = _calcular_semaforo(
        df_ordenes.to_dict('records') if hasattr(df_ordenes, 'to_dict') else list(df_ordenes),
        df_users.to_dict('records') if hasattr(df_users, 'to_dict') else list(df_users)
    )

    if not datos:
        return

    st.markdown("### 🚦 Estado de Carga — Técnicos")
    st.caption("Haz clic en un técnico para ver sus órdenes abiertas.")

    cols = st.columns(len(datos))
    for i, tec in enumerate(datos):
        with cols[i]:
            st.markdown(f"""
            <div style="background-color:rgba(30,41,59,0.8);border:2px solid {tec['color']};border-radius:12px;padding:15px 10px;text-align:center;margin:5px 0;">
                <div style="font-size:1.8rem;margin-bottom:5px;">{tec['icono']}</div>
                <div style="color:white;font-weight:700;font-size:0.9rem;margin-bottom:2px;">{tec['nombre'].split()[0]}</div>
                <div style="color:#9CA3AF;font-size:0.75rem;margin-bottom:8px;">{tec['rol']}</div>
                <div style="color:{tec['color']};font-weight:800;font-size:1.8rem;line-height:1;">{tec['ordenes']}</div>
                <div style="color:#9CA3AF;font-size:0.7rem;margin-bottom:8px;">órdenes</div>
                <div style="background-color:rgba(255,255,255,0.1);border-radius:4px;height:4px;margin:5px 0;">
                    <div style="background-color:{tec['color']};width:{tec['barra']}%;height:4px;border-radius:4px;"></div>
                </div>
                <div style="color:{tec['color']};font-size:0.7rem;font-weight:700;letter-spacing:1px;margin-top:4px;">{tec['estado']}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"Ver órdenes", key=f"sem_tec_{tec['id']}", use_container_width=True):
                st.session_state.current_page = "Ordenes de Trabajo"
                st.session_state.jump_target = "ordenes_por_activo"
                st.session_state.jump_id = None
                st.rerun()


# ==============================================================================
# 🤖 ASIGNACIÓN INTELIGENTE DE TÉCNICOS
# ==============================================================================
def sugerir_tecnico(df_ordenes, df_users):
    if df_users.empty:
        return None, None, 0

    df_tec = df_users[df_users['rol'].isin(['Tecnico', 'Programador'])].copy()
    if df_tec.empty:
        df_tec = df_users.copy()

    abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta'] if not df_ordenes.empty else pd.DataFrame()
    conteo = {}
    for _, u in df_tec.iterrows():
        uid = str(u['id'])
        n = len(abiertas[abiertas['tecnico_asignado'] == uid]) if not abiertas.empty else 0
        conteo[uid] = {'nombre': u['nombre'], 'ordenes': n, 'id': u['id']}

    ordenado = sorted(conteo.values(), key=lambda x: x['ordenes'])
    mejor = ordenado[0]
    return mejor['id'], mejor['nombre'], mejor['ordenes']


def render_sugerencia_tecnico(df_ordenes, df_users):
    id_sug, nom_sug, n_sug = sugerir_tecnico(df_ordenes, df_users)
    if not nom_sug:
        return None

    if n_sug == 0:
        color, estado = "#10B981", "LIBRE"
    elif n_sug <= 3:
        color, estado = "#F59E0B", "DISPONIBLE"
    else:
        color, estado = "#EA580C", "CARGADO"

    st.markdown(f"""
    <div style="background-color:rgba(16,185,129,0.1);border:1px solid {color};border-radius:8px;padding:12px 16px;margin-bottom:10px;display:flex;align-items:center;gap:15px;">
        <div style="font-size:1.5rem;">🤖</div>
        <div>
            <div style="color:{color};font-weight:700;font-size:0.85rem;">SUGERENCIA AUTOMÁTICA</div>
            <div style="color:white;font-size:1rem;font-weight:600;">{nom_sug}</div>
            <div style="color:#9CA3AF;font-size:0.8rem;">{n_sug} órdenes abiertas — {estado}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    return nom_sug


# ==============================================================================
# 📊 MÉTRICAS INTELIGENTES
# ==============================================================================
def mostrar_metricas_inteligentes(df_ordenes, df_users, df_solicitudes):
    n_solicitudes = 0
    if not df_solicitudes.empty:
        n_solicitudes = len(df_solicitudes[df_solicitudes['estado'].astype(str).str.strip() == 'Pendiente'])

    total = len(df_ordenes)
    pendientes = por_validar = concluidas = devueltas_calidad = 0
    porcentaje_concluidas = 0

    if not df_ordenes.empty:
        pendientes = len(df_ordenes[df_ordenes['estado'] == 'Abierta'])
        por_validar = len(df_ordenes[df_ordenes['estado'] == 'Por Validar'])
        concluidas = len(df_ordenes[df_ordenes['estado'] == 'Concluida'])
        if 'comentarios_validacion' in df_ordenes.columns:
            devueltas_calidad = len(df_ordenes[
                (df_ordenes['estado'] == 'Abierta') &
                (df_ordenes['comentarios_validacion'].notnull()) &
                (df_ordenes['comentarios_validacion'] != "")
            ])
        porcentaje_concluidas = (concluidas / total * 100) if total > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        color_sol = "normal" if n_solicitudes == 0 else "inverse"
        st.metric("📬 Solicitudes", n_solicitudes, "Nuevas en Buzón", delta_color=color_sol)
    with c2:
        st.metric("🔨 En Ejecución", pendientes,
                  f"{devueltas_calidad} Devueltas" if devueltas_calidad > 0 else None,
                  delta_color="inverse")
    with c3:
        st.metric("🧐 Calidad", por_validar, "Por Aprobar")
    with c4:
        st.metric("✅ Finalizadas", concluidas, f"{porcentaje_concluidas:.0f}%")
    with c5:
        st.metric("📦 Total OTs", total)
