"""
Seed de categorías globales típicas para el contexto chileno.

Uso:
  python manage.py seed_categorias_chile
"""

from django.core.management.base import BaseCommand

from core.models import Categoria

CATEGORIAS_CHILE = [
    ('Supermercado', '#10b981', 'bi-cart3'),
    ('Transporte', '#3b82f6', 'bi-bus-front'),
    ('Combustible', '#f59e0b', 'bi-fuel-pump'),
    ('Restaurantes', '#ef4444', 'bi-cup-hot'),
    ('Salud', '#ec4899', 'bi-heart-pulse'),
    ('Educación', '#8b5cf6', 'bi-book'),
    ('Vivienda', '#64748b', 'bi-house'),
    ('Servicios', '#0d9488', 'bi-lightning'),
    ('Entretenimiento', '#a855f7', 'bi-controller'),
    ('Suscripciones', '#06b6d4', 'bi-phone'),
    ('Transferencias', '#94a3b8', 'bi-arrow-left-right'),
    ('Otros', '#475569', 'bi-three-dots'),
]


class Command(BaseCommand):
    help = 'Crea categorías globales (espacio=null) para Chile si no existen'

    def handle(self, *args, **options):
        creadas = 0
        for nombre, color, icono in CATEGORIAS_CHILE:
            _, created = Categoria.objects.get_or_create(
                espacio=None,
                nombre=nombre,
                defaults={'color_hex': color, 'icono': icono},
            )
            if created:
                creadas += 1
                self.stdout.write(self.style.SUCCESS(f'  + {nombre}'))
            else:
                self.stdout.write(f'  · {nombre} (ya existía)')

        self.stdout.write(self.style.SUCCESS(
            f'Listo. {creadas} categorías nuevas; {len(CATEGORIAS_CHILE) - creadas} existentes.'
        ))
