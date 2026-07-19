from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction, IntegrityError
from django.db.models import Q, Sum
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_POST
import json

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.authentication import WebhookSignatureAuthentication
from core.categorizacion import resolver_categoria_por_reglas
from core.normalizacion import resolver_comercio
from core.parsers.factory import ParserFactory
from core.models import (
    Espacio, InstitucionFinanciera, CuentaFinanciera,
    Moneda, Movimiento, IngestaFallida, Categoria, PerfilUsuario,
)
from core.utils import get_espacio_activo, espacios_del_usuario
from core.reportes_views import build_chart_payload, registrar_auditoria



class IngestaView(APIView):
    """
    Endpoint de Ingesta para registrar movimientos financieros desde notificaciones bancarias.
    Autenticado mediante firma digital HMAC-SHA256.
    """
    authentication_classes = [WebhookSignatureAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Body crudo firmado por GAS. Puede ser JSON directo (simulate) o Base64(JSON)
        # para evitar problemas de UTF-8 con UrlFetch + mails reales.
        import base64 as _b64
        import json as _json
        raw = request.body
        data = None
        try:
            data = _json.loads(raw.decode('utf-8'))
        except Exception:
            try:
                data = _json.loads(_b64.b64decode(raw).decode('utf-8'))
            except Exception:
                data = request.data if isinstance(request.data, dict) else {}
        if not isinstance(data, dict):
            data = {}
        conector_id = data.get('conector')
        gmail_message_id = data.get('gmail_message_id')
        fecha_correo_str = data.get('fecha_correo')
        raw_text = data.get('raw_text')

        if not all([conector_id, gmail_message_id, fecha_correo_str, raw_text]):
            return Response(
                {'error': 'Faltan campos requeridos en el payload'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Idempotencia: movimiento ya creado
        if Movimiento.objects.filter(gmail_message_id=gmail_message_id).exists():
            return Response(
                {'status': 'ok', 'detail': 'Mensaje duplicado procesado anteriormente'},
                status=status.HTTP_200_OK
            )

        # Idempotencia: falla ya registrada (evita reintentos infinitos del GAS)
        if IngestaFallida.objects.filter(gmail_message_id=gmail_message_id).exists():
            return Response(
                {'status': 'ok', 'detail': 'Mensaje fallido ya registrado anteriormente'},
                status=status.HTTP_200_OK
            )

        fecha_correo = parse_datetime(fecha_correo_str)

        # Resolver parser
        parser = ParserFactory.get(conector_id)
        if not parser:
            return self._registrar_falla(
                request.user,
                gmail_message_id=gmail_message_id,
                conector=conector_id or '',
                fecha_correo=fecha_correo,
                raw_text=raw_text,
                motivo=f"Conector '{conector_id}' no soportado",
            )

        # Ejecutar Parsing
        try:
            parsed_data = parser.parsear(raw_text)
        except Exception as e:
            return self._registrar_falla(
                request.user,
                gmail_message_id=gmail_message_id,
                conector=conector_id,
                fecha_correo=fecha_correo,
                raw_text=raw_text,
                motivo=f"Error al procesar parsing: {e}",
            )

        monto = parsed_data.get('monto')
        comercio_raw = parsed_data.get('comercio_raw')
        identificador_tarjeta = parsed_data.get('identificador_tarjeta')
        tipo_movimiento = parsed_data.get('tipo', 'EGRESO')

        if not monto:
            return self._registrar_falla(
                request.user,
                gmail_message_id=gmail_message_id,
                conector=conector_id,
                fecha_correo=fecha_correo,
                raw_text=raw_text,
                motivo='No se pudo extraer un monto válido de la notificación',
            )

        user = request.user
        fecha_transaccion = fecha_correo or now()

        try:
            with transaction.atomic():
                espacio = Espacio.objects.filter(
                    Q(administrador=user) | Q(miembros=user)
                ).first()
                if not espacio:
                    espacio = Espacio.objects.create(
                        nombre="Mi Espacio Principal",
                        administrador=user
                    )

                nombre_institucion = "BancoEstado"
                if "santander" in conector_id:
                    nombre_institucion = "Santander"
                elif "bci" in conector_id:
                    nombre_institucion = "BCI"

                institucion, _ = InstitucionFinanciera.objects.get_or_create(
                    nombre=nombre_institucion,
                    defaults={'tipo': 'BANCO'}
                )

                cuenta = None
                if identificador_tarjeta:
                    cuenta = CuentaFinanciera.objects.filter(
                        espacio=espacio,
                        institucion=institucion,
                        identificador_conector=identificador_tarjeta
                    ).first()

                if not cuenta:
                    cuenta = CuentaFinanciera.objects.filter(
                        espacio=espacio,
                        institucion=institucion,
                        es_predeterminada=True
                    ).first()

                if not cuenta:
                    cuenta_nombre = f"Cuenta {nombre_institucion}"
                    if identificador_tarjeta:
                        cuenta_nombre += f" (*{identificador_tarjeta})"
                    cuenta = CuentaFinanciera.objects.create(
                        espacio=espacio,
                        institucion=institucion,
                        nombre=cuenta_nombre,
                        identificador_conector=identificador_tarjeta,
                        es_predeterminada=True
                    )

                moneda, _ = Moneda.objects.get_or_create(
                    codigo_iso='CLP',
                    defaults={'simbolo': '$', 'decimales': 0}
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
                    gmail_message_id=gmail_message_id
                )

            return Response(
                {
                    'status': 'success',
                    'movimiento_id': movimiento.id,
                    'monto': movimiento.monto_clp,
                    'comercio': movimiento.comercio_raw,
                    'cuenta': movimiento.cuenta.nombre,
                    'tipo': movimiento.tipo,
                },
                status=status.HTTP_201_CREATED
            )

        except IntegrityError:
            return Response(
                {'status': 'ok', 'detail': 'Registro duplicado procesado concurrentemente'},
                status=status.HTTP_200_OK
            )

    def _registrar_falla(self, user, *, gmail_message_id, conector, fecha_correo, raw_text, motivo):
        """
        Persiste la falla y responde HTTP 200 para que el GAS etiquete el hilo
        y no reintente indefinidamente.
        """
        try:
            falla = IngestaFallida.objects.create(
                usuario=user,
                gmail_message_id=gmail_message_id,
                conector=conector or '',
                fecha_correo=fecha_correo,
                raw_text=raw_text,
                motivo_error=motivo[:255],
            )
        except IntegrityError:
            return Response(
                {'status': 'ok', 'detail': 'Mensaje fallido ya registrado anteriormente'},
                status=status.HTTP_200_OK
            )

        return Response(
            {
                'status': 'failed_logged',
                'detail': motivo,
                'ingesta_fallida_id': falla.id,
            },
            status=status.HTTP_200_OK
        )


@login_required(login_url='/login/')
def dashboard_view(request):
    """
    Vista HTML del Dashboard Principal utilizando Django Templates, HTMX y Tailwind.
    Soporta filtros por mes (YYYY-MM) y categoría.
    """
    espacio = get_espacio_activo(request)
    cuentas = CuentaFinanciera.objects.filter(espacio=espacio)

    base_qs = Movimiento.objects.filter(cuenta__espacio=espacio).select_related(
        'cuenta', 'cuenta__institucion', 'comercio', 'categoria'
    )

    mes_param = (request.GET.get('mes') or '').strip()
    categoria_id = (request.GET.get('categoria') or '').strip()

    filtrado = base_qs
    if mes_param and len(mes_param) >= 7:
        try:
            anio = int(mes_param[:4])
            mes = int(mes_param[5:7])
            filtrado = filtrado.filter(
                fecha_transaccion__year=anio,
                fecha_transaccion__month=mes,
            )
        except ValueError:
            pass

    if categoria_id:
        if categoria_id == 'sin':
            filtrado = filtrado.filter(categoria__isnull=True)
        else:
            try:
                filtrado = filtrado.filter(categoria_id=int(categoria_id))
            except ValueError:
                pass

    egresos = filtrado.filter(tipo__in=['EGRESO', 'COMISION']).aggregate(
        t=Sum('monto_clp')
    )['t'] or 0
    ingresos = filtrado.filter(tipo='INGRESO').aggregate(t=Sum('monto_clp'))['t'] or 0

    categorias = Categoria.objects.filter(
        Q(espacio=espacio) | Q(espacio__isnull=True)
    ).order_by('nombre')

    fallidas_pendientes = IngestaFallida.objects.filter(
        usuario=request.user, resuelto=False
    ).count()

    chart_data = build_chart_payload(espacio, filtrado)

    try:
        page_num = max(1, int(request.GET.get('page') or 1))
    except ValueError:
        page_num = 1

    paginator = Paginator(filtrado, 15)
    page = paginator.get_page(page_num)

    query_base = ''
    if mes_param:
        query_base += f'mes={mes_param}&'
    if categoria_id:
        query_base += f'categoria={categoria_id}&'

    context = {
        'espacio': espacio,
        'espacios': espacios_del_usuario(request.user),
        'cuentas': cuentas,
        'movimientos': page.object_list,
        'page_obj': page,
        'paginator': paginator,
        'query_base': query_base,
        'balance': ingresos - egresos,
        'ingresos': ingresos,
        'egresos': egresos,
        'categorias': categorias,
        'filtro_mes': mes_param,
        'filtro_categoria': categoria_id,
        'fallidas_pendientes': fallidas_pendientes,
        'chart_data_json': json.dumps(chart_data),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/movimientos_panel.html', context)

    return render(request, 'core/dashboard.html', context)


@login_required(login_url='/login/')
@require_POST
def movimiento_recategorizar(request, movimiento_id):
    """Cambia la categoría de un movimiento del espacio activo (HTMX)."""
    espacio = get_espacio_activo(request)
    movimiento = get_object_or_404(
        Movimiento.objects.select_related('cuenta', 'cuenta__institucion', 'categoria'),
        pk=movimiento_id,
        cuenta__espacio=espacio,
    )

    categoria_id = (request.POST.get('categoria_id') or '').strip()
    previa = movimiento.categoria_id
    if not categoria_id:
        movimiento.categoria = None
    else:
        categoria = get_object_or_404(
            Categoria.objects.filter(Q(espacio=espacio) | Q(espacio__isnull=True)),
            pk=categoria_id,
        )
        movimiento.categoria = categoria

    movimiento.save(update_fields=['categoria'])
    registrar_auditoria(
        request.user,
        espacio,
        'MODIFICÓ_CATEGORIA_MOVIMIENTO',
        {
            'movimiento_id': movimiento.id,
            'categoria_previa': previa,
            'categoria_nueva': movimiento.categoria_id,
            'comercio_raw': movimiento.comercio_raw,
        },
    )

    categorias = Categoria.objects.filter(
        Q(espacio=espacio) | Q(espacio__isnull=True)
    ).order_by('nombre')

    return render(request, 'core/partials/movimiento_row.html', {
        'mov': movimiento,
        'categorias': categorias,
        'include_card_oob': True,
    })


def login_view(request):
    """
    Vista de inicio de sesión nativo con AuthenticationForm de Django.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = AuthenticationForm(request, data=request.POST or None)
    error = None
    sugerir_reenvio = False

    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
            if not perfil.email_verificado:
                error = 'Debes verificar tu email antes de ingresar. Revisa tu bandeja o reenvía el enlace.'
                sugerir_reenvio = True
            else:
                login(request, user)
                return redirect(request.GET.get('next', '/'))
        else:
            error = 'Nombre de usuario o contraseña incorrectos.'

    return render(request, 'core/login.html', {
        'form': form,
        'error': error,
        'sugerir_reenvio': sugerir_reenvio,
    })


def logout_view(request):
    """
    Vista de cierre de sesión.
    """
    logout(request)
    return redirect('/login/')
