import hmac
import hashlib
import time
import json
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from core.models import Usuario, PerfilUsuario, Movimiento, Moneda

class WebhookIngestaTestCase(TestCase):
    def setUp(self):
        # 1. Crear usuario de prueba
        self.user = Usuario.objects.create_user(
            username='diego_test',
            email='diego@test.cl',
            password='testpassword123'
        )
        # 2. Perfil se crea de forma automática en el modelo, pero recuperamos su API Key y Secret
        self.perfil = PerfilUsuario.objects.create(user=self.user)
        self.api_key = self.perfil.api_key_id
        self.api_secret = self.perfil.api_secret_token
        
        # 3. Registrar moneda base CLP
        self.moneda_clp = Moneda.objects.create(codigo_iso='CLP', simbolo='$', decimales=0)

        # 4. Datos de prueba del webhook
        self.payload = {
            "conector": "gmail_bancoestado_v1",
            "gmail_message_id": "msg_ch17072026_xyz999",
            "fecha_correo": "2026-07-17T18:32:00Z",
            "raw_text": "BancoEstado: Hola Diego, confirmamos tu compra por un monto de $4.990 en CAFETERIA IQUIQUE con tu tarjeta *5678 el 17/07/2026."
        }
        self.url = reverse('api_ingesta')

    def _generate_headers(self, payload_dict, secret, timestamp=None, nonce="random_nonce_123"):
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
            'HTTP_X_KEY_ID': self.api_key,
            'HTTP_X_SIGNATURE': signature,
            'HTTP_X_TIMESTAMP': timestamp,
            'HTTP_X_NONCE': nonce,
            'content_type': 'application/json'
        }

    def test_ingesta_exitosa(self):
        """Prueba que un webhook con firma válida se procese correctamente."""
        headers = self._generate_headers(self.payload, self.api_secret)
        response = self.client.post(self.url, data=self.payload, format='json', **headers)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['monto'], 4990)
        self.assertEqual(response.data['comercio'], 'CAFETERIA IQUIQUE')
        
        # Verificar que el movimiento se guardó
        self.assertTrue(Movimiento.objects.filter(gmail_message_id="msg_ch17072026_xyz999").exists())

    def test_firma_invalida(self):
        """Prueba que un webhook con una firma incorrecta sea rechazado."""
        headers = self._generate_headers(self.payload, "un_secret_incorrecto")
        response = self.client.post(self.url, data=self.payload, format='json', **headers)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN) # DRF AuthenticationFailed mapea a 403 o 401 según el caso
        self.assertIn('Firma inválida', response.data['detail'])

    def test_anti_replay_attack(self):
        """Prueba que una firma con un timestamp antiguo sea rechazada (anti-replay)."""
        # Timestamp de hace 10 minutos (600 segundos)
        antiguo_timestamp = str(int(time.time()) - 600)
        headers = self._generate_headers(self.payload, self.api_secret, timestamp=antiguo_timestamp)
        response = self.client.post(self.url, data=self.payload, format='json', **headers)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Petición expirada', response.data['detail'])

    def test_idempotencia_absoluta(self):
        """Prueba que enviar el mismo mensaje dos veces no duplique registros (HTTP 201 primero, HTTP 200 después)."""
        # Primera petición
        headers1 = self._generate_headers(self.payload, self.api_secret)
        response1 = self.client.post(self.url, data=self.payload, format='json', **headers1)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Movimiento.objects.filter(gmail_message_id="msg_ch17072026_xyz999").count(), 1)

        # Segunda petición (mismo gmail_message_id)
        # Generamos nuevos encabezados porque el timestamp avanzó ligeramente o usamos un nuevo nonce
        headers2 = self._generate_headers(self.payload, self.api_secret, nonce="different_nonce")
        response2 = self.client.post(self.url, data=self.payload, format='json', **headers2)
        
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data['detail'], 'Mensaje duplicado procesado anteriormente')
        
        # Confirmar que sigue existiendo exactamente 1 registro
        self.assertEqual(Movimiento.objects.filter(gmail_message_id="msg_ch17072026_xyz999").count(), 1)
