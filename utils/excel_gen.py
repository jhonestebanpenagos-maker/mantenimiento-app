import io
import pandas as pd
from datetime import datetime


def generar_excel_historial(df_ordenes, df_act, df_users):
    buffer = io.BytesIO()
    df_export = df_ordenes.copy()

    map_act = dict(zip(df_act['id'], df_act['nombre'])) if not df_act.empty else {}
    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}

    df_export['Activo'] = df_export['activo_id'].map(map_act).fillna('Desconocido')
    df_export['Tecnico'] = df_export['tecnico_asignado'].map(map_user).fillna('Sin asignar')
    df_export['fecha_creacion'] = pd.to_datetime(df_export['fecha_creacion'])
    df_export['fecha_cierre'] = pd.to_datetime(df_export['fecha_cierre'])
    df_export['Duracion_Horas'] = ((df_export['fecha_cierre'] - df_export['fecha_creacion'])
                                    .dt.total_seconds() / 3600).round(1)

    cols = ['id', 'fecha_creacion', 'fecha_cierre', 'Duracion_Horas', 'Activo', 'Tecnico',
            'tipo_mantenimiento', 'criticidad', 'estado', 'descripcion', 'comentarios_cierre']
    nombres_col = {
        'id': 'ID Orden', 'fecha_creacion': 'Fecha Apertura', 'fecha_cierre': 'Fecha Cierre',
        'Duracion_Horas': 'Duración (Horas)', 'Activo': 'Activo', 'Tecnico': 'Técnico',
        'tipo_mantenimiento': 'Tipo', 'criticidad': 'Criticidad', 'estado': 'Estado',
        'descripcion': 'Descripción', 'comentarios_cierre': 'Informe de Cierre'
    }
    df_final = df_export[cols].rename(columns=nombres_col).sort_values('ID Orden', ascending=False)

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Historial OTs')
        worksheet = writer.sheets['Historial OTs']
        for col in worksheet.columns:
            max_len = max(len(str(col[0].value)),
                         *[len(str(cell.value)) if cell.value else 0 for cell in col[1:]])
            worksheet.column_dimensions[col[0].column_letter].width = min(max_len + 3, 50)

    buffer.seek(0)
    return buffer
