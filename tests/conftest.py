"""
Configuración global de tests — ORIÓN.

Objetivo: probar la LÓGICA PURA sin Streamlit ni Supabase reales.
- 'streamlit' se reemplaza por un stub liviano (los tests no prueban UI).
- 'utils.db' se reemplaza para no requerir credenciales de base de datos.
"""
import sys
import types

# ── Stub de streamlit ─────────────────────────────────────────────────────────
if 'streamlit' not in sys.modules:
    st_stub = types.ModuleType('streamlit')

    def _decorator(*args, **kwargs):
        """Soporta @st.cache_data, @st.cache_data(...) y afines sin alterar la función."""
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        def wrap(func):
            return func
        return wrap

    class _SessionState(dict):
        def __getattr__(self, key):
            try:
                return self[key]
            except KeyError:
                raise AttributeError(key)

        def __setattr__(self, key, value):
            self[key] = value

    st_stub.cache_data = _decorator
    st_stub.cache_resource = _decorator
    st_stub.session_state = _SessionState()
    for _name in ("error", "warning", "success", "info", "caption", "write",
                  "markdown", "text", "toast", "rerun", "stop", "title",
                  "subheader", "button", "download_button", "expander",
                  "columns", "container", "dataframe", "table", "image",
                  "file_uploader", "selectbox", "text_input", "spinner"):
        setattr(st_stub, _name, lambda *a, **k: None)
    sys.modules['streamlit'] = st_stub

# ── Stub de utils.db (sin Supabase real) ──────────────────────────────────────
if 'utils.db' not in sys.modules:
    db_stub = types.ModuleType('utils.db')
    db_stub.supabase = None
    db_stub.invalidate_cache = lambda *a, **k: None
    sys.modules['utils.db'] = db_stub
