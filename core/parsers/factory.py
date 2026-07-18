import re


class BaseParser:
    def parsear(self, raw_text):
        raise NotImplementedError("Cada parser debe implementar su propio método de extracción")


def _monto_a_int(monto_str):
    """Convierte '7.490' o '850.000' (formato CL) a entero."""
    if not monto_str:
        return None
    return int(monto_str.replace('.', '').replace(',', ''))


class BancoEstadoParserV1(BaseParser):
    """Compra, transferencia e ingreso — BancoEstado corpus v1."""

    def parsear(self, raw_text):
        text = raw_text or ''
        text_lower = text.lower()

        if self._es_ingreso(text_lower):
            return self._parse_ingreso(text)
        if self._es_transferencia(text_lower):
            return self._parse_transferencia(text)
        return self._parse_compra(text)

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

    def _parse_compra(self, text):
        monto_match = re.search(
            r"(?:compra por un monto de|monto de)\s*\$([0-9\.]+)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            monto_match = re.search(r"\$([0-9\.]+)", text)

        comercio_match = re.search(
            r"en\s+([A-Z0-9ÁÉÍÓÚÑ][A-Z0-9ÁÉÍÓÚÑ\s\-\.]*?)"
            r"(?:\s+con\s+tu|\s+el\s+\d{1,2}/\d{1,2}|\s*$)",
            text,
            re.IGNORECASE,
        )
        tarjeta_match = re.search(r"tarjeta\s*\*([0-9]{4})", text, re.IGNORECASE)

        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': comercio_match.group(1).strip() if comercio_match else "COMERCIO DESCONOCIDO",
            'identificador_tarjeta': tarjeta_match.group(1) if tarjeta_match else None,
            'tipo': 'EGRESO',
        }

    def _parse_transferencia(self, text):
        monto_match = re.search(
            r"transferiste\s+(?:por\s+)?\$([0-9\.]+)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            monto_match = re.search(
                r"transferencia\s+por\s+\$([0-9\.]+)",
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
            'comercio_raw': (
                destinatario_match.group(1).strip()
                if destinatario_match
                else "TRANSFERENCIA ENVIADA"
            ),
            'identificador_tarjeta': None,
            'tipo': 'TRANSFERENCIA',
        }

    def _parse_ingreso(self, text):
        monto_match = re.search(
            r"(?:abono|transferencia)\s+por\s+\$([0-9\.]+)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            monto_match = re.search(r"\$([0-9\.]+)", text)

        origen_match = re.search(
            r"(?:de|desde)\s+([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9\s\.\-]+?)"
            r"(?:\s+el\s+\d{1,2}/\d{1,2}|\s+en\s+tu|\s*$)",
            text,
            re.IGNORECASE,
        )

        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': origen_match.group(1).strip() if origen_match else "ABONO RECIBIDO",
            'identificador_tarjeta': None,
            'tipo': 'INGRESO',
        }


class SantanderParserV1(BaseParser):
    """Compra y transferencia — Santander corpus v1."""

    def parsear(self, raw_text):
        text = raw_text or ''
        text_lower = text.lower()

        if 'transferencia' in text_lower or 'transferiste' in text_lower:
            return self._parse_transferencia(text)
        return self._parse_compra(text)

    def _parse_compra(self, text):
        monto_match = re.search(
            r"(?:Notifica Compra por|compra por)\s*\$([0-9\.]+)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            monto_match = re.search(r"\$([0-9\.]+)", text)

        comercio_match = re.search(r"Lugar:\s*([^\n\r]+)", text, re.IGNORECASE)
        if not comercio_match:
            comercio_match = re.search(
                r"en\s+([A-Z0-9ÁÉÍÓÚÑ][A-Z0-9ÁÉÍÓÚÑ\s\-\.]+)",
                text,
                re.IGNORECASE,
            )

        tarjeta_match = re.search(
            r"(?:\*{1,}|terminada en\s+)(\d{4})",
            text,
            re.IGNORECASE,
        )

        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': (
                comercio_match.group(1).strip()
                if comercio_match
                else "SANTANDER_ESTABLECIMIENTO"
            ),
            'identificador_tarjeta': tarjeta_match.group(1) if tarjeta_match else None,
            'tipo': 'EGRESO',
        }

    def _parse_transferencia(self, text):
        monto_match = re.search(
            r"transferencia\s+por\s+\$([0-9\.]+)",
            text,
            re.IGNORECASE,
        )
        destinatario = re.search(
            r"a\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]+?)"
            r"(?:\s+el\s+\d{1,2}/\d{1,2}|\s*$)",
            text,
            re.IGNORECASE,
        )
        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': destinatario.group(1).strip() if destinatario else "TRANSFERENCIA SANTANDER",
            'identificador_tarjeta': None,
            'tipo': 'TRANSFERENCIA',
        }


class BciParserV1(BaseParser):
    """Compra y abono — BCI corpus v1."""

    def parsear(self, raw_text):
        text = raw_text or ''
        text_lower = text.lower()

        if any(k in text_lower for k in ('recibiste una transferencia', 'abono', 'te depositaron')):
            return self._parse_ingreso(text)
        return self._parse_compra(text)

    def _parse_compra(self, text):
        monto_match = re.search(
            r"(?:compra por|compra de)\s*\$([0-9\.]+)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            monto_match = re.search(r"\$([0-9\.]+)", text)

        comercio_match = re.search(
            r"en\s+([A-Z0-9ÁÉÍÓÚÑ][A-Z0-9ÁÉÍÓÚÑ\s\-\.]*?)"
            r"(?:\s+con\s+(?:tu\s+)?tarjeta|\s+el\s+\d|\s*$)",
            text,
            re.IGNORECASE,
        )
        tarjeta_match = re.search(
            r"(?:\*|terminada en\s+)(\d{4})",
            text,
            re.IGNORECASE,
        )

        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': comercio_match.group(1).strip() if comercio_match else "COMERCIO BCI",
            'identificador_tarjeta': tarjeta_match.group(1) if tarjeta_match else None,
            'tipo': 'EGRESO',
        }

    def _parse_ingreso(self, text):
        monto_match = re.search(
            r"(?:transferencia|abono)\s+por\s+\$([0-9\.]+)",
            text,
            re.IGNORECASE,
        )
        origen = re.search(
            r"de\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]+?)"
            r"(?:\s+el\s+\d{1,2}/\d{1,2}|\s*$)",
            text,
            re.IGNORECASE,
        )
        return {
            'monto': _monto_a_int(monto_match.group(1)) if monto_match else None,
            'comercio_raw': origen.group(1).strip() if origen else "ABONO BCI",
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
