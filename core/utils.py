"""Utilidades compartidas del core (espacios, acceso)."""

from django.db.models import Q

from core.models import Espacio


def espacios_del_usuario(user):
    return Espacio.objects.filter(
        Q(administrador=user) | Q(miembros=user)
    ).distinct().order_by('nombre')


def get_espacio_activo(request):
    """
    Resuelve el Espacio activo desde la sesión.
    Si no hay uno válido, usa el primero del usuario o crea 'Mi Espacio Principal'.
    """
    user = request.user
    qs = espacios_del_usuario(user)
    espacio_id = request.session.get('espacio_id')

    if espacio_id:
        espacio = qs.filter(pk=espacio_id).first()
        if espacio:
            return espacio

    espacio = qs.first()
    if not espacio:
        espacio = Espacio.objects.create(
            nombre="Mi Espacio Principal",
            administrador=user,
        )

    request.session['espacio_id'] = espacio.id
    return espacio


def usuario_puede_acceder_espacio(user, espacio):
    if not espacio:
        return False
    if espacio.administrador_id == user.id:
        return True
    return espacio.miembros.filter(pk=user.pk).exists()
