"""Lógica compartida de ingesta: parse → cuenta → movimiento (webhook y reintento UI)."""

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.timezone import now

from core.categorizacion import resolver_categoria_por_reglas
from core.normalizacion import resolver_comercio
from core.parsers.factory import ParserFactory
from core.models import (
    Espacio,
    InstitucionFinanciera,
    CuentaFinanciera,
    Moneda,
    Movimiento,
)


def nombre_institucion_para_conector(conector_id: str) -> str:
    cid = (conector_id or '').lower()
    if 'santander' in cid:
        return 'Santander'
    if 'bci' in cid:
        return 'BCI'
    return 'BancoEstado'


def resolver_o_crear_cuenta(espacio, institucion, identificador_tarjeta):
    """
    Una cuenta por últimos 4 dígitos cuando el mail los trae.
    Sin dígitos → cuenta genérica del banco (no reutiliza una *1234 ajena).
    """
    tarjeta = (identificador_tarjeta or '').strip() or None

    if tarjeta:
        cuenta = CuentaFinanciera.objects.filter(
            espacio=espacio,
            institucion=institucion,
            identificador_conector=tarjeta,
        ).first()
        if cuenta:
            return cuenta

        ya_hay_pred = CuentaFinanciera.objects.filter(
            espacio=espacio,
            institucion=institucion,
            es_predeterminada=True,
        ).exists()
        return CuentaFinanciera.objects.create(
            espacio=espacio,
            institucion=institucion,
            nombre=f'Cuenta {institucion.nombre} (*{tarjeta})',
            identificador_conector=tarjeta,
            es_predeterminada=not ya_hay_pred,
        )

    # Sin tarjeta: preferir cuenta genérica (sin identificador)
    cuenta = CuentaFinanciera.objects.filter(
        espacio=espacio,
        institucion=institucion,
        identificador_conector__isnull=True,
    ).first()
    if cuenta:
        return cuenta

    cuenta = CuentaFinanciera.objects.filter(
        espacio=espacio,
        institucion=institucion,
        identificador_conector='',
    ).first()
    if cuenta:
        return cuenta

    return CuentaFinanciera.objects.create(
        espacio=espacio,
        institucion=institucion,
        nombre=f'Cuenta {institucion.nombre}',
        identificador_conector=None,
        es_predeterminada=True,
    )


@dataclass
class ResultadoIngesta:
    ok: bool
    motivo: str = ''
    movimiento: Movimiento | None = None
    ya_existia: bool = False


def crear_movimiento_desde_parse(
    *,
    user,
    conector_id: str,
    gmail_message_id: str,
    fecha_correo,
    raw_text: str,
    parsed_data: dict,
) -> ResultadoIngesta:
    """Persiste Movimiento a partir de un parse ya validado (con monto)."""
    monto = parsed_data.get('monto')
    if not monto:
        return ResultadoIngesta(ok=False, motivo='No se pudo extraer un monto válido de la notificación')

    comercio_raw = parsed_data.get('comercio_raw') or 'COMERCIO DESCONOCIDO'
    identificador_tarjeta = parsed_data.get('identificador_tarjeta')
    tipo_movimiento = parsed_data.get('tipo', 'EGRESO')
    fecha_transaccion = fecha_correo or now()

    try:
        with transaction.atomic():
            if Movimiento.objects.filter(gmail_message_id=gmail_message_id).exists():
                mov = Movimiento.objects.get(gmail_message_id=gmail_message_id)
                return ResultadoIngesta(ok=True, movimiento=mov, ya_existia=True)

            espacio = Espacio.objects.filter(
                Q(administrador=user) | Q(miembros=user)
            ).first()
            if not espacio:
                espacio = Espacio.objects.create(
                    nombre='Mi Espacio Principal',
                    administrador=user,
                )

            nombre_inst = nombre_institucion_para_conector(conector_id)
            institucion, _ = InstitucionFinanciera.objects.get_or_create(
                nombre=nombre_inst,
                defaults={'tipo': 'BANCO'},
            )

            cuenta = resolver_o_crear_cuenta(espacio, institucion, identificador_tarjeta)

            moneda, _ = Moneda.objects.get_or_create(
                codigo_iso='CLP',
                defaults={'simbolo': '$', 'decimales': 0},
            )

            comercio = resolver_comercio(comercio_raw)
            categoria = None
            if comercio and comercio.categoria_sugerida:
                categoria = comercio.categoria_sugerida
            if not categoria:
                categoria = resolver_categoria_por_reglas(espacio, comercio_raw)

            movimiento = Movimiento.objects.create(
                cuenta=cuenta,
                comercio=comercio,
                comercio_raw=comercio_raw,
                categoria=categoria,
                fecha_transaccion=fecha_transaccion,
                monto_original=monto,
                moneda_original=moneda,
                monto_clp=int(monto),
                tipo=tipo_movimiento,
                raw_text=raw_text,
                conector_origen=conector_id,
                gmail_message_id=gmail_message_id,
            )
            return ResultadoIngesta(ok=True, movimiento=movimiento)

    except IntegrityError:
        mov = Movimiento.objects.filter(gmail_message_id=gmail_message_id).first()
        if mov:
            return ResultadoIngesta(ok=True, movimiento=mov, ya_existia=True)
        return ResultadoIngesta(ok=False, motivo='Conflicto al guardar el movimiento')


def intentar_ingesta_desde_raw(
    *,
    user,
    conector_id: str,
    gmail_message_id: str,
    fecha_correo,
    raw_text: str,
) -> ResultadoIngesta:
    """Parsea y crea movimiento. No escribe IngestaFallida (eso lo decide el caller)."""
    if Movimiento.objects.filter(gmail_message_id=gmail_message_id).exists():
        mov = Movimiento.objects.get(gmail_message_id=gmail_message_id)
        return ResultadoIngesta(ok=True, movimiento=mov, ya_existia=True)

    parser = ParserFactory.get(conector_id)
    if not parser:
        return ResultadoIngesta(ok=False, motivo=f"Conector '{conector_id}' no soportado")

    try:
        parsed_data = parser.parsear(raw_text)
    except Exception as e:
        return ResultadoIngesta(ok=False, motivo=f'Error al procesar parsing: {e}')

    return crear_movimiento_desde_parse(
        user=user,
        conector_id=conector_id,
        gmail_message_id=gmail_message_id,
        fecha_correo=fecha_correo,
        raw_text=raw_text,
        parsed_data=parsed_data,
    )
