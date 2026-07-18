"""Normalización de nombres de comercio (Fase E4)."""

import re
import unicodedata

from django.db import transaction

# Patrones canónicos: (regex sobre texto normalizado, nombre_fantasia)
MAPEO_CANONICO = [
    (r'^LIDER\b', 'Líder'),
    (r'^JUMBO\b', 'Jumbo'),
    (r'^TOTTUS\b', 'Tottus'),
    (r'^UNIMARC\b', 'Unimarc'),
    (r'^SANTA\s*ISABEL\b', 'Santa Isabel'),
    (r'^COPEC\b', 'Copec'),
    (r'^SHELL\b', 'Shell'),
    (r'^PETROBRAS\b', 'Petrobras'),
    (r'^STARBUCKS\b', 'Starbucks'),
    (r'^MCDONALDS?\b', "McDonald's"),
    (r'^UBER\b', 'Uber'),
    (r'^CABIFY\b', 'Cabify'),
    (r'^FALABELLA\b', 'Falabella'),
    (r'^PARIS\b', 'Paris'),
    (r'^RIPLEY\b', 'Ripley'),
]


def _normalizar_clave(texto):
    if not texto:
        return ''
    t = unicodedata.normalize('NFKD', texto)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = t.upper().strip()
    t = re.sub(r'\s+', ' ', t)
    return t


def nombre_canonico_sugerido(comercio_raw):
    """Devuelve un nombre fantasia sugerido a partir del texto crudo del banco."""
    clave = _normalizar_clave(comercio_raw)
    if not clave:
        return 'COMERCIO DESCONOCIDO'

    for patron, nombre in MAPEO_CANONICO:
        if re.search(patron, clave):
            return nombre

    # Quitar sufijos de ciudad comunes si quedan tokens
    tokens = clave.split()
    ciudades = {
        'IQUIQUE', 'ANTOFAGASTA', 'SANTIAGO', 'VALPARAISO', 'CONCEPCION',
        'LA', 'SERENA', 'TEMUCO', 'PUERTO', 'MONTT', 'ARICA', 'CALAMA',
    }
    while tokens and tokens[-1] in ciudades:
        tokens.pop()
    if tokens:
        # Title-case suave del resto
        return ' '.join(w.capitalize() for w in tokens)
    return comercio_raw.strip()[:150]


def resolver_comercio(comercio_raw, categoria_sugerida=None):
    """
    Resuelve o crea Comercio + AliasComercio.
    1) Alias exacto
    2) Nombre fantasia exacto / canónico
    3) Crea comercio canónico + alias al texto raw
    """
    from core.models import Comercio, AliasComercio

    raw = (comercio_raw or '').strip()
    if not raw:
        raw = 'COMERCIO DESCONOCIDO'

    # 1. Alias exacto (case-insensitive)
    alias = AliasComercio.objects.filter(texto_raw__iexact=raw).select_related('comercio').first()
    if alias:
        return alias.comercio

    canonico = nombre_canonico_sugerido(raw)

    with transaction.atomic():
        comercio = Comercio.objects.filter(nombre_fantasia__iexact=canonico).first()
        if not comercio:
            comercio = Comercio.objects.create(
                nombre_fantasia=canonico[:150],
                categoria_sugerida=categoria_sugerida,
            )
        elif categoria_sugerida and not comercio.categoria_sugerida_id:
            comercio.categoria_sugerida = categoria_sugerida
            comercio.save(update_fields=['categoria_sugerida'])

        AliasComercio.objects.get_or_create(
            texto_raw=raw[:150],
            defaults={'comercio': comercio},
        )

    return comercio
