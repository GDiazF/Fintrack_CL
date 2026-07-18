"""Corpus mínimo BCI (fixtures de desarrollo / tests)."""

BCI_COMPRA = (
    "BCI: Informamos compra por $15.990 en JUMBO ANTOFAGASTA "
    "con tarjeta *9876 el 18/07/2026."
)

BCI_COMPRA_COPEC = (
    "BCI: Se registró una compra de $9.200 en COPEC EXPRESS "
    "con tu tarjeta terminada en 9876."
)

BCI_ABONO = (
    "BCI: Recibiste una transferencia por $120.000 de "
    "CLAUDIA RAMIREZ el 18/07/2026."
)

CORPUS_BCI_V1 = {
    'compra': BCI_COMPRA,
    'compra_copec': BCI_COMPRA_COPEC,
    'abono': BCI_ABONO,
}
