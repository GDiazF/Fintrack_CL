from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Usuario, PerfilUsuario, Espacio


@receiver(post_save, sender=Usuario)
def crear_perfil_y_espacio(sender, instance, created, **kwargs):
    """Al registrar un usuario, crea PerfilUsuario y un Espacio principal."""
    if not created:
        return
    PerfilUsuario.objects.get_or_create(user=instance)
    if not Espacio.objects.filter(administrador=instance).exists():
        Espacio.objects.create(
            nombre='Mi Espacio Principal',
            administrador=instance,
        )
