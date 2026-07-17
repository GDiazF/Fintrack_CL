import os
import time
import json
import hmac
import hashlib
import requests
import django

# 1. Configurar el entorno de Django para consultar las claves directamente de la base de datos
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fintrack_main.settings')
django.setup()

from core.models import PerfilUsuario

def simular_envio():
    # Obtener las credenciales del primer usuario (admin)
    perfil = PerfilUsuario.objects.first()
    if not perfil:
        print("Error: No se encontró ningún perfil de usuario en la base de datos.")
        return

    api_key_id = perfil.api_key_id
    api_secret_token = perfil.api_secret_token

    print(f"Usando API Key ID: {api_key_id}")
    
    # URL del servidor local (puerto 8080)
    url = "http://127.0.0.1:8080/api/v1/conectores/ingesta/"

    # Payload de prueba (Ejemplo de correo de compra BancoEstado)
    payload = {
        "conector": "gmail_bancoestado_v1",
        "gmail_message_id": f"msg_mock_{int(time.time())}",
        "fecha_correo": "2026-07-17T19:00:00Z",
        "raw_text": "BancoEstado: Hola Diego, confirmamos tu compra por un monto de $7.490 en COPEC S.A. con tu tarjeta *1234 el 17/07/2026."
    }

    payload_str = json.dumps(payload)
    timestamp = str(int(time.time()))
    nonce = f"nonce_{int(time.time())}"

    # Calcular la firma criptográfica HMAC-SHA256
    message_to_sign = payload_str.encode('utf-8') + timestamp.encode('utf-8') + nonce.encode('utf-8')
    signature = hmac.new(
        api_secret_token.encode('utf-8'),
        message_to_sign,
        hashlib.sha256
    ).hexdigest()

    # Encabezados de seguridad requeridos por el middleware de Fintrack CL
    headers = {
        "X-Key-ID": api_key_id,
        "X-Signature": signature,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "Content-Type": "application/json"
    }

    print("\nEnviando petición POST simulada...")
    try:
        response = requests.post(url, data=payload_str, headers=headers)
        print(f"Código de respuesta: {response.status_code}")
        print("Respuesta del servidor:")
        print(json.dumps(response.json(), indent=4, ensure_ascii=False))
    except Exception as e:
        print(f"Error al conectar con el servidor: {e}")

if __name__ == "__main__":
    simular_envio()
