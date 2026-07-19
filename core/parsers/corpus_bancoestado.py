"""
Corpus mínimo de textos BancoEstado para tests y validación de parsers (Fase A5).

Estos samples imitan el plain-text típico de notificaciones; se ajustan cuando
lleguen mails reales en Fase C.
"""

BE_COMPRA = (
    "BancoEstado: Hola Diego, confirmamos tu compra por un monto de "
    "$4.990 en CAFETERIA IQUIQUE con tu tarjeta *5678 el 17/07/2026."
)

BE_COMPRA_COPEC = (
    "BancoEstado: Hola Diego, confirmamos tu compra por un monto de "
    "$7.490 en COPEC S.A. con tu tarjeta *1234 el 17/07/2026."
)

BE_TRANSFERENCIA = (
    "BancoEstado: Hola Diego, confirmamos que transferiste $50.000 a "
    "MARIA GONZALEZ el 17/07/2026 desde tu CuentaRUT."
)

BE_INGRESO = (
    "BancoEstado: Hola Diego, recibiste un abono por $850.000 de "
    "EMPRESA SPA el 17/07/2026 en tu CuentaRUT."
)

BE_SIN_MONTO = (
    "BancoEstado: Hola Diego, te informamos sobre un movimiento en tu cuenta. "
    "Revisa los detalles en la app."
)

BE_PAGO_SERVICIOS = (
    "BancoEstado: Comprobante de pago de servicios.\n"
    "Hola, pagaste a AGUAS ANDINAS por un monto de $45.890 el 10/07/2026 "
    "desde tu CuentaRUT."
)

BE_AVISO_ENVIO = (
    "BancoEstado: Aviso de envío o recepción de dinero.\n"
    "Hola, enviaste dinero por $12.000 a MARIA GONZALEZ el 11/07/2026."
)

BE_AVISO_RECEPCION = (
    "BancoEstado: Aviso de envío o recepción de dinero.\n"
    "Hola, recibiste dinero por $80.000 de EMPRESA SPA el 12/07/2026."
)

CORPUS_BANCOESTADO_V1 = {
    'compra': BE_COMPRA,
    'compra_copec': BE_COMPRA_COPEC,
    'transferencia': BE_TRANSFERENCIA,
    'ingreso': BE_INGRESO,
    'sin_monto': BE_SIN_MONTO,
    'pago_servicios': BE_PAGO_SERVICIOS,
    'aviso_envio': BE_AVISO_ENVIO,
    'aviso_recepcion': BE_AVISO_RECEPCION,
}
