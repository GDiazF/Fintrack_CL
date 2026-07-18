"""Vistas de organización: categorías, reglas, espacios, presupuestos y metas."""

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import (
    Categoria, ReglaCategoria, Presupuesto, MetaAhorro, Movimiento, Espacio,
)
from core.utils import get_espacio_activo, espacios_del_usuario, usuario_puede_acceder_espacio

COLORES_CATEGORIA = [
    '#0d9488', '#10b981', '#3b82f6', '#8b5cf6',
    '#f59e0b', '#ef4444', '#ec4899', '#64748b',
]


def _ctx_base(request):
    espacio = get_espacio_activo(request)
    return {
        'espacio': espacio,
        'espacios': espacios_del_usuario(request.user),
        'colores': COLORES_CATEGORIA,
    }


def _categorias_disponibles(espacio):
    return Categoria.objects.filter(
        Q(espacio=espacio) | Q(espacio__isnull=True)
    ).order_by('nombre')


@login_required(login_url='/login/')
def organizacion_view(request):
    """Página de categorías y reglas del espacio activo."""
    ctx = _ctx_base(request)
    espacio = ctx['espacio']
    ctx['categorias'] = Categoria.objects.filter(espacio=espacio).order_by('nombre')
    ctx['categorias_globales'] = Categoria.objects.filter(espacio__isnull=True).order_by('nombre')
    ctx['categorias_para_reglas'] = _categorias_disponibles(espacio)
    ctx['reglas'] = ReglaCategoria.objects.filter(espacio=espacio).select_related(
        'categoria_destino'
    ).order_by('patron_texto')
    return render(request, 'core/organizacion.html', ctx)


@login_required(login_url='/login/')
@require_POST
def categoria_crear(request):
    espacio = get_espacio_activo(request)
    nombre = (request.POST.get('nombre') or '').strip()
    color = request.POST.get('color_hex') or '#3498DB'
    icono = (request.POST.get('icono') or 'bi-tag').strip()

    if not nombre:
        return HttpResponse('Nombre requerido', status=400)

    try:
        Categoria.objects.create(
            espacio=espacio,
            nombre=nombre[:100],
            color_hex=color[:7],
            icono=icono[:50],
        )
    except IntegrityError:
        pass

    return _partial_categorias(request, espacio)


@login_required(login_url='/login/')
@require_POST
def categoria_eliminar(request, categoria_id):
    espacio = get_espacio_activo(request)
    categoria = get_object_or_404(Categoria, pk=categoria_id, espacio=espacio)
    categoria.delete()
    return _partial_categorias(request, espacio)


@login_required(login_url='/login/')
@require_POST
def regla_crear(request):
    espacio = get_espacio_activo(request)
    patron = (request.POST.get('patron_texto') or '').strip().upper()
    categoria_id = request.POST.get('categoria_id')

    if not patron or not categoria_id:
        return HttpResponse('Patrón y categoría requeridos', status=400)

    categoria = get_object_or_404(_categorias_disponibles(espacio), pk=categoria_id)

    ReglaCategoria.objects.create(
        espacio=espacio,
        patron_texto=patron[:100],
        categoria_destino=categoria,
    )
    return _partial_reglas(request, espacio)


@login_required(login_url='/login/')
@require_POST
def regla_eliminar(request, regla_id):
    espacio = get_espacio_activo(request)
    regla = get_object_or_404(ReglaCategoria, pk=regla_id, espacio=espacio)
    regla.delete()
    return _partial_reglas(request, espacio)


@login_required(login_url='/login/')
@require_POST
def espacio_activar(request):
    espacio_id = request.POST.get('espacio_id')
    espacio = get_object_or_404(Espacio, pk=espacio_id)
    if not usuario_puede_acceder_espacio(request.user, espacio):
        return HttpResponseForbidden('Sin acceso a este espacio')
    request.session['espacio_id'] = espacio.id
    return redirect(request.POST.get('next') or 'dashboard')


@login_required(login_url='/login/')
@require_POST
def espacio_crear(request):
    nombre = (request.POST.get('nombre') or '').strip()
    if not nombre:
        return redirect('organizacion')
    espacio = Espacio.objects.create(
        nombre=nombre[:100],
        administrador=request.user,
    )
    request.session['espacio_id'] = espacio.id
    next_url = request.POST.get('next') or 'organizacion'
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect(next_url)


@login_required(login_url='/login/')
def presupuestos_view(request):
    ctx = _ctx_base(request)
    espacio = ctx['espacio']
    ahora = timezone.localtime()
    mes = int(request.GET.get('mes') or ahora.month)
    anio = int(request.GET.get('anio') or ahora.year)

    presupuestos = Presupuesto.objects.filter(
        espacio=espacio, mes=mes, anio=anio
    ).select_related('categoria')

    items = []
    for p in presupuestos:
        gastado = Movimiento.objects.filter(
            cuenta__espacio=espacio,
            categoria=p.categoria,
            tipo='EGRESO',
            fecha_transaccion__year=anio,
            fecha_transaccion__month=mes,
        ).aggregate(t=Sum('monto_clp'))['t'] or 0
        pct = min(100, int((gastado / p.monto_limite) * 100)) if p.monto_limite else 0
        items.append({'presupuesto': p, 'gastado': gastado, 'pct': pct})

    ctx.update({
        'items': items,
        'mes': mes,
        'anio': anio,
        'categorias': _categorias_disponibles(espacio),
    })
    return render(request, 'core/presupuestos.html', ctx)


@login_required(login_url='/login/')
@require_POST
def presupuesto_crear(request):
    espacio = get_espacio_activo(request)
    categoria_id = request.POST.get('categoria_id')
    monto = request.POST.get('monto_limite')
    mes = int(request.POST.get('mes') or timezone.localtime().month)
    anio = int(request.POST.get('anio') or timezone.localtime().year)

    categoria = get_object_or_404(_categorias_disponibles(espacio), pk=categoria_id)
    try:
        Presupuesto.objects.update_or_create(
            espacio=espacio,
            categoria=categoria,
            mes=mes,
            anio=anio,
            defaults={'monto_limite': int(monto)},
        )
    except (TypeError, ValueError):
        pass
    return redirect(f'/presupuestos/?mes={mes}&anio={anio}')


@login_required(login_url='/login/')
def metas_view(request):
    ctx = _ctx_base(request)
    espacio = ctx['espacio']
    metas = MetaAhorro.objects.filter(espacio=espacio).order_by('nombre')
    items = []
    for m in metas:
        pct = min(100, int((m.monto_actual / m.monto_objetivo) * 100)) if m.monto_objetivo else 0
        items.append({'meta': m, 'pct': pct})
    ctx['items'] = items
    return render(request, 'core/metas.html', ctx)


@login_required(login_url='/login/')
@require_POST
def meta_crear(request):
    espacio = get_espacio_activo(request)
    nombre = (request.POST.get('nombre') or '').strip()
    objetivo = request.POST.get('monto_objetivo')
    actual = request.POST.get('monto_actual') or 0
    if nombre and objetivo:
        try:
            MetaAhorro.objects.create(
                espacio=espacio,
                nombre=nombre[:100],
                monto_objetivo=int(objetivo),
                monto_actual=int(actual),
            )
        except (TypeError, ValueError):
            pass
    return redirect('metas')


@login_required(login_url='/login/')
@require_POST
def meta_actualizar(request, meta_id):
    espacio = get_espacio_activo(request)
    meta = get_object_or_404(MetaAhorro, pk=meta_id, espacio=espacio)
    actual = request.POST.get('monto_actual')
    try:
        meta.monto_actual = int(actual)
        meta.save(update_fields=['monto_actual'])
    except (TypeError, ValueError):
        pass
    return redirect('metas')


def _partial_categorias(request, espacio):
    categorias = Categoria.objects.filter(espacio=espacio).order_by('nombre')
    return render(request, 'core/partials/categorias_list.html', {
        'categorias': categorias,
        'espacio': espacio,
    })


def _partial_reglas(request, espacio):
    reglas = ReglaCategoria.objects.filter(espacio=espacio).select_related(
        'categoria_destino'
    ).order_by('patron_texto')
    return render(request, 'core/partials/reglas_list.html', {
        'reglas': reglas,
        'espacio': espacio,
    })
