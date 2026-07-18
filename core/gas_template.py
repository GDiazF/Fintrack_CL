"""Plantilla completa de Google Apps Script para onboarding (Fase C)."""


def build_gas_script(*, api_key_id, api_secret, endpoint_url):
    """Devuelve el script GAS listo para pegar, con credenciales inyectadas."""
    return f'''/**
 * Fintrack CL — Cliente de captura Gmail (mensajero).
 * Trigger recomendado: cada 10 minutos.
 * No parsea correos: solo envía el texto crudo al backend.
 */
var API_KEY_ID = "{api_key_id}";
var API_SECRET = "{api_secret}";
var ENDPOINT_URL = "{endpoint_url}";
var ETIQUETA_PROCESADO = "fintrack-procesado";

function enviarCorreosAlServidor() {{
  var etiqueta = GmailApp.getUserLabelByName(ETIQUETA_PROCESADO) || GmailApp.createLabel(ETIQUETA_PROCESADO);
  var query = "(from:bancoestado.cl OR from:santander.cl OR from:bci.cl) -label:" + ETIQUETA_PROCESADO;
  var hilos = GmailApp.search(query, 0, 15);

  for (var i = 0; i < hilos.length; i++) {{
    var mensajes = hilos[i].getMessages();
    for (var j = 0; j < mensajes.length; j++) {{
      var mensaje = mensajes[j];
      var etiquetasActuales = hilos[i].getLabels();
      var revisado = etiquetasActuales.some(function(l) {{
        return l.getName() === ETIQUETA_PROCESADO;
      }});

      if (!revisado) {{
        var remitente = mensaje.getFrom();
        var conectorId = "gmail_bancoestado_v1";
        if (remitente.indexOf("santander.cl") !== -1) conectorId = "gmail_santander_v1";
        if (remitente.indexOf("bci.cl") !== -1) conectorId = "gmail_bci_v1";

        var payloadObj = {{
          "conector": conectorId,
          "gmail_message_id": mensaje.getId(),
          "fecha_correo": mensaje.getDate().toISOString(),
          "raw_text": mensaje.getPlainBody()
        }};

        var payloadStr = JSON.stringify(payloadObj);
        var timestamp = Math.floor(Date.now() / 1000).toString();
        var nonce = Math.random().toString(36).substring(2, 12);
        var stringParaFirmar = payloadStr + timestamp + nonce;
        var firmaBytes = Utilities.computeHmacSignature(
          Utilities.MacAlgorithm.HMAC_SHA_256,
          stringParaFirmar,
          API_SECRET
        );
        var firmaHex = firmaBytes.map(function(byte) {{
          return ("0" + (byte & 0xFF).toString(16)).slice(-2);
        }}).join("");

        var opciones = {{
          "method": "post",
          "contentType": "application/json",
          "headers": {{
            "X-Key-ID": API_KEY_ID,
            "X-Signature": firmaHex,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce
          }},
          "payload": payloadStr,
          "muteHttpExceptions": true
        }};

        try {{
          var respuesta = UrlFetchApp.fetch(ENDPOINT_URL, opciones);
          var codigoEstado = respuesta.getResponseCode();
          if (codigoEstado === 200 || codigoEstado === 201) {{
            hilos[i].addLabel(etiqueta);
          }} else {{
            Logger.log("Fintrack HTTP " + codigoEstado + ": " + respuesta.getContentText());
          }}
        }} catch (error) {{
          Logger.log("Fallo de red Fintrack: " + error.toString());
        }}
      }}
    }}
  }}
}}
'''
