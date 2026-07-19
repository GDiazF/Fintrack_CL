"""Reportes: analítica del dashboard, export CSV y auditoría (Fase E)."""

import csv
import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from core.models import Movimiento, EventoAuditoria
from core.utils import get_espacio_activo, espacios_del_usuario


def build_chart_payload(espacio, filtrado_qs):
    """Datos JSON-serializables para Chart.js en el dashboard."""
    por_categoria = (
        filtrado_qs.filter(tipo__in=['EGRESO', 'COMISION'])
        .values('categoria__nombre', 'categoria__color_hex')
        .annotate(total=Sum('monto_clp'))
        .order_by('-total')
    )

    labels_cat = []
    data_cat = []
    colors_cat = []
    for row in por_categoria:
        nombre = row['categoria__nombre'] or 'Sin categoría'
        labels_cat.append(nombre)
        data_cat.append(int(row['total'] or 0))
        colors_cat.append(row['categoria__color_hex'] or '#64748b')

    # Últimos 6 meses (ingresos vs egresos) sobre el espacio completo
    hace_6 = timezone.localtime() - timedelta(days=185)
    mensual = (
        Movimiento.objects.filter(
            cuenta__espacio=espacio,
            fecha_transaccion__gte=hace_6,
        )
        .annotate(mes=TruncMonth('fecha_transaccion'))
        .values('mes')
        .annotate(
            egresos=Sum('monto_clp', filter=Q(tipo__in=['EGRESO', 'COMISION'])),
            ingresos=Sum('monto_clp', filter=Q(tipo='INGRESO')),
        )
        .order_by('mes')
    )

    labels_mes = []
    data_egresos = []
    data_ingresos = []
    for row in mensual:
        mes = row['mes']
        labels_mes.append(mes.strftime('%Y-%m') if mes else '?')
        data_egresos.append(int(row['egresos'] or 0))
        data_ingresos.append(int(row['ingresos'] or 0))

    return {
        'categorias': {
            'labels': labels_cat,
            'data': data_cat,
            'colors': colors_cat,
        },
        'mensual': {
            'labels': labels_mes,
            'egresos': data_egresos,
            'ingresos': data_ingresos,
        },
    }


@login_required(login_url='/login/')
def export_csv_view(request):
    """Exporta movimientos del espacio activo (respeta filtros mes/categoría)."""
    espacio = get_espacio_activo(request)
    qs = Movimiento.objects.filter(cuenta__espacio=espacio).select_related(
        'cuenta', 'categoria', 'comercio'
    ).order_by('-fecha_transaccion')

    mes_param = (request.GET.get('mes') or '').strip()
    categoria_id = (request.GET.get('categoria') or '').strip()
    cuenta_id = (request.GET.get('cuenta') or '').strip()

    if mes_param and len(mes_param) >= 7:
        try:
            qs = qs.filter(
                fecha_transaccion__year=int(mes_param[:4]),
                fecha_transaccion__month=int(mes_param[5:7]),
            )
        except ValueError:
            pass

    if categoria_id == 'sin':
        qs = qs.filter(categoria__isnull=True)
    elif categoria_id:
        try:
            qs = qs.filter(categoria_id=int(categoria_id))
        except ValueError:
            pass

    if cuenta_id:
        try:
            qs = qs.filter(cuenta_id=int(cuenta_id), cuenta__espacio=espacio)
        except ValueError:
            pass

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="fintrack_{espacio.id}.csv"'
    response.write('\ufeff')  # BOM para Excel

    writer = csv.writer(response)
    writer.writerow([
        'fecha', 'tipo', 'cuenta', 'comercio_raw', 'comercio',
        'categoria', 'monto_clp', 'conector', 'gmail_message_id',
    ])
    for m in qs.iterator():
        writer.writerow([
            m.fecha_transaccion.isoformat(),
            m.tipo,
            m.cuenta.nombre,
            m.comercio_raw,
            m.comercio.nombre_fantasia if m.comercio_id else '',
            m.categoria.nombre if m.categoria_id else '',
            m.monto_clp,
            m.conector_origen,
            m.gmail_message_id,
        ])
    return response


@login_required(login_url='/login/')
def auditoria_view(request):
    espacio = get_espacio_activo(request)
    eventos = EventoAuditoria.objects.filter(espacio=espacio).select_related(
        'usuario'
    ).order_by('-fecha')[:100]
    return render(request, 'core/auditoria.html', {
        'espacio': espacio,
        'espacios': espacios_del_usuario(request.user),
        'eventos': eventos,
    })


def registrar_auditoria(usuario, espacio, accion, detalles_dict):
    EventoAuditoria.objects.create(
        usuario=usuario,
        espacio=espacio,
        accion=accion,
        detalles=json.dumps(detalles_dict, ensure_ascii=False),
    )
