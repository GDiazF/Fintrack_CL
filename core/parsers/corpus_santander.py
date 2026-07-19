"""Corpus mínimo Santander (fixtures de desarrollo / tests)."""

SA_COMPRA = (
    "Santander: Notifica Compra por $12.990\n"
    "Lugar: LIDER IQUIQUE\n"
    "Fecha: 17/07/2026\n"
    "Tarjeta: ****4321"
)

SA_COMPRA_STARBUCKS = (
    "Santander: Notifica Compra por $4.500\n"
    "Lugar: STARBUCKS CAFE SANTIAGO\n"
    "Fecha: 18/07/2026"
)

SA_TRANSFERENCIA = (
    "Santander: Realizaste una transferencia por $25.000 a PEDRO SOTO el 18/07/2026."
)

SA_COMPROBANTE_TRANSFERENCIA = """Santander
Comprobante
Transferencia de fondos
Estimado(a) GUILLERMO RICARDO DIAZ FLORES:
Te enviamos el detalle de la transferencia realizada el 11/07/2026.

*Monto transferido*
*$ 3.200*
*Datos de origen*
Tipo de cuenta
Cuenta Corriente
*Datos de destino*
Nombre
Victor
RUT
20.707.311-3
Banco
Tenpo Prepago
"""

CORPUS_SANTANDER_V1 = {
    'compra': SA_COMPRA,
    'compra_starbucks': SA_COMPRA_STARBUCKS,
    'transferencia': SA_TRANSFERENCIA,
    'comprobante_transferencia': SA_COMPROBANTE_TRANSFERENCIA,
}
