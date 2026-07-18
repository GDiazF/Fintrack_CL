"""Helpers de categorización automática por Espacio."""


def resolver_categoria_por_reglas(espacio, comercio_raw, reglas_qs=None):
    """
    Busca la primera regla cuyo patron_texto aparece como substring
    dentro de comercio_raw (case-insensitive).

    Prioriza patrones más largos para preferir coincidencias específicas
    (ej: "COPEC EXPRESS" sobre "COPEC").
    """
    from core.models import ReglaCategoria

    if not comercio_raw:
        return None

    haystack = comercio_raw.upper()
    reglas = list(reglas_qs if reglas_qs is not None else ReglaCategoria.objects.filter(espacio=espacio))
    reglas.sort(key=lambda r: len(r.patron_texto or ''), reverse=True)

    for regla in reglas:
        patron = (regla.patron_texto or '').strip()
        if patron and patron.upper() in haystack:
            return regla.categoria_destino

    return None
