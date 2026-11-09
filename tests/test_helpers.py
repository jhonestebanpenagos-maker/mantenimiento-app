"""
Tests — utils/helpers.py (lógica pura: validaciones, passwords, tipos).
"""
import hashlib

import numpy as np
import pandas as pd

from utils.helpers import (
    validar_politica_password,
    hashear_password,
    verificar_password,
    _es_sha256,
    convertir_tipos_python,
)


# ── Política de contraseñas ──────────────────────────────────────────────────
class TestPoliticaPassword:
    def test_password_valida(self):
        ok, msg = validar_politica_password("Clave123")
        assert ok is True
        assert msg == ""

    def test_password_valida_exactamente_8_chars(self):
        ok, _ = validar_politica_password("Clave12a")
        assert ok is True

    def test_rechaza_corta(self):
        ok, msg = validar_politica_password("Cort7")
        assert ok is False
        assert "al menos 8" in msg

    def test_rechaza_sin_mayuscula(self):
        ok, msg = validar_politica_password("minusc123")
        assert ok is False
        assert "mayúscula" in msg

    def test_rechaza_sin_minuscula(self):
        ok, msg = validar_politica_password("MAYUSC123")
        assert ok is False
        assert "minúscula" in msg

    def test_rechaza_sin_numero(self):
        ok, msg = validar_politica_password("SinNumeros")
        assert ok is False
        assert "número" in msg

    def test_vacia_es_invalida(self):
        ok, _ = validar_politica_password("")
        assert ok is False


# ── Hashing de contraseñas ───────────────────────────────────────────────────
class TestHashPasswords:
    def test_hash_no_expone_password(self):
        h = hashear_password("Clave123")
        assert "Clave123" not in h
        assert h.startswith("$2")

    def test_roundtrip_bcrypt(self):
        h = hashear_password("Clave123")
        assert verificar_password("Clave123", h) is True
        assert verificar_password("clave123", h) is False

    def test_verificacion_sha256_legado(self):
        # Compatibilidad con hashes antiguos SHA-256 (64 hex)
        h_sha = hashlib.sha256("Clave123".encode()).hexdigest()
        assert verificar_password("Clave123", h_sha) is True
        assert verificar_password("otra", h_sha) is False

    def test_dos_hashes_son_diferentes(self):
        # bcrypt usa salt aleatorio: mismo password → hashes distintos
        assert hashear_password("Clave123") != hashear_password("Clave123")


class TestDeteccionSha256:
    def test_sha256_lowercase(self):
        assert _es_sha256(hashlib.sha256(b"x").hexdigest()) is True

    def test_sha256_mayusculas(self):
        assert _es_sha256(hashlib.sha256(b"x").hexdigest().upper()) is True

    def test_longitud_incorrecta(self):
        assert _es_sha256("abc123") is False

    def test_caracter_no_hex(self):
        assert _es_sha256("g" * 64) is False

    def test_vacio_o_none(self):
        assert _es_sha256("") is False
        assert _es_sha256(None) is False

    def test_hash_bcrypt_no_es_sha256(self):
        assert _es_sha256(hashear_password("Clave123")) is False


# ── Conversión de tipos para Supabase/JSON ───────────────────────────────────
class TestConvertirTipos:
    def test_numpy_integer_a_int(self):
        r = convertir_tipos_python({"id": np.int64(5)})
        assert r["id"] == 5
        assert isinstance(r["id"], int)

    def test_numpy_float_a_float(self):
        r = convertir_tipos_python({"monto": np.float64(1.5)})
        assert r["monto"] == 1.5
        assert isinstance(r["monto"], float)

    def test_timestamp_a_isoformat(self):
        ts = pd.Timestamp("2026-01-02 03:04:05")
        r = convertir_tipos_python({"fecha": ts})
        assert r["fecha"] == "2026-01-02T03:04:05"

    def test_numpy_bool_a_bool(self):
        r = convertir_tipos_python({"activo": np.bool_(True)})
        assert r["activo"] is True

    def test_series_a_lista(self):
        r = convertir_tipos_python({"vals": pd.Series([1, 2, 3])})
        assert r["vals"] == [1, 2, 3]

    def test_ndarray_a_lista(self):
        r = convertir_tipos_python({"vals": np.array([4, 5])})
        assert r["vals"] == [4, 5]

    def test_none_se_conserva(self):
        r = convertir_tipos_python({"foto": None})
        assert r["foto"] is None

    def test_tipos_normales_pasan_igual(self):
        r = convertir_tipos_python({"nombre": "Bomba", "n": 7, "ok": True})
        assert r == {"nombre": "Bomba", "n": 7, "ok": True}
