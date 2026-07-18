from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_alias_comercio'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilusuario',
            name='email_verificado',
            field=models.BooleanField(
                default=True,
                help_text='False tras registro hasta que confirme el enlace del correo. Usuarios existentes/admin quedan en True.',
            ),
        ),
    ]
