"""Vistas de autenticación, perfil y onboarding."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST, require_http_methods

from core.models import Usuario, PerfilUsuario, IngestaFallida
from core.gas_template import build_gas_script
from core.email_service import enviar_verificacion_email
from core.utils import get_espacio_activo, espacios_del_usuario


class RegistroForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            from django.core.exceptions import ValidationError
            raise ValidationError('El email es obligatorio.')
        if Usuario.objects.filter(email__iexact=email).exists():
            from django.core.exceptions import ValidationError
            raise ValidationError('Ya existe una cuenta con este email.')
        return email


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = RegistroForm(request.POST or None)
    error = None

    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
            perfil.email_verificado = False
            perfil.save(update_fields=['email_verificado'])
            try:
                enviar_verificacion_email(user)
            except Exception:
                messages.warning(
                    request,
                    'Cuenta creada, pero no se pudo enviar el correo. Usa "Reenviar verificación".',
                )
                return redirect('reenviar_verificacion')
            return redirect('registro_pendiente')
        error = 'Revisa los datos del formulario.'

    return render(request, 'core/register.html', {'form': form, 'error': error})


def registro_pendiente_view(request):
    return render(request, 'core/registro_pendiente.html')


def verificar_email_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = Usuario.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
        perfil.email_verificado = True
        perfil.save(update_fields=['email_verificado'])
        request.session['mostrar_onboarding'] = True
        login(request, user)
        messages.success(request, 'Email verificado. ¡Bienvenido a Fintrack CL!')
        return redirect('onboarding')

    return render(request, 'core/verificar_invalido.html', status=400)


@require_http_methods(['GET', 'POST'])
def reenviar_verificacion_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    enviado = False
    error = None

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        if not email:
            error = 'Ingresa tu email.'
        else:
            user = Usuario.objects.filter(email__iexact=email).first()
            # Respuesta genérica para no filtrar cuentas
            if user:
                perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
                if not perfil.email_verificado:
                    try:
                        enviar_verificacion_email(user)
                    except Exception:
                        error = 'No se pudo enviar el correo. Revisa la configuración SMTP.'
            enviado = error is None

    return render(request, 'core/reenviar_verificacion.html', {
        'enviado': enviado,
        'error': error,
    })


class FintrackPasswordResetView(PasswordResetView):
    template_name = 'core/password_reset_form.html'
    email_template_name = 'core/email/password_reset.txt'
    subject_template_name = 'core/email/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')
    form_class = PasswordResetForm

    def form_valid(self, form):
        from urllib.parse import urlparse
        parsed = urlparse(settings.PUBLIC_BASE_URL)
        opts = {
            'use_https': parsed.scheme == 'https',
            'token_generator': self.token_generator,
            'from_email': self.from_email,
            'email_template_name': self.email_template_name,
            'subject_template_name': self.subject_template_name,
            'request': self.request,
            'html_email_template_name': self.html_email_template_name,
            'extra_email_context': self.extra_email_context,
            'domain_override': parsed.netloc or self.request.get_host(),
        }
        form.save(**opts)
        return redirect(self.get_success_url())


class FintrackPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'core/password_reset_done.html'


class FintrackPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'core/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')
    form_class = SetPasswordForm


class FintrackPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'core/password_reset_complete.html'


@login_required(login_url='/login/')
def perfil_view(request):
    """Edición de datos de cuenta (nombre, email, teléfono)."""
    user = request.user
    perfil, _ = PerfilUsuario.objects.get_or_create(user=user)

    if request.method == 'POST':
        first_name = (request.POST.get('first_name') or '').strip()[:150]
        last_name = (request.POST.get('last_name') or '').strip()[:150]
        email = (request.POST.get('email') or '').strip()[:254]
        telefono = (request.POST.get('telefono') or '').strip()[:20]

        email_changed = email.lower() != (user.email or '').lower()
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.telefono = telefono
        user.save(update_fields=['first_name', 'last_name', 'email', 'telefono'])

        if email_changed and email:
            perfil.email_verificado = False
            perfil.save(update_fields=['email_verificado'])
            try:
                enviar_verificacion_email(user)
            except Exception:
                pass
            logout(request)
            messages.warning(
                request,
                'Email actualizado. Verifica el nuevo correo antes de volver a entrar.',
            )
            return redirect('registro_pendiente')
        messages.success(request, 'Perfil actualizado.')
        return redirect('perfil')

    return render(request, 'core/perfil.html', {
        'perfil': perfil,
        'espacio': get_espacio_activo(request),
        'espacios': espacios_del_usuario(request.user),
    })


@login_required(login_url='/login/')
def onboarding_view(request):
    """Wizard GAS + credenciales API."""
    user = request.user
    perfil, _ = PerfilUsuario.objects.get_or_create(user=user)

    endpoint = f"{settings.PUBLIC_BASE_URL}/api/v1/conectores/ingesta/"
    mostrar_secreto = not perfil.secret_revelado
    secreto_para_gas = perfil.api_secret_token if mostrar_secreto else '***ROTA_EL_SECRETO_PARA_VERLO***'

    gas_code = build_gas_script(
        api_key_id=perfil.api_key_id,
        api_secret=secreto_para_gas,
        endpoint_url=endpoint,
    )

    return render(request, 'core/onboarding.html', {
        'perfil': perfil,
        'gas_code': gas_code,
        'mostrar_secreto': mostrar_secreto,
        'endpoint_url': endpoint,
        'mostrar_onboarding': request.session.pop('mostrar_onboarding', False),
        'espacio': get_espacio_activo(request),
        'espacios': espacios_del_usuario(request.user),
    })


@login_required(login_url='/login/')
@require_POST
def confirmar_secreto(request):
    perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)
    perfil.confirmar_secreto_guardado()
    messages.success(request, 'Secreto ocultado. Ya puedes usar el script en GAS.')
    return redirect('onboarding')


@login_required(login_url='/login/')
@require_POST
def rotar_secreto(request):
    perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)
    perfil.rotar_secret()
    messages.success(request, 'Nuevo secreto generado. Cópialo y actualiza el GAS.')
    return redirect('onboarding')


@login_required(login_url='/login/')
def fallidas_view(request):
    qs = IngestaFallida.objects.filter(usuario=request.user)
    pendientes = qs.filter(resuelto=False).count()
    return render(request, 'core/fallidas.html', {
        'fallidas': qs[:100],
        'pendientes': pendientes,
        'espacio': get_espacio_activo(request),
        'espacios': espacios_del_usuario(request.user),
    })


@login_required(login_url='/login/')
@require_POST
def fallida_resolver(request, fallida_id):
    falla = get_object_or_404(IngestaFallida, pk=fallida_id, usuario=request.user)
    falla.resuelto = True
    falla.save(update_fields=['resuelto'])
    return redirect('fallidas')
