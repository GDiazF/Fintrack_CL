"""Envío de correos transaccionales (verificación, etc.)."""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def build_verify_url(user) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.PUBLIC_BASE_URL}/verificar/{uid}/{token}/"


def enviar_verificacion_email(user) -> None:
    """Envía el correo de verificación. Sin EMAIL_HOST va a consola."""
    if not user.email:
        return

    verify_url = build_verify_url(user)
    context = {
        'user': user,
        'verify_url': verify_url,
        'site_name': 'Fintrack CL',
    }
    subject = 'Verifica tu cuenta — Fintrack CL'
    body = render_to_string('core/email/verificar_cuenta.txt', context)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
