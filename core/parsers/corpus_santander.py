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

CORPUS_SANTANDER_V1 = {
    'compra': SA_COMPRA,
    'compra_starbucks': SA_COMPRA_STARBUCKS,
    'transferencia': SA_TRANSFERENCIA,
}
