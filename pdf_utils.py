from fpdf import FPDF
import requests
import tempfile
import os
import re
import pandas as pd
from datetime import datetime

# --- 🖨️ CLASE BASE PDF ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'REPORTE DE SERVICIO TECNICO', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, 'Sistema de Mantenimiento Orion', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    def _safe(self, text):
        """Convierte texto a latin-1 seguro para fpdf."""
        if not text:
            return ""
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    def section_title(self, title):
        self.set_fill_color(245, 158, 11)
        self.set_text_color(255, 255, 255)
        self.set_font('Arial', 'B', 11)
        self.cell(0, 8, self._safe(title), 0, 1, 'L', fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def label_value(self, label, value, w_label=45):
        self.set_font('Arial', 'B', 9)
        self.cell(w_label, 6, self._safe(label), 0, 0)
        self.set_font('Arial', '', 9)
        self.cell(0, 6, self._safe(value), 0, 1)

    def separator(self):
        self.ln(2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)


# ==============================================================================
# REPORTE COMPLETO DE UNA ORDEN INDIVIDUAL (REESCRITO)
# ==============================================================================
def generar_pdf_orden(orden, activo_nombre, tecnico_nombre):
    """
    Genera un PDF COMPLETO de una orden con todo su historial:
    - Info general + descripción + cierre
    - Historial de avances (bitácora)
    - Sesiones de tiempo
    - Costos registrados
    - Firmas de cierre
    - Archivos adjuntos
    """
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    oid = orden['id'] if hasattr(orden, '__getitem__') else orden.get('id', '?')
    estado = orden['estado'] if hasattr(orden, '__getitem__') else orden.get('estado', '?')
    fecha_creacion = (orden['fecha_creacion'][:10] if hasattr(orden, '__getitem__') else orden.get('fecha_creacion', ''))[:10]
    fecha_cierre = orden.get('fecha_cierre', '') if hasattr(orden, 'get') else ''
    if fecha_cierre:
        fecha_cierre = str(fecha_cierre)[:10]
    descripcion = orden['descripcion'] if hasattr(orden, '__getitem__') else orden.get('descripcion', '')
    comentarios_cierre = orden.get('comentarios_cierre', '') if hasattr(orden, 'get') else ''
    tipo_mant = orden.get('tipo_mantenimiento', 'N/A') if hasattr(orden, 'get') else 'N/A'
    criticidad = orden['criticidad'] if hasattr(orden, '__getitem__') else orden.get('criticidad', 'N/A')
    foto_url = orden.get('foto_cierre_url', '') if hasattr(orden, 'get') else ''

    # Color según estado
    if estado == 'Abierta':
        color_estado = (245, 158, 11)
    elif estado == 'Por Validar':
        color_estado = (59, 130, 246)
    elif estado == 'Concluida':
        color_estado = (16, 185, 129)
    else:
        color_estado = (107, 114, 128)

    # ══════════════════════════════════════════════
    # ENCABEZADO
    # ══════════════════════════════════════════════
    pdf.set_fill_color(*color_estado)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, pdf._safe(f'ORDEN DE TRABAJO #{oid}'), 0, 1, 'C', fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # ══════════════════════════════════════════════
    # 1. INFORMACION GENERAL
    # ══════════════════════════════════════════════
    pdf.section_title('1. INFORMACION GENERAL')
    pdf.label_value('Estado:', estado)
    pdf.label_value('Fecha Creacion:', fecha_creacion)
    if fecha_cierre:
        pdf.label_value('Fecha Cierre:', fecha_cierre)
    pdf.label_value('Activo:', str(activo_nombre))
    pdf.label_value('Tecnico:', str(tecnico_nombre))
    pdf.label_value('Tipo:', str(tipo_mant))
    pdf.label_value('Criticidad:', str(criticidad))
    pdf.ln(3)

    # ══════════════════════════════════════════════
    # 2. DESCRIPCION DEL PROBLEMA
    # ══════════════════════════════════════════════
    pdf.section_title('2. DESCRIPCION / FALLA REPORTADA')
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(0, 5, pdf._safe(str(descripcion)))
    pdf.ln(3)

    # ══════════════════════════════════════════════
    # 3. COMENTARIOS DE CIERRE
    # ══════════════════════════════════════════════
    if comentarios_cierre:
        pdf.section_title('3. INFORME DE REPARACION / CIERRE')
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(0, 5, pdf._safe(str(comentarios_cierre)))
        pdf.ln(3)

    # ══════════════════════════════════════════════
    # 4. EVIDENCIA FOTOGRAFICA
    # ══════════════════════════════════════════════
    if foto_url:
        pdf.section_title('4. EVIDENCIA FOTOGRAFICA')
        try:
            response = requests.get(str(foto_url), timeout=10)
            if response.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(response.content)
                    tmp_path = tmp.name
                if pdf.get_y() > 200:
                    pdf.add_page()
                pdf.image(tmp_path, x=10, w=80)
                os.remove(tmp_path)
                pdf.ln(5)
        except Exception as e:
            print(f"Error img pdf: {e}")
            pdf.set_font('Arial', 'I', 9)
            pdf.cell(0, 6, 'No se pudo cargar la imagen.', 0, 1)

    # ══════════════════════════════════════════════
    # 5. HISTORIAL DE AVANCES (BITACORA)
    # ══════════════════════════════════════════════
    try:
        from utils.db import supabase
        bit_res = supabase.table("bitacora").select("*") \
            .eq("orden_id", int(oid)) \
            .order("fecha").execute()
        bitacora = bit_res.data if bit_res.data else []
    except Exception:
        bitacora = []

    # Separar avances normales de cierre/sistema
    avances = []
    cierres = []
    for b in bitacora:
        msg = b.get('mensaje', '')
        if any(tag in msg for tag in ['[⏱️', '[💰', '[✍️', '[CIERRE', '🏁', '🔄 Orden RE-ABIERTA']):
            cierres.append(b)
        else:
            avances.append(b)

    if avances:
        pdf.section_title(f'5. HISTORIAL DE AVANCES ({len(avances)} registros)')
        for b in avances:
            if pdf.get_y() > 250:
                pdf.add_page()

            fecha_b = (b.get('fecha', '') or '')[:16].replace('T', ' ')
            usuario_b = b.get('usuario_text', 'Sistema')
            mensaje_b = b.get('mensaje', '')
            archivo_url = b.get('archivo_url', '')

            # Fila de fecha + usuario
            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(35, 5, pdf._safe(fecha_b), 0, 0)
            pdf.set_text_color(245, 158, 11)
            pdf.cell(40, 5, pdf._safe(usuario_b), 0, 1)
            pdf.set_text_color(0, 0, 0)

            # Mensaje
            pdf.set_font('Arial', '', 8)
            pdf.multi_cell(0, 4, pdf._safe(mensaje_b))

            # Adjunto
            if archivo_url:
                pdf.set_font('Arial', 'I', 7)
                pdf.set_text_color(59, 130, 246)
                nombre_archivo = str(archivo_url).split('/')[-1][:50]
                pdf.cell(0, 4, pdf._safe(f'  Adjunto: {nombre_archivo}'), 0, 1)
                pdf.set_text_color(0, 0, 0)

            pdf.separator()
    else:
        pdf.section_title('5. HISTORIAL DE AVANCES')
        pdf.set_font('Arial', 'I', 9)
        pdf.cell(0, 6, 'Sin avances registrados.', 0, 1)
        pdf.ln(3)

    # ══════════════════════════════════════════════
    # 6. REGISTROS DE SISTEMA (cierres, reaperturas, etc.)
    # ══════════════════════════════════════════════
    if cierres:
        pdf.section_title('6. REGISTROS DE SISTEMA')
        for b in cierres:
            if pdf.get_y() > 260:
                pdf.add_page()

            fecha_b = (b.get('fecha', '') or '')[:16].replace('T', ' ')
            usuario_b = b.get('usuario_text', 'Sistema')
            mensaje_b = b.get('mensaje', '')

            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(35, 5, pdf._safe(fecha_b), 0, 0)
            pdf.set_font('Arial', '', 8)
            pdf.cell(30, 5, pdf._safe(usuario_b), 0, 0)
            pdf.set_font('Arial', 'I', 8)
            pdf.multi_cell(0, 4, pdf._safe(mensaje_b))
            pdf.set_text_color(0, 0, 0)
            pdf.separator()

    # ══════════════════════════════════════════════
    # 7. TIEMPO DE EJECUCION
    # ══════════════════════════════════════════════
    try:
        from utils.time_tracking import obtener_resumen_sesiones, calcular_total_horas
        sesiones = obtener_resumen_sesiones(int(oid))
        total_horas = calcular_total_horas(int(oid))
    except Exception:
        sesiones = []
        total_horas = 0.0

    seccion_num = 7 if not cierres else 7
    pdf.section_title(f'{seccion_num}. TIEMPO DE EJECUCION')

    if sesiones:
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 6, pdf._safe(f'Total trabajado: {total_horas}h en {len(sesiones)} sesion(es)'), 0, 1)
        pdf.ln(2)

        pdf.set_fill_color(230, 230, 230)
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(35, 6, 'Inicio', 1, 0, 'C', fill=True)
        pdf.cell(35, 6, 'Fin', 1, 0, 'C', fill=True)
        pdf.cell(25, 6, 'Duracion', 1, 0, 'C', fill=True)
        pdf.cell(40, 6, 'Usuario', 1, 0, 'C', fill=True)
        pdf.cell(55, 6, 'Nota', 1, 1, 'C', fill=True)

        pdf.set_font('Arial', '', 8)
        for s in sesiones:
            inicio = (s.get('inicio', '') or '')[:16].replace('T', ' ')
            fin = (s.get('fin', '') or '')[:16].replace('T', ' ') if s.get('fin') else 'En curso'
            duracion = s.get('duracion', 'N/A')
            usuario_s = (s.get('usuario', '?') or '?')[:15]
            nota = (s.get('nota', '') or '')[:25]

            pdf.cell(35, 5, pdf._safe(inicio), 1, 0, 'C')
            pdf.cell(35, 5, pdf._safe(fin), 1, 0, 'C')
            pdf.cell(25, 5, pdf._safe(duracion), 1, 0, 'C')
            pdf.cell(40, 5, pdf._safe(usuario_s), 1, 0, 'C')
            pdf.cell(55, 5, pdf._safe(nota), 1, 1, 'C')
        pdf.ln(3)
    else:
        pdf.set_font('Arial', 'I', 9)
        pdf.cell(0, 6, 'Sin registros de tiempo.', 0, 1)
        pdf.ln(3)

    # ══════════════════════════════════════════════
    # 8. COSTOS
    # ══════════════════════════════════════════════
    try:
        from utils.costos import calcular_costos
        costos = calcular_costos(int(oid))
    except Exception:
        costos = {"total": 0, "registros": [], "mano_obra": 0, "repuesto": 0, "servicio_externo": 0, "material": 0}

    pdf.section_title('8. COSTOS')

    if costos.get('total', 0) > 0:
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(45, 6, pdf._safe(f'Mano de Obra: ${costos.get("mano_obra", 0):,.0f}'), 0, 0)
        pdf.cell(45, 6, pdf._safe(f'Repuestos: ${costos.get("repuesto", 0):,.0f}'), 0, 0)
        pdf.cell(50, 6, pdf._safe(f'Serv. Externos: ${costos.get("servicio_externo", 0):,.0f}'), 0, 0)
        pdf.cell(0, 6, pdf._safe(f'Material: ${costos.get("material", 0):,.0f}'), 0, 1)
        pdf.ln(2)

        pdf.set_fill_color(245, 158, 11)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 7, pdf._safe(f'TOTAL: ${costos["total"]:,.0f}'), 0, 1, 'C', fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

        if costos.get('registros'):
            pdf.set_fill_color(230, 230, 230)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(25, 6, 'Fecha', 1, 0, 'C', fill=True)
            pdf.cell(40, 6, 'Tipo', 1, 0, 'C', fill=True)
            pdf.cell(70, 6, 'Concepto', 1, 0, 'C', fill=True)
            pdf.cell(25, 6, 'Monto', 1, 0, 'C', fill=True)
            pdf.cell(30, 6, 'Usuario', 1, 1, 'C', fill=True)

            pdf.set_font('Arial', '', 8)
            for reg in costos['registros']:
                pdf.cell(25, 5, pdf._safe(reg.get('fecha', '')), 1, 0, 'C')
                pdf.cell(40, 5, pdf._safe((reg.get('tipo_label', '') or '')[:18]), 1, 0, 'L')
                pdf.cell(70, 5, pdf._safe((reg.get('concepto', '') or '')[:30]), 1, 0, 'L')
                pdf.cell(25, 5, pdf._safe(f"${reg.get('monto', 0):,.0f}"), 1, 0, 'R')
                pdf.cell(30, 5, pdf._safe((reg.get('usuario', '') or '')[:12]), 1, 1, 'C')
        pdf.ln(3)
    else:
        pdf.set_font('Arial', 'I', 9)
        pdf.cell(0, 6, 'Sin costos registrados.', 0, 1)
        pdf.ln(3)

    # ══════════════════════════════════════════════
    # 9. FIRMAS DE CIERRE
    # ══════════════════════════════════════════════
    try:
        from utils.firmas import obtener_firmas
        firmas = obtener_firmas(int(oid))
    except Exception:
        firmas = {"tecnico": None, "supervisor": None}

    pdf.section_title('9. FIRMAS DE CIERRE')

    for tipo, datos in firmas.items():
        label = "Tecnico" if tipo == "tecnico" else "Supervisor"
        if datos:
            fecha_firma = (datos.get('fecha', '') or '')[:16].replace('T', ' ')
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(5, 6, '', 0, 0)
            pdf.set_text_color(16, 185, 129)
            pdf.cell(10, 6, '[X]', 0, 0)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 6, pdf._safe(f'Firma {label}: {datos.get("usuario", "?")} (Doc: {datos.get("documento", "?")}) - {fecha_firma}'), 0, 1)
            if datos.get('observacion'):
                pdf.set_font('Arial', 'I', 8)
                pdf.cell(15, 5, '', 0, 0)
                pdf.cell(0, 5, pdf._safe(f'Obs: {datos["observacion"]}'), 0, 1)
        else:
            pdf.set_font('Arial', '', 9)
            pdf.cell(5, 6, '', 0, 0)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(10, 6, '[ ]', 0, 0)
            pdf.cell(0, 6, pdf._safe(f'Firma {label}: Pendiente'), 0, 1)
            pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    # ══════════════════════════════════════════════
    # 10. ARCHIVOS ADJUNTOS
    # ══════════════════════════════════════════════
    pdf.section_title('10. ARCHIVOS ADJUNTOS')
    archivos = []
    for b in bitacora:
        url = b.get('archivo_url', '')
        if url:
            archivos.append({
                'url': url,
                'fecha': (b.get('fecha', '') or '')[:10],
                'usuario': b.get('usuario_text', '?'),
                'nombre': str(url).split('/')[-1][:60]
            })

    if archivos:
        for a in archivos:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.set_font('Arial', '', 8)
            pdf.cell(25, 5, pdf._safe(a['fecha']), 0, 0)
            pdf.cell(30, 5, pdf._safe(a['usuario']), 0, 0)
            pdf.set_font('Arial', 'I', 8)
            pdf.set_text_color(59, 130, 246)
            pdf.cell(0, 5, pdf._safe(a['nombre']), 0, 1)
            pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_font('Arial', 'I', 9)
        pdf.cell(0, 6, 'Sin archivos adjuntos.', 0, 1)

    return pdf.output(dest='S').encode('latin-1')


# ==============================================================================
# REPORTE CONSOLIDADO DE ORDENES
# ==============================================================================
def generar_reporte_ordenes_pdf(ordenes_data, df_users, df_act, incluir_abiertas=True, incluir_cerradas=True):
    """
    Genera un reporte PDF consolidado con todas las órdenes filtradas.
    """
    ordenes_filtradas = []
    for o in ordenes_data:
        estado = o.get('estado', '')
        if incluir_abiertas and estado in ('Abierta', 'Por Validar'):
            ordenes_filtradas.append(o)
        if incluir_cerradas and estado in ('Concluida', 'Cancelada'):
            ordenes_filtradas.append(o)

    if not ordenes_filtradas:
        return None

    map_act = dict(zip(df_act['id'].astype(str), df_act['nombre'])) if not df_act.empty else {}
    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}

    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- PORTADA ---
    pdf.set_fill_color(30, 41, 59)
    pdf.rect(0, 0, 210, 297, 'F')

    pdf.set_y(60)
    pdf.set_text_color(245, 158, 11)
    pdf.set_font('Arial', 'B', 28)
    pdf.cell(0, 15, 'ORION', 0, 1, 'C')

    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', '', 14)
    pdf.cell(0, 10, 'REPORTE DE ORDENES DE TRABAJO', 0, 1, 'C')

    pdf.set_font('Arial', 'I', 10)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(0, 8, f'Generado: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'C')
    pdf.cell(0, 8, f'Total de ordenes: {len(ordenes_filtradas)}', 0, 1, 'C')

    abiertas = len([o for o in ordenes_filtradas if o.get('estado') == 'Abierta'])
    por_validar = len([o for o in ordenes_filtradas if o.get('estado') == 'Por Validar'])
    concluidas = len([o for o in ordenes_filtradas if o.get('estado') == 'Concluida'])
    canceladas = len([o for o in ordenes_filtradas if o.get('estado') == 'Cancelada'])

    pdf.ln(10)
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, f'Abiertas: {abiertas}  |  Por Validar: {por_validar}  |  Concluidas: {concluidas}  |  Canceladas: {canceladas}', 0, 1, 'C')

    # --- DETALLE DE CADA ORDEN ---
    for orden in ordenes_filtradas:
        pdf.add_page()
        oid = orden.get('id', '?')
        estado = orden.get('estado', '?')
        fecha_creacion = (orden.get('fecha_creacion', '') or '')[:10]
        fecha_cierre = (orden.get('fecha_cierre', '') or '')[:10]
        activo_id = str(orden.get('activo_id', ''))
        tecnico_id = str(orden.get('tecnico_asignado', ''))
        activo_nombre = map_act.get(activo_id, f'Activo #{activo_id}')
        tecnico_nombre = map_user.get(tecnico_id, 'Sin asignar')

        if estado == 'Abierta':
            color_estado = (245, 158, 11)
        elif estado == 'Por Validar':
            color_estado = (59, 130, 246)
        elif estado == 'Concluida':
            color_estado = (16, 185, 129)
        else:
            color_estado = (107, 114, 128)

        pdf.set_fill_color(*color_estado)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 13)
        pdf.cell(0, 10, pdf._safe(f'ORDEN DE TRABAJO #{oid}'), 0, 1, 'C', fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

        pdf.section_title('1. INFORMACION GENERAL')
        pdf.label_value('Estado:', estado)
        pdf.label_value('Fecha Creacion:', fecha_creacion)
        if fecha_cierre:
            pdf.label_value('Fecha Cierre:', fecha_cierre)
        pdf.label_value('Activo:', activo_nombre)
        pdf.label_value('Tecnico:', tecnico_nombre)
        pdf.label_value('Tipo:', orden.get('tipo_mantenimiento', 'N/A'))
        pdf.label_value('Criticidad:', orden.get('criticidad', 'N/A'))
        pdf.ln(3)

        pdf.section_title('2. DESCRIPCION / FALLA REPORTADA')
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(0, 5, pdf._safe(orden.get('descripcion', 'Sin descripcion.')))
        pdf.ln(3)

        comentarios = orden.get('comentarios_cierre', '')
        if comentarios:
            pdf.section_title('3. INFORME DE REPARACION / CIERRE')
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, pdf._safe(comentarios))
            pdf.ln(3)

        pdf.section_title('4. HISTORIAL DE EJECUCION')
        try:
            from utils.db import supabase
            bit_res = supabase.table("bitacora").select("*") \
                .eq("orden_id", int(oid)) \
                .order("fecha").execute()
            bitacora = bit_res.data if bit_res.data else []
        except Exception:
            bitacora = []

        if bitacora:
            for b in bitacora:
                fecha_b = (b.get('fecha', '') or '')[:16].replace('T', ' ')
                usuario_b = b.get('usuario_text', 'Sistema')
                mensaje_b = b.get('mensaje', '')
                archivo_url = b.get('archivo_url', '')

                if pdf.get_y() > 250:
                    pdf.add_page()

                pdf.set_font('Arial', 'B', 8)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(35, 5, pdf._safe(fecha_b), 0, 0)
                pdf.cell(35, 5, pdf._safe(usuario_b), 0, 1)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font('Arial', '', 8)
                pdf.multi_cell(0, 4, pdf._safe(mensaje_b))

                if archivo_url:
                    pdf.set_font('Arial', 'I', 7)
                    pdf.set_text_color(59, 130, 246)
                    nombre_archivo = str(archivo_url).split('/')[-1][:50]
                    pdf.cell(0, 4, pdf._safe(f'  Adjunto: {nombre_archivo}'), 0, 1)
                    pdf.set_text_color(0, 0, 0)

                pdf.separator()
        else:
            pdf.set_font('Arial', 'I', 9)
            pdf.cell(0, 6, 'Sin registros en bitacora.', 0, 1)
            pdf.ln(3)

        pdf.section_title('5. TIEMPO DE EJECUCION')
        try:
            from utils.time_tracking import obtener_resumen_sesiones, calcular_total_horas
            sesiones = obtener_resumen_sesiones(int(oid))
            total_horas = calcular_total_horas(int(oid))
        except Exception:
            sesiones = []
            total_horas = 0.0

        if sesiones:
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(0, 6, pdf._safe(f'Total trabajado: {total_horas}h en {len(sesiones)} sesion(es)'), 0, 1)
            pdf.ln(2)

            pdf.set_fill_color(230, 230, 230)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(35, 6, 'Inicio', 1, 0, 'C', fill=True)
            pdf.cell(35, 6, 'Fin', 1, 0, 'C', fill=True)
            pdf.cell(25, 6, 'Duracion', 1, 0, 'C', fill=True)
            pdf.cell(40, 6, 'Usuario', 1, 0, 'C', fill=True)
            pdf.cell(55, 6, 'Nota', 1, 1, 'C', fill=True)

            pdf.set_font('Arial', '', 8)
            for s in sesiones:
                inicio = (s.get('inicio', '') or '')[:16].replace('T', ' ')
                fin = (s.get('fin', '') or '')[:16].replace('T', ' ') if s.get('fin') else 'En curso'
                duracion = s.get('duracion', 'N/A')
                usuario_s = (s.get('usuario', '?') or '?')[:15]
                nota = (s.get('nota', '') or '')[:25]

                pdf.cell(35, 5, pdf._safe(inicio), 1, 0, 'C')
                pdf.cell(35, 5, pdf._safe(fin), 1, 0, 'C')
                pdf.cell(25, 5, pdf._safe(duracion), 1, 0, 'C')
                pdf.cell(40, 5, pdf._safe(usuario_s), 1, 0, 'C')
                pdf.cell(55, 5, pdf._safe(nota), 1, 1, 'C')
            pdf.ln(3)
        else:
            pdf.set_font('Arial', 'I', 9)
            pdf.cell(0, 6, 'Sin registros de tiempo.', 0, 1)
            pdf.ln(3)

        pdf.section_title('6. COSTOS')
        try:
            from utils.costos import calcular_costos
            costos = calcular_costos(int(oid))
        except Exception:
            costos = {"total": 0, "registros": [], "mano_obra": 0, "repuesto": 0, "servicio_externo": 0, "material": 0}

        if costos.get('total', 0) > 0:
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(40, 6, pdf._safe(f'Mano de Obra: ${costos.get("mano_obra", 0):,.0f}'), 0, 0)
            pdf.cell(40, 6, pdf._safe(f'Repuestos: ${costos.get("repuesto", 0):,.0f}'), 0, 0)
            pdf.cell(50, 6, pdf._safe(f'Serv. Externos: ${costos.get("servicio_externo", 0):,.0f}'), 0, 0)
            pdf.cell(0, 6, pdf._safe(f'Material: ${costos.get("material", 0):,.0f}'), 0, 1)
            pdf.ln(2)

            pdf.set_fill_color(245, 158, 11)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 7, pdf._safe(f'TOTAL: ${costos["total"]:,.0f}'), 0, 1, 'C', fill=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)
        else:
            pdf.set_font('Arial', 'I', 9)
            pdf.cell(0, 6, 'Sin costos registrados.', 0, 1)
            pdf.ln(3)

        pdf.section_title('7. FIRMAS DE CIERRE')
        try:
            from utils.firmas import obtener_firmas
            firmas = obtener_firmas(int(oid))
        except Exception:
            firmas = {"tecnico": None, "supervisor": None}

        for tipo, datos in firmas.items():
            label = "Tecnico" if tipo == "tecnico" else "Supervisor"
            if datos:
                fecha_firma = (datos.get('fecha', '') or '')[:16].replace('T', ' ')
                pdf.set_font('Arial', 'B', 9)
                pdf.set_text_color(16, 185, 129)
                pdf.cell(10, 6, '[X]', 0, 0)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 6, pdf._safe(f'Firma {label}: {datos.get("usuario", "?")} - {fecha_firma}'), 0, 1)
            else:
                pdf.set_font('Arial', '', 9)
                pdf.set_text_color(150, 150, 150)
                pdf.cell(10, 6, '[ ]', 0, 0)
                pdf.cell(0, 6, pdf._safe(f'Firma {label}: Pendiente'), 0, 1)
                pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

        pdf.section_title('8. ARCHIVOS ADJUNTOS')
        archivos = []
        for b in bitacora:
            url = b.get('archivo_url', '')
            if url:
                archivos.append({
                    'fecha': (b.get('fecha', '') or '')[:10],
                    'usuario': b.get('usuario_text', '?'),
                    'nombre': str(url).split('/')[-1][:60]
                })

        if archivos:
            for a in archivos:
                if pdf.get_y() > 260:
                    pdf.add_page()
                pdf.set_font('Arial', '', 8)
                pdf.cell(25, 5, pdf._safe(a['fecha']), 0, 0)
                pdf.cell(30, 5, pdf._safe(a['usuario']), 0, 0)
                pdf.set_font('Arial', 'I', 8)
                pdf.set_text_color(59, 130, 246)
                pdf.cell(0, 5, pdf._safe(a['nombre']), 0, 1)
                pdf.set_text_color(0, 0, 0)
        else:
            pdf.set_font('Arial', 'I', 9)
            pdf.cell(0, 6, 'Sin archivos adjuntos.', 0, 1)

    # --- RESUMEN FINAL ---
    pdf.add_page()
    pdf.section_title('RESUMEN EJECUTIVO')
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, pdf._safe(f'Total de ordenes en el reporte: {len(ordenes_filtradas)}'), 0, 1)
    pdf.cell(0, 8, pdf._safe(f'Abiertas: {abiertas}  |  Por Validar: {por_validar}  |  Concluidas: {concluidas}  |  Canceladas: {canceladas}'), 0, 1)
    pdf.ln(5)

    pdf.set_fill_color(245, 158, 11)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(15, 7, 'ID', 1, 0, 'C', fill=True)
    pdf.cell(25, 7, 'Estado', 1, 0, 'C', fill=True)
    pdf.cell(50, 7, 'Activo', 1, 0, 'C', fill=True)
    pdf.cell(30, 7, 'Tecnico', 1, 0, 'C', fill=True)
    pdf.cell(20, 7, 'Criticidad', 1, 0, 'C', fill=True)
    pdf.cell(25, 7, 'Fecha', 1, 0, 'C', fill=True)
    pdf.cell(25, 7, 'Tipo', 1, 1, 'C', fill=True)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 8)
    for orden in ordenes_filtradas:
        oid = orden.get('id', '?')
        estado = orden.get('estado', '?')[:12]
        activo = map_act.get(str(orden.get('activo_id', '')), '?')[:22]
        tecnico = map_user.get(str(orden.get('tecnico_asignado', '')), '?')[:12]
        criticidad = orden.get('criticidad', '?')[:10]
        fecha = (orden.get('fecha_creacion', '') or '')[:10]
        tipo = (orden.get('tipo_mantenimiento', '') or '?')[:12]

        fill = False
        if orden.get('estado') == 'Concluida':
            pdf.set_fill_color(220, 252, 231)
            fill = True
        elif orden.get('estado') == 'Cancelada':
            pdf.set_fill_color(254, 226, 226)
            fill = True

        pdf.cell(15, 6, str(oid), 1, 0, 'C', fill=fill)
        pdf.cell(25, 6, pdf._safe(estado), 1, 0, 'C', fill=fill)
        pdf.cell(50, 6, pdf._safe(activo), 1, 0, 'L', fill=fill)
        pdf.cell(30, 6, pdf._safe(tecnico), 1, 0, 'C', fill=fill)
        pdf.cell(20, 6, pdf._safe(criticidad), 1, 0, 'C', fill=fill)
        pdf.cell(25, 6, pdf._safe(fecha), 1, 0, 'C', fill=fill)
        pdf.cell(25, 6, pdf._safe(tipo), 1, 1, 'C', fill=fill)

        if fill:
            pdf.set_fill_color(255, 255, 255)

    return pdf.output(dest='S').encode('latin-1')


# ==============================================================================
# VISOR DE PDF ADJUNTO (para Streamlit)
# ==============================================================================
def render_pdf_viewer(url, titulo="Documento PDF"):
    """Renderiza un visor inline de PDF en Streamlit usando iframe."""
    if not url:
        st.warning("No hay URL de documento disponible.")
        return

    url_lower = url.lower()
    es_pdf = url_lower.endswith('.pdf') or 'raw' in url_lower or 'pdf' in url_lower

    if not es_pdf:
        st.info("Este archivo no parece ser un PDF. Usa el link directo para abrirlo.")
        st.markdown(f'<a href="{url}" target="_blank">📎 Abrir archivo</a>', unsafe_allow_html=True)
        return

    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"📄 {titulo}")
    with col2:
        st.markdown(f'<a href="{url}" target="_blank" style="font-size:0.8em;">🔗 Abrir en pestaña nueva</a>', unsafe_allow_html=True)

    iframe_html = f"""
    <div style="border: 1px solid #374151; border-radius: 8px; overflow: hidden; background: #1F2937;">
        <iframe 
            src="https://docs.google.com/gview?url={url}&embedded=true" 
            style="width: 100%; height: 500px; border: none;"
            loading="lazy"
        ></iframe>
    </div>
    """
    st.markdown(iframe_html, unsafe_allow_html=True)

    with st.expander("💡 ¿No se ve el documento?", expanded=False):
        st.markdown("""
        Si el visor no carga, puedes:
        1. **Abrir en pestaña nueva** con el link de arriba
        2. **Descargar** directamente desde la URL
        """)
        st.code(url, language=None)


# ==============================================================================
# HOJA DE VIDA DE ACTIVO (original)
# ==============================================================================
def generar_hoja_vida_pdf(activo, lista_ordenes, df_users):
    """Genera un reporte historico completo del activo antes de borrarlo"""
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_fill_color(245, 158, 11)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, pdf._safe(f"HOJA DE VIDA: {activo['nombre']}"), 0, 1, 'C', fill=True)
    pdf.ln(5)

    pdf.set_text_color(0, 0, 0)
    pdf.label_value('Ubicacion:', f"{activo['area']} - {activo['ubicacion']}")
    pdf.label_value('Categoria:', activo['categoria'])
    pdf.ln(5)

    pdf.set_fill_color(220, 220, 220)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, pdf._safe(f"HISTORIAL ({len(lista_ordenes)} Registros)"), 0, 1, 'L', fill=True)
    pdf.ln(2)

    user_map = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}

    for orden in lista_ordenes:
        fecha = orden['fecha_creacion'][:10]
        tecnico = user_map.get(str(orden['tecnico_asignado']), "N/A")

        pdf.set_font('Arial', 'B', 9)
        pdf.cell(30, 5, pdf._safe(fecha), 0, 0)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(30, 5, pdf._safe(f"OT #{orden['id']}"), 0, 0)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', 'I', 8)
        pdf.cell(0, 5, pdf._safe(f"Tec: {tecnico}"), 0, 1, 'R')

        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(0, 5, pdf._safe(f"Falla: {orden['descripcion']}"))
        if orden.get('comentarios_cierre'):
            pdf.set_font('Arial', 'I', 8)
            pdf.multi_cell(0, 5, pdf._safe(f"Solucion: {orden['comentarios_cierre']}"))

        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)

    return pdf.output(dest='S').encode('latin-1')
