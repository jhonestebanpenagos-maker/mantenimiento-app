import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime


# ==============================================================================
# 📊 GRÁFICOS
# ==============================================================================

def graficar_ordenes_por_tecnico(df_ordenes, df_users):
    """Muestra gráfico compacto de órdenes por técnico."""
    df_ordenes = pd.DataFrame(df_ordenes) if not isinstance(df_ordenes, pd.DataFrame) else df_ordenes
    df_users = pd.DataFrame(df_users) if not isinstance(df_users, pd.DataFrame) else df_users

    if df_ordenes.empty or df_users.empty:
        st.info("No hay datos suficientes para mostrar la carga por técnico.")
        return

    user_map = dict(zip(df_users['id'].astype(str), df_users['nombre']))
    df_tecnicos = df_ordenes.copy()
    df_tecnicos['tecnico_nombre'] = df_tecnicos['tecnico_asignado'].astype(str).map(user_map).fillna('Sin asignar')

    conteo_tecnicos = df_tecnicos.groupby(['tecnico_nombre', 'estado']).size().reset_index(name='cantidad')
    abiertas = conteo_tecnicos[conteo_tecnicos['estado'] == 'Abierta']
    concluidas = conteo_tecnicos[conteo_tecnicos['estado'] == 'Concluida']
    tecnicos_unicos = df_tecnicos['tecnico_nombre'].unique()

    datos_final = []
    for tecnico in tecnicos_unicos:
        abierta_count = abiertas[abiertas['tecnico_nombre'] == tecnico]['cantidad'].sum()
        concluida_count = concluidas[concluidas['tecnico_nombre'] == tecnico]['cantidad'].sum()
        total_tecnico = abierta_count + concluida_count
        datos_final.append({
            'Técnico': tecnico, 'Abiertas': abierta_count,
            'Concluidas': concluida_count, 'Total': total_tecnico
        })

    df_final = pd.DataFrame(datos_final).sort_values('Total', ascending=True)

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
        font=dict(color='white'), showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=250,
        xaxis=dict(title=None),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
    )
    fig.update_traces(textfont_size=14, textposition='outside', marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)


def graficar_gantt_mantenimiento(df_ordenes, df_users):
    if df_ordenes.empty:
        st.info("No hay datos para generar el calendario.")
        return

    df_gantt = df_ordenes.copy()
    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}
    df_gantt['Tecnico'] = df_gantt['tecnico_asignado'].map(map_user).fillna("Sin Asignar")
    df_gantt['Inicio'] = pd.to_datetime(df_gantt['fecha_creacion'])
    now = datetime.now()
    df_gantt['Final_Real'] = pd.to_datetime(df_gantt['fecha_cierre'])
    df_gantt['Final_Visual'] = df_gantt['Final_Real'].fillna(now)
    df_gantt['Duracion_Horas'] = ((df_gantt['Final_Visual'] - df_gantt['Inicio'])
                                  .dt.total_seconds() / 3600).round(1)

    fig = px.timeline(
        df_gantt, x_start="Inicio", x_end="Final_Visual", y="Tecnico",
        color="criticidad",
        color_discrete_map={"Alta": "#EF4444", "Media": "#F59E0B", "Baja": "#10B981", "Crítica": "#7F1D1D"},
        hover_data=["id", "descripcion", "estado", "Duracion_Horas"],
        title="📅 Línea de Tiempo de Ejecución", height=400
    )
    fig.update_yaxes(categoryorder="total ascending", title=None)
    fig.update_xaxes(title="Tiempo de Ejecución")
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(255,255,255,0.05)',
        font=dict(color='white'), legend=dict(orientation="h", y=1.1),
        margin=dict(l=10, r=10, t=40, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)


def mostrar_tops_ordenes(df_ordenes):
    if df_ordenes.empty:
        return
    now = datetime.now()
    df_ordenes['fecha_dt'] = pd.to_datetime(df_ordenes['fecha_creacion'])
    df_abiertas = df_ordenes[df_ordenes['estado'] != 'Concluida'].copy()

    if df_abiertas.empty:
        st.toast("¡Increíble! No hay órdenes pendientes antiguas.")
        return

    df_abiertas['dias_abierta'] = (now - df_abiertas['fecha_dt']).dt.days

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🐢 Top 10 Más Antiguas")
        df_old = df_abiertas.sort_values('dias_abierta', ascending=False).head(10)
        st.dataframe(
            df_old[['id', 'descripcion', 'dias_abierta', 'tecnico_asignado']],
            column_config={
                "id": st.column_config.NumberColumn("ID", format="#%d", width="small"),
                "descripcion": st.column_config.TextColumn("Problema", width="medium"),
                "dias_abierta": st.column_config.ProgressColumn("Días Esperando",
                                  format="%d días", min_value=0, max_value=30),
                "tecnico_asignado": st.column_config.TextColumn("Técnico ID")
            },
            hide_index=True, use_container_width=True, height=300
        )
    with c2:
        st.markdown("### 🔥 Top Críticas Pendientes")
        df_crit = df_abiertas[df_abiertas['criticidad'].isin(['Alta', 'Crítica'])] \
            .sort_values('fecha_dt').head(10)
        if df_crit.empty:
            st.info("No hay órdenes críticas pendientes.")
        else:
            st.dataframe(
                df_crit[['id', 'criticidad', 'descripcion', 'estado']],
                column_config={
                    "id": st.column_config.NumberColumn("ID", format="#%d", width="small"),
                    "criticidad": st.column_config.TextColumn("Nivel"),
                    "descripcion": st.column_config.TextColumn("Problema"),
                    "estado": st.column_config.TextColumn("Estado")
                },
                hide_index=True, use_container_width=True, height=300
            )


def graficar_torta_tipo(df):
    if df.empty:
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
    df_ordenes = pd.DataFrame(df_ordenes) if not isinstance(df_ordenes, pd.DataFrame) else df_ordenes
    df_users = pd.DataFrame(df_users) if not isinstance(df_users, pd.DataFrame) else df_users

    if df_ordenes.empty:
        st.info("No hay datos para graficar.")
        return

    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}
    df_vis = df_ordenes.copy()
    df_vis['Tecnico'] = df_vis['tecnico_asignado'].map(map_user).fillna("Sin Asignar")
    now = datetime.now()
    df_vis['Inicio'] = pd.to_datetime(df_vis['fecha_creacion'])
    df_vis['Cierre_Calc'] = pd.to_datetime(df_vis['fecha_cierre']).fillna(now)
    df_vis['Dias_Activa'] = ((df_vis['Cierre_Calc'] - df_vis['Inicio'])
                              .dt.total_seconds() / 86400).round(1)

    color_map_crit = {"Alta": "#EF4444", "Media": "#F59E0B", "Baja": "#10B981", "Crítica": "#7F1D1D"}

    st.markdown("### 🌊 Flujo de Distribución")
    st.caption("Sigue las líneas: Técnico ➔ Criticidad ➔ Estado actual.")
    fig_flow = px.parallel_categories(
        df_vis, dimensions=['Tecnico', 'criticidad', 'estado'],
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


# ==============================================================================
# 🏭 KPIs INDUSTRIALES — MTTR & MTBF
# ==============================================================================
def mostrar_kpis_industriales(df_ordenes, df_act):
    df_ordenes = pd.DataFrame(df_ordenes) if not isinstance(df_ordenes, pd.DataFrame) else df_ordenes
    df_act = pd.DataFrame(df_act) if not isinstance(df_act, pd.DataFrame) else df_act

    if df_ordenes.empty:
        st.info("No hay órdenes suficientes para calcular KPIs.")
        return

    map_act = dict(zip(df_act['id'], df_act['nombre'])) if not df_act.empty else {}
    df_k = df_ordenes[df_ordenes['estado'] == 'Concluida'].copy()

    if df_k.empty:
        st.info("Sin órdenes concluidas para calcular KPIs industriales.")
        return

    df_k['fecha_creacion'] = pd.to_datetime(df_k['fecha_creacion'])
    df_k['fecha_cierre'] = pd.to_datetime(df_k['fecha_cierre'])
    df_k['duracion_horas'] = ((df_k['fecha_cierre'] - df_k['fecha_creacion'])
                               .dt.total_seconds() / 3600)
    df_k['Activo'] = df_k['activo_id'].map(map_act).fillna('Desconocido')

    mttr = df_k.groupby('Activo')['duracion_horas'].mean().reset_index()
    mttr.columns = ['Activo', 'MTTR_horas']
    mttr = mttr.sort_values('MTTR_horas', ascending=False).head(10)
    mttr['MTTR_horas'] = mttr['MTTR_horas'].round(1)

    df_sorted = df_k.sort_values(['Activo', 'fecha_creacion'])
    df_sorted['tiempo_entre_fallas'] = (
        df_sorted.groupby('Activo')['fecha_creacion'].diff().dt.total_seconds() / 3600
    )
    mtbf = df_sorted.groupby('Activo')['tiempo_entre_fallas'].mean().reset_index()
    mtbf.columns = ['Activo', 'MTBF_horas']
    mtbf = mtbf.dropna().sort_values('MTBF_horas', ascending=False).head(10)
    mtbf['MTBF_horas'] = mtbf['MTBF_horas'].round(1)

    st.markdown("### 🏭 KPIs Industriales")
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    mttr_prom = df_k['duracion_horas'].mean()
    mtbf_prom = df_sorted['tiempo_entre_fallas'].mean()
    activo_critico = mttr['Activo'].iloc[0] if not mttr.empty else "N/A"
    activo_confiable = mtbf['Activo'].iloc[-1] if not mtbf.empty else "N/A"

    col_r1.metric("⏱️ MTTR Promedio", f"{mttr_prom:.1f}h")
    col_r2.metric("🔁 MTBF Promedio", f"{mtbf_prom:.1f}h" if not pd.isna(mtbf_prom) else "N/A")
    col_r3.metric("🔴 Más Difícil de Reparar", activo_critico.split()[0] if activo_critico != "N/A" else "N/A")
    col_r4.metric("🟢 Más Confiable", activo_confiable.split()[0] if activo_confiable != "N/A" else "N/A")

    st.markdown("---")
    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.markdown("<span class='chart-header'>⏱️ MTTR — Tiempo Medio de Reparación</span>", unsafe_allow_html=True)
        st.caption("Menos horas = más fácil de reparar")
        if not mttr.empty:
            fig_mttr = px.bar(mttr, x='MTTR_horas', y='Activo', orientation='h',
                              color='MTTR_horas', color_continuous_scale='Reds', text='MTTR_horas')
            fig_mttr.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                   font=dict(color='white'), height=300, showlegend=False,
                                   coloraxis_showscale=False, margin=dict(l=0, r=0, t=10, b=0),
                                   yaxis=dict(title=None), xaxis=dict(title="Horas promedio"))
            fig_mttr.update_traces(texttemplate='%{text}h', textposition='outside')
            st.plotly_chart(fig_mttr, use_container_width=True)
        else:
            st.info("Sin datos suficientes.")

    with col_m2:
        st.markdown("<span class='chart-header'>🔁 MTBF — Tiempo Medio Entre Fallas</span>", unsafe_allow_html=True)
        st.caption("Más horas = equipo más confiable")
        if not mtbf.empty:
            fig_mtbf = px.bar(mtbf, x='MTBF_horas', y='Activo', orientation='h',
                              color='MTBF_horas', color_continuous_scale='Greens', text='MTBF_horas')
            fig_mtbf.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                   font=dict(color='white'), height=300, showlegend=False,
                                   coloraxis_showscale=False, margin=dict(l=0, r=0, t=10, b=0),
                                   yaxis=dict(title=None), xaxis=dict(title="Horas promedio"))
            fig_mtbf.update_traces(texttemplate='%{text}h', textposition='outside')
            st.plotly_chart(fig_mtbf, use_container_width=True)
        else:
            st.info("Sin datos suficientes para MTBF (se necesitan 2+ fallas por activo).")


# ==============================================================================
# 🚦 SEMÁFORO DE CARGA DE TÉCNICOS
# ==============================================================================
def semaforo_tecnicos(df_ordenes, df_users):
    if df_ordenes.empty or df_users.empty:
        return

    LIMITE_OCUPADO = 3
    LIMITE_SOBRECARGADO = 6

    abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta']
    conteo = abiertas.groupby('tecnico_asignado').size().reset_index(name='ordenes_abiertas')
    conteo['tecnico_asignado'] = conteo['tecnico_asignado'].astype(str)

    st.markdown("### 🚦 Estado de Carga — Técnicos")
    st.caption("Basado en órdenes con estado Abierta.")

    cols = st.columns(len(df_users))
    for i, (_, user) in enumerate(df_users.iterrows()):
        uid = str(user['id'])
        nom = user['nombre']
        rol_u = user['rol']
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

        with cols[i]:
            st.markdown(f"""
            <div style="background-color:rgba(30,41,59,0.8);border:2px solid {color};border-radius:12px;padding:15px 10px;text-align:center;margin:5px 0;">
                <div style="font-size:1.8rem;margin-bottom:5px;">{icono}</div>
                <div style="color:white;font-weight:700;font-size:0.9rem;margin-bottom:2px;">{nom.split()[0]}</div>
                <div style="color:#9CA3AF;font-size:0.75rem;margin-bottom:8px;">{rol_u}</div>
                <div style="color:{color};font-weight:800;font-size:1.8rem;line-height:1;">{n}</div>
                <div style="color:#9CA3AF;font-size:0.7rem;margin-bottom:8px;">órdenes</div>
                <div style="background-color:rgba(255,255,255,0.1);border-radius:4px;height:4px;margin:5px 0;">
                    <div style="background-color:{color};width:{barra}%;height:4px;border-radius:4px;"></div>
                </div>
                <div style="color:{color};font-size:0.7rem;font-weight:700;letter-spacing:1px;margin-top:4px;">{estado}</div>
            </div>
            """, unsafe_allow_html=True)


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
        df_solicitudes['estado'] = df_solicitudes['estado'].astype(str).str.strip()
        n_solicitudes = len(df_solicitudes[df_solicitudes['estado'] == 'Pendiente'])

    total = len(df_ordenes)
    pendientes = por_validar = concluidas = devueltas_calidad = 0
    porcentaje_concluidas = 0

    if not df_ordenes.empty:
        df_ordenes['estado'] = df_ordenes['estado'].astype(str).str.strip()
        pendientes = len(df_ordenes[df_ordenes['estado'] == 'Abierta'])
        por_validar = len(df_ordenes[df_ordenes['estado'] == 'Por Validar'])
        concluidas = len(df_ordenes[df_ordenes['estado'] == 'Concluida'])
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
