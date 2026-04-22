import streamlit as st
import pandas as pd
from supabase import create_client, Client


# ==============================================================================
# 🔌 CONEXIÓN A SUPABASE
# ==============================================================================
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError as e:
        st.error(f"❌ Configuración incompleta: falta la clave {e} en secrets.toml.")
        return None
    except Exception as e:
        st.error("❌ No se pudo conectar a la base de datos. Contacte al administrador.")
        print(f"Error conectando Supabase: {e}")
        return None


supabase = init_supabase()


# ==============================================================================
# 🔍 FUNCIONES DE CONSULTA
# ==============================================================================
def run_query(table_name, filters=None, order_by="id"):
    tablas_maestras = ["usuarios", "activos", "categorias", "ubicaciones", "inventario"]
    if table_name in tablas_maestras:
        return pd.DataFrame(_run_query_internal(table_name, filters, order_by))
    else:
        return pd.DataFrame(_run_query_live_data(table_name, filters, order_by))


@st.cache_data(ttl=600)
def _run_query_internal(table_name, filters, order_by):
    query = supabase.table(table_name).select("*")
    if filters:
        for key, value in filters.items():
            query = query.eq(key, value)
    res = query.order(order_by).execute()
    return res.data if res.data else []


def _run_query_live_data(table_name, filters, order_by):
    try:
        query = supabase.table(table_name).select("*")
        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)
        res = query.order(order_by).execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"Error en consulta {table_name}: {e}")
        st.error(f"⚠️ No se pudieron cargar los datos de {table_name}. Intente nuevamente.")
        return []
