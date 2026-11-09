"""
Tests — utils/email_parser.py (parseo .eml y limpieza de contenido).
"""
from email.message import EmailMessage

from utils.email_parser import (
    parse_email_file,
    _limpiar_cuerpo,
    _html_a_texto,
    construir_descripcion_email,
    _detectar_mime,
)


class FakeUpload:
    """Imita un archivo subido a Streamlit (.name + .getvalue())."""

    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def _eml_simple() -> bytes:
    m = EmailMessage()
    m['From'] = 'ana@empresa.com'
    m['To'] = 'soporte@empresa.com'
    m['Subject'] = 'Falla en Linea 3'
    m['Date'] = 'Tue, 04 Nov 2025 10:00:00 -0500'
    m.set_content('Equipo detenido\n-- \nAna G.\nGerente de Planta')
    return m.as_bytes()


def _eml_con_adjunto() -> bytes:
    m = EmailMessage()
    m['From'] = 'carlos@empresa.com'
    m['To'] = 'soporte@empresa.com'
    m['Subject'] = 'Informe semanal'
    m['Date'] = 'Wed, 05 Nov 2025 09:00:00 -0500'
    m.set_content('Adjunto el informe.')
    m.add_attachment(b'%PDF-FAKE%', maintype='application', subtype='pdf',
                     filename='informe.pdf')
    return m.as_bytes()


# ── Limpieza de cuerpo ───────────────────────────────────────────────────────
class TestLimpiarCuerpo:
    def test_vacio_y_none(self):
        assert _limpiar_cuerpo("") == ""
        assert _limpiar_cuerpo(None) == ""

    def test_quita_firma(self):
        texto = "Equipo detenido\n-- \nAna G.\nGerente"
        resultado = _limpiar_cuerpo(texto)
        assert "Equipo detenido" in resultado
        assert "Ana G." not in resultado

    def test_quita_firma_formato_alternativo(self):
        resultado = _limpiar_cuerpo("Mensaje\n--\nFirma")
        assert resultado == "Mensaje"

    def test_trunca_contenido_largo(self):
        texto = "a" * 2500
        resultado = _limpiar_cuerpo(texto)
        assert len(resultado) < 2500
        assert resultado.endswith("... [contenido truncado]")
        assert resultado.startswith("a" * 2000)

    def test_texto_normal_intacto(self):
        assert _limpiar_cuerpo("Hola mundo") == "Hola mundo"


# ── HTML → texto ─────────────────────────────────────────────────────────────
class TestHtmlATexto:
    def test_quita_style_y_script(self):
        html = "<style>p{color:red}</style><script>alert(1)</script>Hola"
        resultado = _html_a_texto(html)
        assert "color" not in resultado
        assert "alert" not in resultado
        assert "Hola" in resultado

    def test_convierte_br_y_p_en_saltos(self):
        resultado = _html_a_texto("uno<br>dos<p>tres</p>")
        assert "uno\ndos" in resultado
        assert "tres" in resultado

    def test_decodifica_entidades(self):
        resultado = _html_a_texto("A &amp; B &lt;b&gt; &quot;c&quot;")
        assert "A & B" in resultado
        assert "<b>" in resultado
        assert '"c"' in resultado

    def test_quita_tags(self):
        resultado = _html_a_texto('<span class="x">Texto plano</span>')
        assert "Texto plano" in resultado
        assert "span" not in resultado


# ── parse_email_file (.eml) ──────────────────────────────────────────────────
class TestParseEmailFile:
    def test_none_retorna_none(self):
        assert parse_email_file(None) is None

    def test_extension_desconocida_retorna_none(self):
        assert parse_email_file(FakeUpload("nota.txt", b"hola")) is None

    def test_eml_simple(self):
        datos = parse_email_file(FakeUpload("correo.eml", _eml_simple()))
        assert datos is not None
        assert str(datos['remitente']) == 'ana@empresa.com'
        assert str(datos['asunto']) == 'Falla en Linea 3'
        assert datos['fecha']
        assert "Equipo detenido" in datos['cuerpo']
        assert "Gerente" not in datos['cuerpo']       # firma eliminada
        assert datos['formato'] == 'eml'

    def test_eml_con_adjunto(self):
        datos = parse_email_file(FakeUpload("correo.eml", _eml_con_adjunto()))
        assert datos is not None
        assert len(datos['adjuntos']) == 1
        adj = datos['adjuntos'][0]
        assert adj['nombre'] == 'informe.pdf'
        assert adj['datos'] == b'%PDF-FAKE%'
        assert "Adjunto el informe." in datos['cuerpo']

    def test_eml_corrupto_no_revienta(self):
        datos = parse_email_file(FakeUpload("roto.eml", b"\x00\x01\x02 no es un correo"))
        # O parsea vacío o retorna None, pero nunca lanza excepción
        assert datos is None or isinstance(datos, dict)


# ── Utilidades ───────────────────────────────────────────────────────────────
class TestDescripcionYMime:
    def test_descripcion_incluye_datos_y_adjuntos(self):
        datos = {
            "remitente": "ana@empresa.com",
            "asunto": "Falla",
            "fecha": "2025-11-04",
            "cuerpo": "Equipo detenido",
            "adjuntos": [{"nombre": "foto.jpg", "datos": b"x", "tipo": "image/jpeg"}],
        }
        desc = construir_descripcion_email(datos)
        assert "De: ana@empresa.com" in desc
        assert "Asunto: Falla" in desc
        assert "Equipo detenido" in desc
        assert "foto.jpg" in desc

    def test_detectar_mime(self):
        assert _detectar_mime("a.JPG") == "image/jpeg"
        assert _detectar_mime("b.png") == "image/png"
        assert _detectar_mime("c.pdf") == "application/pdf"
        assert _detectar_mime("d.msg") == "application/vnd.ms-outlook"
        assert _detectar_mime("e.zip") == "application/octet-stream"
