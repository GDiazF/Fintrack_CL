import html as html_lib
import re


class BaseParser:
    def parsear(self, raw_text):
        raise NotImplementedError("Cada parser debe implementar su propio método de extracción")


def _monto_a_int(monto_str):
    """Convierte '7.490', '850.000' o ' 3.200 ' (formato CL) a entero."""
    if not monto_str:
        return None
    limpio = monto_str.replace('.', '').replace(',', '').replace(' ', '').strip()
    if not limpio:
        return None
    return int(limpio)


def _texto_para_parse(raw):
    """Quita HTML/ruido típico de mails bancarios antes de aplicar regex."""
    t = raw or ''
    t = re.sub(r'(?is)<(script|style).*?>.*?</\1>', ' ', t)
    t = re.sub(r'(?i)<br\s*/?>', '\n', t)
    t = re.sub(r'(?i)</p\s*>', '\n', t)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = html_lib.unescape(t)
    t = t.replace('\xa0', ' ')
    t = re.sub(r'[ \t]+', ' ', t)
    return t


_JUNK_COMERCIO = re.compile(
    r'^(la\s+secci[oó]n|este\s+correo|inf[oó]rmese|antes\s+de|estimado|'
    r'participa|mundial|para\s+al|www\.|https?://|notifica)',
    re.IGNORECASE,
)


def _limpiar_comercio(nombre, fallback='COMERCIO DESCONOCIDO'):
    if not nombre:
        return fallback
    n = re.sub(r'[\*_]+', '', nombre)
    n = re.sub(r'\s+', ' ', n).strip(' .,;:-\t|"\'')
    if len(n) > 60:
        n = n[:60]
        if ' ' in n:
            n = n.rsplit(' ', 1)[0]
    if len(n) < 2 or _JUNK_COMERCIO.search(n):
        return fallback
    low = n.lower()
    if any(w in low for w in (
        'puedes acompañ', 'participa por', 'correo electrónico',
        'garantía estatal', 'cmfchile',
    )):
        return fallback
    return n


def _extraer_comercio_compra(text):
    """
    Extrae el comercio de una notificación de compra.
    Prioriza etiquetas (Lugar/Comercio); evita pies de marketing
    (el patrón 'en …' con IGNORECASE capturaba 'en la sección…').
    """
    for label in (
        r'Lugar',
        r'Comercio',
        r'Establecimiento',
        r'Nombre\s+del\s+comercio',
        r'Comercio\s+o\s+establecimiento',
    ):
        m = re.search(rf'{label}\s*[:\-]\s*([^\n\r\|]+)', text, re.IGNORECASE)
        if m:
            limpio = _limpiar_comercio(m.group(1))
            if limpio != 'COMERCIO DESCONOCIDO':
                return limpio

    # Ventana cerca del primer monto (el pie del mail suele estar lejos)
    ventana = text
    m_monto = re.search(r'\$\s*[0-9]', text)
    if m_monto:
        start = max(0, m_monto.start() - 100)
        ventana = text[start:m_monto.start() + 320]

    # Case-sensitive: los bancos suelen poner el comercio en MAYÚSCULAS
    patterns = [
        r'\ben\s+([A-Z0-9ÁÉÍÓÚÑ][A-Z0-9ÁÉÍÓÚÑ0-9\s\.\-&/\']{1,55}?)'
        r'(?:\s+con\s+(?:tu\s+)?tarjeta|\s+el\s+\d{1,2}/\d{1,2}|\s*\*|$)',
        r'compra(?:ste)?\s+en\s+([A-Z0-9ÁÉÍÓÚÑ][A-Z0-9ÁÉÍÓÚÑ0-9\s\.\-&/\']{1,55}?)'
        r'(?:\s+con\s+|\s+el\s+\d|\s*\*|$)',
    ]
    for fuente in (ventana, text):
        for pat in patterns:
            m = re.search(pat, fuente)
            if m:
                limpio = _limpiar_comercio(m.group(1))
                if limpio != 'COMERCIO DESCONOCIDO':
                    return limpio

    return 'COMERCIO DESCONOCIDO'


def _extraer_tarjeta(text):
    m = re.search(r"(?:tarjeta\s*)?\*([0-9]{4})", text, re.IGNORECASE)
    return m.group(1) if m else None


def _extraer_monto(text, *prefijos):
    for pref in prefijos:
        m = re.search(pref + r"\s*\$\s*([0-9.\s]+)", text, re.IGNORECASE)
        if m:
            return _monto_a_int(m.group(1))
    m = re.search(r"\$\s*([0-9.\s]+)", text)
    return _monto_a_int(m.group(1)) if m else None


class BancoEstadoParserV1(BaseParser):
    """Compra, transferencia, pago servicios e ingreso — BancoEstado corpus v1."""

    def parsear(self, raw_text):
        text = _texto_para_parse(raw_text)
        text_lower = text.lower()

        if self._es_pago_servicios(text_lower):
            return self._parse_pago_servicios(text)
        if self._es_aviso_envio_recepcion(text_lower):
            return self._parse_aviso_envio_recepcion(text)
        if self._es_ingreso(text_lower):
            return self._parse_ingreso(text)
        if self._es_transferencia(text_lower):
            return self._parse_transferencia(text)
        return self._parse_compra(text)

    def _es_pago_servicios(self, text_lower):
        return any(k in text_lower for k in (
            'pago de servicios',
            'comprobante de pago de servicios',
            'pagaste un servicio',
            'pago de servicio',
        ))

    def _es_aviso_envio_recepcion(self, text_lower):
        return any(k in text_lower for k in (
            'envío o recepción de dinero',
            'envio o recepcion de dinero',
            'aviso de envío',
            'aviso de envio',
            'enviaste dinero',
            'recibiste dinero',
        ))

    def _es_ingreso(self, text_lower):
        return any(k in text_lower for k in (
            'recibiste un abono',
            'recibiste una transferencia',
            'abono por',
            'te abonaron',
        ))

    def _es_transferencia(self, text_lower):
        return any(k in text_lower for k in (
            'transferiste',
            'realizaste una transferencia',
            'confirmamos que transferiste',
        ))

    def _parse_pago_servicios(self, text):
        monto = _extraer_monto(
            text,
            r"(?:monto(?:\s+pagado)?|pagaste|pago(?:\s+por)?)\s*(?:de|:)?",
        )
        # Empresa / servicio: "a AGUAS ANDINAS", "empresa: ENTEL", "servicio ENTEL"
        empresa = re.search(
            r"(?:empresa|servicio|convenio|a favor de|pagaste a|pago a)\s*:?\s*"
            r"([A-Z0-9ÁÉÍÓÚÑ][A-Z0-9ÁÉÍÓÚÑ\s\.\-&]{1,60}?)"
            r"(?:\s+por\s+|\$|\s+el\s+\d|\s+RUT|\s*$)",
            text,
            re.IGNORECASE,
        )
        if not empresa:
            empresa = re.search(
                r"a\s+([A-Z0-9ÁÉÍÓÚÑ][A-Z0-9ÁÉÍÓÚÑ\s\.\-]{1,40}?)"
                r"(?:\s+por\s+|\$|\s+el\s+\d|\s*$)",
                text,
                re.IGNORECASE,
            )
        nombre = empresa.group(1).strip() if empresa else 'PAGO DE SERVICIOS'
        return {
            'monto': monto,
            'comercio_raw': _limpiar_comercio(nombre, fallback='PAGO DE SERVICIOS'),
            'identificador_tarjeta': _extraer_tarjeta(text),
            'tipo': 'EGRESO',
        }

    def _parse_aviso_envio_recepcion(self, text):
        text_lower = text.lower()
        es_ingreso = any(k in text_lower for k in (
            'recibiste', 'recepción', 'recepcion', 'te enviaron', 'abono',
        )) and not any(k in text_lower for k in (
            'enviaste', 'envío de', 'envio de', 'transferiste',
        ))
        # Si dice ambos (asunto genérico), inferir por verbos de acción
        if 'enviaste' in text_lower or 'enviaste dinero' in text_lower:
            es_ingreso = False
        if 'recibiste' in text_lower and 'enviaste' not in text_lower:
            es_ingreso = True

        monto = _extraer_monto(
            text,
            r"(?:monto|enviaste|recibiste|transferiste|por)\s*(?:de|:)?",
        )
        contraparte = re.search(
            r"(?:a|de|desde|hacia)\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]{1,50}?)"
            r"(?:\s+el\s+\d|\s+por\s+|\$|\s+RUT|\s+desde|\s+en\s+tu|\s*$)",
            text,
            re.IGNORECASE,
        )
        nombre = contraparte.group(1).strip() if contraparte else (
            'DINERO RECIBIDO' if es_ingreso else 'DINERO ENVIADO'
        )
        return {
            'monto': monto,
            'comercio_raw': _limpiar_comercio(
                nombre,
                fallback='DINERO RECIBIDO' if es_ingreso else 'DINERO ENVIADO',
            ),
            'identificador_tarjeta': _extraer_tarjeta(text),
            'tipo': 'INGRESO' if es_ingreso else 'TRANSFERENCIA',
        }

    def _parse_compra(self, text):
        monto_match = re.search(
            r"(?:compra por un monto de|monto de|Notifica(?:ción)?\s+de\s+compra.*?)\s*\$\s*([0-9.\s]+)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not monto_match:
            monto_match = re.search(
                r"(?:compra por un monto de|monto de)\s*\$\s*([0-9.\s]+)",
                text,
                re.IGNORECASE,
            )
        if not monto_match:
            monto_match = re.search(r"\$\s*([0-9.\s]+)", text)

        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': _extraer_comercio_compra(text),
            'identificador_tarjeta': _extraer_tarjeta(text),
            'tipo': 'EGRESO',
        }

    def _parse_transferencia(self, text):
        monto_match = re.search(
            r"transferiste\s+(?:por\s+)?\$\s*([0-9.\s]+)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            monto_match = re.search(
                r"transferencia\s+por\s+\$\s*([0-9.\s]+)",
                text,
                re.IGNORECASE,
            )

        destinatario_match = re.search(
            r"(?:a|hacia)\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]+?)"
            r"(?:\s+el\s+\d{1,2}/\d{1,2}|\s+desde|\s*$)",
            text,
            re.IGNORECASE,
        )

        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': _limpiar_comercio(
                destinatario_match.group(1),
                fallback='TRANSFERENCIA ENVIADA',
            ) if destinatario_match else 'TRANSFERENCIA ENVIADA',
            'identificador_tarjeta': _extraer_tarjeta(text),
            'tipo': 'TRANSFERENCIA',
        }

    def _parse_ingreso(self, text):
        monto_match = re.search(
            r"(?:abono|transferencia)\s+por\s+\$\s*([0-9.\s]+)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            monto_match = re.search(r"\$\s*([0-9.\s]+)", text)

        origen_match = re.search(
            r"(?:de|desde)\s+([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9\s\.\-]+?)"
            r"(?:\s+el\s+\d{1,2}/\d{1,2}|\s+en\s+tu|\s*$)",
            text,
            re.IGNORECASE,
        )

        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': _limpiar_comercio(
                origen_match.group(1),
                fallback='ABONO RECIBIDO',
            ) if origen_match else 'ABONO RECIBIDO',
            'identificador_tarjeta': _extraer_tarjeta(text),
            'tipo': 'INGRESO',
        }


class SantanderParserV1(BaseParser):
    """Compra y transferencia — Santander corpus v1."""

    def parsear(self, raw_text):
        text = _texto_para_parse(raw_text)
        text_lower = text.lower()

        if 'transferencia' in text_lower or 'transferiste' in text_lower:
            return self._parse_transferencia(text)
        return self._parse_compra(text)

    def _parse_compra(self, text):
        monto_match = re.search(
            r"(?:Notifica Compra por|compra por)\s*\$\s*([0-9.\s]+)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            monto_match = re.search(r"\$\s*([0-9.\s]+)", text)

        comercio = _extraer_comercio_compra(text)
        if comercio == 'COMERCIO DESCONOCIDO':
            comercio = 'SANTANDER_ESTABLECIMIENTO'

        tarjeta_match = re.search(
            r"(?:\*{1,}|terminada en\s+)(\d{4})",
            text,
            re.IGNORECASE,
        )

        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': comercio,
            'identificador_tarjeta': tarjeta_match.group(1) if tarjeta_match else None,
            'tipo': 'EGRESO',
        }

    def _parse_transferencia(self, text):
        monto_match = re.search(
            r"Monto\s+transferido[\s\S]{0,80}?\$\s*([0-9.\s]+)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            monto_match = re.search(
                r"transferencia\s+por\s+\$\s*([0-9.\s]+)",
                text,
                re.IGNORECASE,
            )
        if not monto_match:
            monto_match = re.search(r"\$\s*([0-9.\s]+)", text)

        destinatario = re.search(
            r"Datos\s+de\s+destino[\s\S]*?Nombre\s+"
            r"([A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ\s\.]{0,60}?)"
            r"(?:\s+RUT|\s+Banco|\s*$)",
            text,
            re.IGNORECASE,
        )
        if not destinatario:
            destinatario = re.search(
                r"a\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]+?)"
                r"(?:\s+el\s+\d{1,2}/\d{1,2}|\s*$)",
                text,
            )

        nombre = destinatario.group(1).strip() if destinatario else 'TRANSFERENCIA SANTANDER'
        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': _limpiar_comercio(nombre, fallback='TRANSFERENCIA SANTANDER'),
            'identificador_tarjeta': None,
            'tipo': 'TRANSFERENCIA',
        }


class BciParserV1(BaseParser):
    """Compra y abono — BCI corpus v1."""

    def parsear(self, raw_text):
        text = _texto_para_parse(raw_text)
        text_lower = text.lower()

        if any(k in text_lower for k in ('recibiste una transferencia', 'abono', 'te depositaron')):
            return self._parse_ingreso(text)
        return self._parse_compra(text)

    def _parse_compra(self, text):
        monto_match = re.search(
            r"(?:compra por|compra de)\s*\$\s*([0-9.\s]+)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            monto_match = re.search(r"\$\s*([0-9.\s]+)", text)

        tarjeta_match = re.search(
            r"(?:\*|terminada en\s+)(\d{4})",
            text,
            re.IGNORECASE,
        )

        comercio = _extraer_comercio_compra(text)
        if comercio == 'COMERCIO DESCONOCIDO':
            comercio = 'COMERCIO BCI'

        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': comercio,
            'identificador_tarjeta': tarjeta_match.group(1) if tarjeta_match else None,
            'tipo': 'EGRESO',
        }

    def _parse_ingreso(self, text):
        monto_match = re.search(
            r"(?:transferencia|abono)\s+por\s+\$\s*([0-9.\s]+)",
            text,
            re.IGNORECASE,
        )
        origen = re.search(
            r"de\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]+?)"
            r"(?:\s+el\s+\d{1,2}/\d{1,2}|\s*$)",
            text,
        )
        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': _limpiar_comercio(
                origen.group(1), fallback='ABONO BCI'
            ) if origen else 'ABONO BCI',
            'identificador_tarjeta': None,
            'tipo': 'INGRESO',
        }


class ParserFactory:
    _STRATEGIES = {
        'gmail_bancoestado_v1': BancoEstadoParserV1(),
        'gmail_santander_v1': SantanderParserV1(),
        'gmail_bci_v1': BciParserV1(),
    }

    @classmethod
    def get(cls, conector_id):
        return cls._STRATEGIES.get(conector_id, None)
