import re

class BaseParser:
    def parsear(self, raw_text):
        raise NotImplementedError("Cada parser debe implementar su propio método de extracción")


class BancoEstadoParserV1(BaseParser):
    def parsear(self, raw_text):
        # Expresiones regulares específicas de BancoEstado v1
        monto_match = re.search(r"monto de \$([0-9\.]+)", raw_text, re.IGNORECASE)
        comercio_match = re.search(r"en ([A-Z0-9\s\-\.]+)", raw_text)
        tarjeta_match = re.search(r"tarjeta\s*\*([0-9]{4})", raw_text, re.IGNORECASE)
        
        return {
            'monto': int(monto_match.group(1).replace('.', '')) if monto_match else None,
            'comercio_raw': comercio_match.group(1).strip() if comercio_match else "COMERCIO DESCONOCIDO",
            'identificador_tarjeta': tarjeta_match.group(1) if tarjeta_match else None,
            'tipo': 'EGRESO'
        }


class SantanderParserV1(BaseParser):
    def parsear(self, raw_text):
        # Lógica de extracción adaptada al formato de correos Santander v1
        monto_match = re.search(r"Notifica Compra por \$([0-9\.]+)", raw_text)
        comercio_match = re.search(r"Lugar:\s*([A-Z0-9\s\-\.]+)", raw_text, re.IGNORECASE)
        
        return {
            'monto': int(monto_match.group(1).replace('.', '')) if monto_match else None,
            'comercio_raw': comercio_match.group(1).strip() if comercio_match else "SANTANDER_ESTABLECIMIENTO",
            'identificador_tarjeta': None,
            'tipo': 'EGRESO'
        }


class ParserFactory:
    _STRATEGIES = {
        'gmail_bancoestado_v1': BancoEstadoParserV1(),
        'gmail_santander_v1': SantanderParserV1(),
    }

    @classmethod
    def get(cls, conector_id):
        return cls._STRATEGIES.get(conector_id, None)
