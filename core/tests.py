import hmac
import hashlib
import time
import json
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from core.models import (
    Usuario, PerfilUsuario, Movimiento, Moneda, Espacio, WebhookNonce,
    IngestaFallida, Categoria, ReglaCategoria,
)
from core.categorizacion import resolver_categoria_por_reglas
from core.parsers.factory import ParserFactory, BancoEstadoParserV1
from core.parsers.corpus_bancoestado import (
    BE_COMPRA, BE_COMPRA_COPEC, BE_TRANSFERENCIA, BE_INGRESO, BE_SIN_MONTO,
)


class WebhookIngestaTestCase(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            username='diego_test',
            email='diego@test.cl',
            password='testpassword123'
        )
        self.perfil = self.user.perfil
        self.api_key = self.perfil.api_key_id
        self.api_secret = self.perfil.api_secret_token

        self.moneda_clp = Moneda.objects.create(codigo_iso='CLP', simbolo='$', decimales=0)

        self.payload = {
            "conector": "gmail_bancoestado_v1",
            "gmail_message_id": "msg_ch17072026_xyz999",
            "fecha_correo": "2026-07-17T18:32:00Z",
            "raw_text": BE_COMPRA,
        }
        self.url = reverse('api_ingesta')

    def _generate_headers(self, payload_dict, secret, timestamp=None, nonce="random_nonce_123", api_key=None):
        payload_str = json.dumps(payload_dict)
        if timestamp is None:
            timestamp = str(int(time.time()))

        message_to_sign = payload_str.encode('utf-8') + timestamp.encode('utf-8') + nonce.encode('utf-8')
        signature = hmac.new(
            secret.encode('utf-8'),
            message_to_sign,
            hashlib.sha256
        ).hexdigest()

        return {
            'HTTP_X_KEY_ID': api_key or self.api_key,
            'HTTP_X_SIGNATURE': signature,
            'HTTP_X_TIMESTAMP': timestamp,
            'HTTP_X_NONCE': nonce,
            'content_type': 'application/json',
        }

    def test_ingesta_exitosa(self):
        headers = self._generate_headers(self.payload, self.api_secret, nonce="nonce_exito_001")
        response = self.client.post(self.url, data=self.payload, format='json', **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['monto'], 4990)
        self.assertEqual(response.data['comercio'], 'CAFETERIA IQUIQUE')
        self.assertTrue(Movimiento.objects.filter(gmail_message_id="msg_ch17072026_xyz999").exists())
        self.assertTrue(
            WebhookNonce.objects.filter(perfil=self.perfil, nonce="nonce_exito_001").exists()
        )

    def test_firma_invalida(self):
        headers = self._generate_headers(self.payload, "un_secret_incorrecto", nonce="nonce_firma_bad")
        response = self.client.post(self.url, data=self.payload, format='json', **headers)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Firma inválida', response.data['detail'])

    def test_anti_replay_attack(self):
        antiguo_timestamp = str(int(time.time()) - 600)
        headers = self._generate_headers(
            self.payload, self.api_secret, timestamp=antiguo_timestamp, nonce="nonce_viejo"
        )
        response = self.client.post(self.url, data=self.payload, format='json', **headers)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Petición expirada', response.data['detail'])

    def test_nonce_reutilizado_rechazado(self):
        nonce = "nonce_replay_unico"
        headers1 = self._generate_headers(self.payload, self.api_secret, nonce=nonce)
        response1 = self.client.post(self.url, data=self.payload, format='json', **headers1)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        payload2 = {**self.payload, "gmail_message_id": "msg_otro_mensaje_002"}
        headers2 = self._generate_headers(payload2, self.api_secret, nonce=nonce)
        response2 = self.client.post(self.url, data=payload2, format='json', **headers2)

        self.assertEqual(response2.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Nonce reutilizado', response2.data['detail'])
        self.assertEqual(Movimiento.objects.count(), 1)

    def test_idempotencia_absoluta(self):
        headers1 = self._generate_headers(self.payload, self.api_secret, nonce="nonce_idem_1")
        response1 = self.client.post(self.url, data=self.payload, format='json', **headers1)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Movimiento.objects.filter(gmail_message_id="msg_ch17072026_xyz999").count(), 1)

        headers2 = self._generate_headers(self.payload, self.api_secret, nonce="nonce_idem_2")
        response2 = self.client.post(self.url, data=self.payload, format='json', **headers2)

        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data['detail'], 'Mensaje duplicado procesado anteriormente')
        self.assertEqual(Movimiento.objects.filter(gmail_message_id="msg_ch17072026_xyz999").count(), 1)

    def test_aislamiento_usuario_a_vs_b(self):
        user_b = Usuario.objects.create_user(
            username='usuario_b',
            email='b@test.cl',
            password='testpassword123',
        )
        perfil_b = user_b.perfil
        espacio_b = Espacio.objects.filter(administrador=user_b).first()
        if not espacio_b:
            espacio_b = Espacio.objects.create(nombre="Espacio de B", administrador=user_b)

        headers_a = self._generate_headers(self.payload, self.api_secret, nonce="nonce_aislamiento_a")
        response_a = self.client.post(self.url, data=self.payload, format='json', **headers_a)
        self.assertEqual(response_a.status_code, status.HTTP_201_CREATED)

        movimiento = Movimiento.objects.get(gmail_message_id="msg_ch17072026_xyz999")
        self.assertEqual(movimiento.cuenta.espacio.administrador, self.user)
        self.assertNotEqual(movimiento.cuenta.espacio_id, espacio_b.id)

        headers_cruzados = self._generate_headers(
            {**self.payload, "gmail_message_id": "msg_cruzado"},
            perfil_b.api_secret_token,
            nonce="nonce_cruzado",
            api_key=self.api_key,
        )
        response_cruzado = self.client.post(
            self.url,
            data={**self.payload, "gmail_message_id": "msg_cruzado"},
            format='json',
            **headers_cruzados,
        )
        self.assertEqual(response_cruzado.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Movimiento.objects.filter(gmail_message_id="msg_cruzado").exists())

    def test_ingesta_fallida_sin_monto(self):
        """Mails no parseables se registran como IngestaFallida y responden 200."""
        payload = {
            "conector": "gmail_bancoestado_v1",
            "gmail_message_id": "msg_sin_monto_001",
            "fecha_correo": "2026-07-17T18:32:00Z",
            "raw_text": BE_SIN_MONTO,
        }
        headers = self._generate_headers(payload, self.api_secret, nonce="nonce_falla_001")
        response = self.client.post(self.url, data=payload, format='json', **headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'failed_logged')
        self.assertTrue(IngestaFallida.objects.filter(gmail_message_id="msg_sin_monto_001").exists())
        self.assertEqual(Movimiento.objects.count(), 0)

        # Reenvío idempotente de la misma falla
        headers2 = self._generate_headers(payload, self.api_secret, nonce="nonce_falla_002")
        response2 = self.client.post(self.url, data=payload, format='json', **headers2)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(IngestaFallida.objects.filter(gmail_message_id="msg_sin_monto_001").count(), 1)

    def test_regla_categoria_substring_en_ingesta(self):
        """Regla 'COPEC' categoriza 'COPEC S.A.' vía substring."""
        espacio = Espacio.objects.filter(administrador=self.user).first()
        self.assertIsNotNone(espacio)
        categoria = Categoria.objects.create(espacio=espacio, nombre="Combustible")
        ReglaCategoria.objects.create(
            espacio=espacio,
            patron_texto="COPEC",
            categoria_destino=categoria,
        )

        payload = {
            "conector": "gmail_bancoestado_v1",
            "gmail_message_id": "msg_copec_regla",
            "fecha_correo": "2026-07-17T19:00:00Z",
            "raw_text": BE_COMPRA_COPEC,
        }
        headers = self._generate_headers(payload, self.api_secret, nonce="nonce_regla_copec")
        response = self.client.post(self.url, data=payload, format='json', **headers)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mov = Movimiento.objects.get(gmail_message_id="msg_copec_regla")
        self.assertEqual(mov.categoria_id, categoria.id)


class CategorizacionTestCase(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(username='cat_user', password='x')
        self.espacio = Espacio.objects.create(nombre="Espacio Cat", administrador=self.user)
        self.cat_combustible = Categoria.objects.create(espacio=self.espacio, nombre="Combustible")
        self.cat_cafe = Categoria.objects.create(espacio=self.espacio, nombre="Café")
        ReglaCategoria.objects.create(
            espacio=self.espacio, patron_texto="COPEC", categoria_destino=self.cat_combustible
        )
        ReglaCategoria.objects.create(
            espacio=self.espacio, patron_texto="STARBUCKS", categoria_destino=self.cat_cafe
        )

    def test_substring_match(self):
        cat = resolver_categoria_por_reglas(self.espacio, "COPEC S.A. IQUIQUE")
        self.assertEqual(cat, self.cat_combustible)

    def test_prioridad_patron_mas_largo(self):
        cat_express = Categoria.objects.create(espacio=self.espacio, nombre="Copecexpress")
        ReglaCategoria.objects.create(
            espacio=self.espacio, patron_texto="COPEC EXPRESS", categoria_destino=cat_express
        )
        cat = resolver_categoria_por_reglas(self.espacio, "Tienda COPEC EXPRESS 12")
        self.assertEqual(cat, cat_express)

    def test_sin_match(self):
        self.assertIsNone(resolver_categoria_por_reglas(self.espacio, "LIDER IQUIQUE"))


class BancoEstadoParserTestCase(TestCase):
    def setUp(self):
        self.parser = BancoEstadoParserV1()

    def test_parse_compra(self):
        data = self.parser.parsear(BE_COMPRA)
        self.assertEqual(data['tipo'], 'EGRESO')
        self.assertEqual(data['monto'], 4990)
        self.assertEqual(data['comercio_raw'], 'CAFETERIA IQUIQUE')
        self.assertEqual(data['identificador_tarjeta'], '5678')

    def test_parse_transferencia(self):
        data = self.parser.parsear(BE_TRANSFERENCIA)
        self.assertEqual(data['tipo'], 'TRANSFERENCIA')
        self.assertEqual(data['monto'], 50000)
        self.assertIn('MARIA', data['comercio_raw'].upper())

    def test_parse_ingreso(self):
        data = self.parser.parsear(BE_INGRESO)
        self.assertEqual(data['tipo'], 'INGRESO')
        self.assertEqual(data['monto'], 850000)
        self.assertIn('EMPRESA', data['comercio_raw'].upper())

    def test_factory_resuelve_conector(self):
        self.assertIsInstance(ParserFactory.get('gmail_bancoestado_v1'), BancoEstadoParserV1)
        self.assertIsNone(ParserFactory.get('gmail_desconocido_v9'))

    def test_sin_monto_retorna_none(self):
        data = self.parser.parsear(BE_SIN_MONTO)
        self.assertIsNone(data['monto'])


class OrganizacionFaseBTestCase(TestCase):
    """UI/API mínima de Fase B: categorías, reglas, re-categorizar, seed."""

    def setUp(self):
        self.user = Usuario.objects.create_user(username='faseb', password='pass12345')
        self.client.login(username='faseb', password='pass12345')
        self.espacio = Espacio.objects.create(nombre='Espacio B', administrador=self.user)
        session = self.client.session
        session['espacio_id'] = self.espacio.id
        session.save()

    def test_crear_categoria_htmx(self):
        response = self.client.post('/organizacion/categorias/crear/', {
            'nombre': 'Combustible',
            'color_hex': '#f59e0b',
            'icono': 'bi-fuel-pump',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Categoria.objects.filter(espacio=self.espacio, nombre='Combustible').exists()
        )

    def test_crear_regla(self):
        cat = Categoria.objects.create(espacio=self.espacio, nombre='Combustible')
        response = self.client.post('/organizacion/reglas/crear/', {
            'patron_texto': 'copec',
            'categoria_id': cat.id,
        })
        self.assertEqual(response.status_code, 200)
        regla = ReglaCategoria.objects.get(espacio=self.espacio)
        self.assertEqual(regla.patron_texto, 'COPEC')

    def test_recategorizar_movimiento(self):
        from core.models import InstitucionFinanciera, CuentaFinanciera, Moneda
        inst = InstitucionFinanciera.objects.create(nombre='BancoEstado')
        cuenta = CuentaFinanciera.objects.create(
            espacio=self.espacio, institucion=inst, nombre='CuentaRUT', es_predeterminada=True
        )
        moneda = Moneda.objects.create(codigo_iso='CLP', simbolo='$')
        mov = Movimiento.objects.create(
            cuenta=cuenta,
            comercio_raw='COPEC S.A.',
            fecha_transaccion='2026-07-18T12:00:00Z',
            monto_original=1000,
            moneda_original=moneda,
            monto_clp=1000,
            tipo='EGRESO',
            gmail_message_id='msg_recat_001',
        )
        cat = Categoria.objects.create(espacio=self.espacio, nombre='Combustible')
        response = self.client.post(f'/movimientos/{mov.id}/categoria/', {
            'categoria_id': cat.id,
        })
        self.assertEqual(response.status_code, 200)
        mov.refresh_from_db()
        self.assertEqual(mov.categoria_id, cat.id)

    def test_seed_categorias_chile(self):
        from django.core.management import call_command
        call_command('seed_categorias_chile')
        self.assertGreaterEqual(
            Categoria.objects.filter(espacio__isnull=True).count(), 12
        )
        call_command('seed_categorias_chile')  # idempotente
        self.assertEqual(Categoria.objects.filter(espacio__isnull=True).count(), 12)


class FaseCOnboardingTestCase(TestCase):
    def test_registro_crea_perfil_y_espacio(self):
        response = self.client.post('/registro/', {
            'username': 'nuevo_user',
            'email': 'nuevo@test.cl',
            'password1': 'ClaveSegura123!',
            'password2': 'ClaveSegura123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/registro/pendiente/', response.url)
        user = Usuario.objects.get(username='nuevo_user')
        self.assertTrue(hasattr(user, 'perfil'))
        self.assertTrue(Espacio.objects.filter(administrador=user).exists())
        self.assertFalse(user.perfil.secret_revelado)
        self.assertFalse(user.perfil.email_verificado)

    def test_confirmar_y_rotar_secreto(self):
        user = Usuario.objects.create_user(username='sec', password='ClaveSegura123!')
        self.client.login(username='sec', password='ClaveSegura123!')
        perfil = user.perfil
        old = perfil.api_secret_token
        self.assertFalse(perfil.secret_revelado)

        r1 = self.client.post('/perfil/confirmar-secreto/')
        self.assertEqual(r1.status_code, 302)
        self.assertIn('/onboarding/', r1.url)
        perfil.refresh_from_db()
        self.assertTrue(perfil.secret_revelado)

        r2 = self.client.post('/perfil/rotar-secreto/')
        self.assertEqual(r2.status_code, 302)
        self.assertIn('/onboarding/', r2.url)
        perfil.refresh_from_db()
        self.assertFalse(perfil.secret_revelado)
        self.assertNotEqual(perfil.api_secret_token, old)

    def test_fallida_resolver(self):
        user = Usuario.objects.create_user(username='fail', password='ClaveSegura123!')
        self.client.login(username='fail', password='ClaveSegura123!')
        falla = IngestaFallida.objects.create(
            usuario=user,
            gmail_message_id='msg_fail_ui',
            conector='gmail_bancoestado_v1',
            raw_text='sin monto',
            motivo_error='No se pudo extraer un monto',
        )
        response = self.client.post(f'/fallidas/{falla.id}/resolver/')
        self.assertEqual(response.status_code, 302)
        falla.refresh_from_db()
        self.assertTrue(falla.resuelto)


class FaseEParsersNormalizacionTestCase(TestCase):
    def test_santander_compra(self):
        from core.parsers.factory import SantanderParserV1
        from core.parsers.corpus_santander import SA_COMPRA
        data = SantanderParserV1().parsear(SA_COMPRA)
        self.assertEqual(data['tipo'], 'EGRESO')
        self.assertEqual(data['monto'], 12990)
        self.assertIn('LIDER', data['comercio_raw'].upper())

    def test_bci_compra_y_factory(self):
        from core.parsers.factory import BciParserV1, ParserFactory
        from core.parsers.corpus_bci import BCI_COMPRA, BCI_ABONO
        compra = BciParserV1().parsear(BCI_COMPRA)
        self.assertEqual(compra['monto'], 15990)
        self.assertEqual(compra['tipo'], 'EGRESO')
        abono = BciParserV1().parsear(BCI_ABONO)
        self.assertEqual(abono['tipo'], 'INGRESO')
        self.assertEqual(abono['monto'], 120000)
        self.assertIsNotNone(ParserFactory.get('gmail_bci_v1'))

    def test_normalizacion_lider(self):
        from core.normalizacion import resolver_comercio, nombre_canonico_sugerido
        self.assertEqual(nombre_canonico_sugerido('LIDER IQUIQUE'), 'Líder')
        c1 = resolver_comercio('LIDER IQUIQUE')
        c2 = resolver_comercio('LIDER ANTOFAGASTA')
        self.assertEqual(c1.id, c2.id)
        self.assertEqual(c1.nombre_fantasia, 'Líder')

    def test_export_csv(self):
        user = Usuario.objects.create_user(username='csvuser', password='ClaveSegura123!')
        self.client.login(username='csvuser', password='ClaveSegura123!')
        response = self.client.get('/export/csv/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])


class EmailAuthTests(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            username='mailuser',
            email='mailuser@example.com',
            password='ClaveSegura123!',
        )
        self.perfil = PerfilUsuario.objects.get(user=self.user)

    def test_login_bloquea_sin_verificar(self):
        self.perfil.email_verificado = False
        self.perfil.save(update_fields=['email_verificado'])
        response = self.client.post('/login/', {
            'username': 'mailuser',
            'password': 'ClaveSegura123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'verificar tu email')
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_registro_envia_mail_y_no_loguea(self):
        from django.core import mail
        response = self.client.post('/registro/', {
            'username': 'nuevo',
            'email': 'nuevo@example.com',
            'password1': 'ClaveSegura123!',
            'password2': 'ClaveSegura123!',
        })
        self.assertRedirects(response, '/registro/pendiente/')
        self.assertEqual(len(mail.outbox), 1)
        user = Usuario.objects.get(username='nuevo')
        self.assertFalse(user.perfil.email_verificado)

    def test_verificar_activa_cuenta(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        self.perfil.email_verificado = False
        self.perfil.save(update_fields=['email_verificado'])
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        response = self.client.get(f'/verificar/{uid}/{token}/')
        self.assertRedirects(response, '/onboarding/')
        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.email_verificado)

    def test_password_reset_envia_mail(self):
        from django.core import mail
        response = self.client.post('/password-reset/', {'email': 'mailuser@example.com'})
        self.assertRedirects(response, '/password-reset/done/')
        self.assertEqual(len(mail.outbox), 1)
