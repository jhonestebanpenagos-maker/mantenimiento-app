from fpdf import FPDF
import requests
import tempfile
import os
import pandas as pd
from datetime import datetime

# --- 🖨️ GENERADOR DE REPORTES PDF ---
class PDFReport(FPDF):
    def header(self):
        # Título
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'REPORTE DE SERVICIO TÉCNICO', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, 'Sistema de Mantenimiento Orión', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
        
# --- FUNCIÓN NUEVA: GENERAR HOJA DE VIDA (HISTORIAL) ---
def generar_hoja_vida_pdf(activo, lista_ordenes, df_users):
    """Genera un reporte histórico completo del activo antes de borrarlo"""
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # 1. ENCABEZADO
    pdf.set_fill_color(245, 158, 11) # Naranja
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"HOJA DE VIDA: {activo['nombre']}".encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'C', fill=True)
    pdf.ln(5)
    
    # 2. DATOS DEL EQUIPO
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', 'B', 10); pdf.cell(40, 6, "Ubicacion:", 0, 0)
    pdf.set_font('Arial', '', 10); pdf.cell(0, 6, f"{activo['area']} - {activo['ubicacion']}".encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    pdf.set_font('Arial', 'B', 10); pdf.cell(40, 6, "Categoria:", 0, 0)
    pdf.set_font('Arial', '', 10); pdf.cell(0, 6, f"{activo['categoria']}".encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    pdf.ln(5)
    
    # 3. LISTADO DE MANTENIMIENTOS
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f"HISTORIAL ({len(lista_ordenes)} Registros)", 0, 1, 'L', fill=True)
    pdf.ln(2)
    
    # Mapa de usuarios para saber nombres
    user_map = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}

    for orden in lista_ordenes:
        # Fecha y Estado
        fecha = orden['fecha_creacion'][:10]
        tecnico = user_map.get(str(orden['tecnico_asignado']), "N/A")
        
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(30, 5, f"{fecha}", 0, 0)
        pdf.set_text_color(0, 128, 0) # Verde
        pdf.cell(30, 5, f"OT #{orden['id']}", 0, 0)
        pdf.set_text_color(0,0,0)
        pdf.set_font('Arial', 'I', 8)
        pdf.cell(0, 5, f"Tec: {tecnico}".encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'R')
        
        # Falla y Solución
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(0, 5, f"Falla: {orden['descripcion']}".encode('latin-1', 'replace').decode('latin-1'))
        if orden.get('comentarios_cierre'):
            pdf.set_font('Arial', 'I', 8)
            pdf.multi_cell(0, 5, f"Solucion: {orden['comentarios_cierre']}".encode('latin-1', 'replace').decode('latin-1'))
        
        pdf.line(10, pdf.get_y(), 200, pdf.get_y()) # Línea separadora
        pdf.ln(2)

    return pdf.output(dest='S').encode('latin-1')

# --- FUNCIÓN ORIGINAL (YA EXISTENTE) ---
def generar_pdf_orden(orden, activo_nombre, tecnico_nombre):
    """Genera un PDF con los detalles de la orden y las fotos"""
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- 1. INFORMACIÓN GENERAL ---
    pdf.set_fill_color(240, 240, 240) # Gris claro
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"Orden de Trabajo #{orden['id']}", 0, 1, 'L', fill=True)
    pdf.ln(2)
    
    pdf.set_font('Arial', '', 10)
    # Fila 1
    pdf.cell(50, 8, "Fecha Creación:", 0, 0, 'B')
    pdf.cell(50, 8, f"{orden['fecha_creacion'][:10]}", 0, 0)
    pdf.cell(40, 8, "Estado Final:", 0, 0, 'B')
    pdf.set_text_color(0, 128, 0) # Verde
    pdf.cell(50, 8, f"{orden['estado']}", 0, 1)
    pdf.set_text_color(0, 0, 0) # Negro
    
    # Fila 2
    pdf.cell(50, 8, "Activo:", 0, 0, 'B')
    pdf.cell(50, 8, f"{activo_nombre}".encode('latin-1', 'replace').decode('latin-1'), 0, 0)
    pdf.cell(40, 8, "Técnico:", 0, 0, 'B')
    pdf.cell(50, 8, f"{tecnico_nombre}".encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    
    # Fila 3
    pdf.cell(50, 8, "Tipo:", 0, 0, 'B')
    pdf.cell(50, 8, f"{orden.get('tipo_mantenimiento', 'N/A')}", 0, 0)
    pdf.cell(40, 8, "Criticidad:", 0, 0, 'B')
    pdf.cell(50, 8, f"{orden['criticidad']}", 0, 1)
    pdf.ln(5)

    # --- 2. DETALLE DEL PROBLEMA ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "1. Reporte de Falla / Solicitud", 0, 1, 'L', fill=True)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 6, f"{orden['descripcion']}".encode('latin-1', 'replace').decode('latin-1'))
    pdf.ln(5)

    # --- 3. SOLUCIÓN TÉCNICA ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "2. Informe de Reparación", 0, 1, 'L', fill=True)
    pdf.set_font('Arial', '', 10)
    reporte = orden.get('comentarios_cierre') or "Sin reporte registrado."
    pdf.multi_cell(0, 6, f"{reporte}".encode('latin-1', 'replace').decode('latin-1'))
    pdf.ln(5)

    # --- 4. EVIDENCIA FOTOGRÁFICA ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "3. Evidencia Fotográfica", 0, 1, 'L', fill=True)
    pdf.ln(2)

    y_pos = pdf.get_y()
    
    # Función interna para descargar y poner imagen
    def poner_imagen_desde_url(url, x, y, w, titulo):
        try:
            if url:
                response = requests.get(url)
                if response.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(response.content)
                        tmp_path = tmp.name
                    pdf.image(tmp_path, x=x, y=y, w=w)
                    pdf.set_xy(x, y + 45) # Bajamos para el título
                    pdf.set_font('Arial', 'I', 8)
                    pdf.cell(w, 5, titulo, 0, 0, 'C')
                    os.remove(tmp_path) # Limpiar
        except Exception as e:
            print(f"Error img pdf: {e}")

    # Foto de cierre
    if orden.get('foto_cierre_url'):
        poner_imagen_desde_url(orden['foto_cierre_url'], 10, y_pos, 60, "Trabajo Terminado (Evidencia)")
    else:
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 10, "Sin evidencia fotográfica de cierre.", 0, 1)

    # Retornar bytes
    return pdf.output(dest='S').encode('latin-1')
