from django.shortcuts import render, redirect
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.authentication import WebhookSignatureAuthentication
from core.parsers.factory import ParserFactory
from core.models import (
    Espacio, InstitucionFinanciera, CuentaFinanciera,
    Comercio, Categoria, ReglaCategoria, Moneda, Movimiento,
    PerfilUsuario
)

class IngestaView(APIView):
    """
    Endpoint de Ingesta para registrar movimientos financieros desde notificaciones bancarias.
    Autenticado mediante firma digital HMAC-SHA256.
    """
    authentication_classes = [WebhookSignatureAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        data = request.data
        conector_id = data.get('conector')
        gmail_message_id = data.get('gmail_message_id')
        fecha_correo_str = data.get('fecha_correo')
        raw_text = data.get('raw_text')

        if not all([conector_id, gmail_message_id, fecha_correo_str, raw_text]):
            return Response(
                {'error': 'Faltan campos requeridos en el payload'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Control de Duplicados (Idempotencia absoluta)
        if Movimiento.objects.filter(gmail_message_id=gmail_message_id).exists():
            return Response(
                {'status': 'ok', 'detail': 'Mensaje duplicado procesado anteriormente'},
                status=status.HTTP_200_OK
            )

        # Resolver parser
        parser = ParserFactory.get(conector_id)
        if not parser:
            return Response(
                {'error': f"Conector '{conector_id}' no soportado"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ejecutar Parsing
        try:
            parsed_data = parser.parsear(raw_text)
        except Exception as e:
            return Response(
                {'error': f"Error al procesar parsing del correo: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        monto = parsed_data.get('monto')
        comercio_raw = parsed_data.get('comercio_raw')
        identificador_tarjeta = parsed_data.get('identificador_tarjeta')
        tipo_movimiento = parsed_data.get('tipo', 'EGRESO')

        if not monto:
            return Response(
                {'error': 'No se pudo extraer un monto válido de la notificación'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        fecha_transaccion = parse_datetime(fecha_correo_str) or now()

        try:
            with transaction.atomic():
                # 1. Obtener o crear Espacio del usuario
                espacio = Espacio.objects.filter(
                    Q(administrador=user) | Q(miembros=user)
                ).first()
                if not espacio:
                    espacio = Espacio.objects.create(
                        nombre="Mi Espacio Principal",
                        administrador=user
                    )

                # 2. Identificar la Institución Financiera según el conector
                nombre_institucion = "BancoEstado"
                if "santander" in conector_id:
                    nombre_institucion = "Santander"
                elif "bci" in conector_id:
                    nombre_institucion = "BCI"

                institucion, _ = InstitucionFinanciera.objects.get_or_create(
                    nombre=nombre_institucion,
                    defaults={'tipo': 'BANCO'}
                )

                # 3. Obtener o crear la Cuenta Financiera asociada al Espacio
                # Intentamos buscar por identificador de tarjeta en el espacio
                cuenta = None
                if identificador_tarjeta:
                    cuenta = CuentaFinanciera.objects.filter(
                        espacio=espacio,
                        institucion=institucion,
                        identificador_conector=identificador_tarjeta
                    ).first()

                if not cuenta:
                    # Si no se encuentra, buscar la predeterminada o crear una nueva genérica
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

                # 4. Moneda (Por defecto CLP)
                moneda, _ = Moneda.objects.get_or_create(
                    codigo_iso='CLP',
                    defaults={'simbolo': '$', 'decimales': 0}
                )

                # 5. Resolver Comercio
                comercio = Comercio.objects.filter(nombre_fantasia__iexact=comercio_raw).first()
                if not comercio and comercio_raw:
                    comercio = Comercio.objects.create(nombre_fantasia=comercio_raw)

                # 6. Intentar mapear categoría sugerida del comercio o reglas
                categoria = None
                if comercio and comercio.categoria_sugerida:
                    categoria = comercio.categoria_sugerida

                if not categoria:
                    # Buscar por patrones de texto personalizados
                    regla = ReglaCategoria.objects.filter(
                        espacio=espacio,
                        patron_texto__in=[comercio_raw.upper(), comercio_raw.lower()]
                    ).first()
                    if not regla:
                        # Búsqueda substring parcial sencilla
                        regla = ReglaCategoria.objects.filter(
                            espacio=espacio
                        ).filter(
                            Q(patron_texto__icontains=comercio_raw) | Q(patron_texto__iexact=comercio_raw)
                        ).first()
                    
                    if regla:
                        categoria = regla.categoria_destino

                # 7. Registrar Movimiento
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
                    'cuenta': movimiento.cuenta.nombre
                },
                status=status.HTTP_201_CREATED
            )

        except IntegrityError:
            # Captura de reintentos concurrentes de última hora
            return Response(
                {'status': 'ok', 'detail': 'Registro duplicado procesado concurrentemente'},
                status=status.HTTP_200_OK
            )


@login_required(login_url='/login/')
def dashboard_view(request):
    """
    Vista HTML del Dashboard Principal utilizando Django Templates, HTMX y Tailwind.
    """
    user = request.user
    espacio = Espacio.objects.filter(Q(administrador=user) | Q(miembros=user)).first()
    
    if not espacio:
        espacio = Espacio.objects.create(nombre="Mi Espacio Principal", administrador=user)

    cuentas = CuentaFinanciera.objects.filter(espacio=espacio)
    
    # Obtener los últimos 15 movimientos ordenados por fecha
    movimientos = Movimiento.objects.filter(cuenta__espacio=espacio).select_related(
        'cuenta', 'comercio', 'categoria'
    )[:15]

    # Calcular balances rápidos
    total_egresos = sum(
        mov.monto_clp for mov in Movimiento.objects.filter(
            cuenta__espacio=espacio, tipo='EGRESO'
        )
    )
    total_ingresos = sum(
        mov.monto_clp for mov in Movimiento.objects.filter(
            cuenta__espacio=espacio, tipo='INGRESO'
        )
    )

    context = {
        'espacio': espacio,
        'cuentas': cuentas,
        'movimientos': movimientos,
        'balance': total_ingresos - total_egresos,
        'ingresos': total_ingresos,
        'egresos': total_egresos,
    }

    # Soporte HTMX para refrescar la lista de movimientos de manera parcial
    if request.headers.get('HX-Request'):
        return render(request, 'core/htmx_movimientos_list.html', context)

    return render(request, 'core/dashboard.html', context)


@login_required(login_url='/login/')
def perfil_view(request):
    """
    Página de perfil del usuario: muestra las claves API y el código de GAS pre-rellenado.
    """
    user = request.user
    perfil, _ = PerfilUsuario.objects.get_or_create(user=user)

    # Generar el código GAS pre-rellenado con las claves del usuario
    gas_code = f"""var API_KEY_ID = \"{perfil.api_key_id}\";
var API_SECRET = \"{perfil.api_secret_token}\";
var ENDPOINT_URL = \"http://127.0.0.1:8080/api/v1/conectores/ingesta/\";"""

    context = {
        'perfil': perfil,
        'gas_code': gas_code,
    }
    return render(request, 'core/perfil.html', context)


def login_view(request):
    """
    Vista de inicio de sesión nativo con AuthenticationForm de Django.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = AuthenticationForm(request, data=request.POST or None)
    error = None

    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect(request.GET.get('next', '/'))
        else:
            error = 'Nombre de usuario o contraseña incorrectos.'

    return render(request, 'core/login.html', {'form': form, 'error': error})


def logout_view(request):
    """
    Vista de cierre de sesión.
    """
    logout(request)
    return redirect('/login/')
