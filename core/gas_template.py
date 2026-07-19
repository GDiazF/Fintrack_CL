"""Plantilla completa de Google Apps Script para onboarding (Fase C)."""


def build_gas_script(*, api_key_id, api_secret, endpoint_url):
    """Devuelve el script GAS listo para pegar, con credenciales inyectadas."""
    # Escapar por si el secreto/url tuvieran comillas (token_urlsafe no las trae, pero por seguridad)
    api_key_id = api_key_id.replace('\\', '\\\\').replace('"', '\\"')
    api_secret = api_secret.replace('\\', '\\\\').replace('"', '\\"')
    endpoint_url = endpoint_url.replace('\\', '\\\\').replace('"', '\\"')

    return f'''/**
 * Fintrack CL — Cliente Gmail (mensajero).
 * Trigger: cada 10 minutos → enviarCorreosAlServidor
 */
var API_KEY_ID = "{api_key_id}";
var API_SECRET = "{api_secret}";
var ENDPOINT_URL = "{endpoint_url}";
var ETIQUETA_PROCESADO = "fintrack-procesado";

function _hexFromBytes(firmaBytes) {{
  return firmaBytes.map(function(byte) {{
    return ("0" + (byte & 0xFF).toString(16)).slice(-2);
  }}).join("");
}}

/** Firma HMAC-SHA256 sobre los bytes UTF-8 exactos (igual que el backend Django). */
function _firmar(payloadStr, timestamp, nonce) {{
  var stringParaFirmar = payloadStr + timestamp + nonce;
  var msgBytes = Utilities.newBlob(stringParaFirmar).getBytes();
  var keyBytes = Utilities.newBlob(API_SECRET).getBytes();
  var firmaBytes = Utilities.computeHmacSha256Signature(msgBytes, keyBytes);
  return _hexFromBytes(firmaBytes);
}}

function _postFintrack(payloadObj) {{
  var payloadStr = JSON.stringify(payloadObj);
  var timestamp = Math.floor(Date.now() / 1000).toString();
  var nonce = Utilities.getUuid().replace(/-/g, "").substring(0, 16);
  var firmaHex = _firmar(payloadStr, timestamp, nonce);

  var opciones = {{
    method: "post",
    headers: {{
      "Content-Type": "application/json; charset=utf-8",
      "X-Key-ID": API_KEY_ID,
      "X-Signature": firmaHex,
      "X-Timestamp": timestamp,
      "X-Nonce": nonce
    }},
    payload: Utilities.newBlob(payloadStr).getBytes(),
    muteHttpExceptions: true
  }};

  return UrlFetchApp.fetch(ENDPOINT_URL, opciones);
}}

/** Prueba rápida de firma (sin Gmail). Ejecuta esta función primero. */
function probarConexionFintrack() {{
  if (!API_SECRET || API_SECRET.indexOf("REEMPLAZA") === 0) {{
    Logger.log("API_SECRET inválido. Genera script nuevo en Onboarding.");
    return;
  }}
  // Payload FIJO (mismo string que en el diagnóstico del servidor)
  var payloadStr = '{{"conector":"gmail_bancoestado_v1","gmail_message_id":"gas_probe_1","fecha_correo":"2026-07-18T12:00:00.000Z","raw_text":"hola fintrack"}}';
  var timestamp = Math.floor(Date.now() / 1000).toString();
  var nonce = "probe" + Utilities.getUuid().replace(/-/g, "").substring(0, 8);
  var firmaHex = _firmar(payloadStr, timestamp, nonce);

  Logger.log("KEY_ID=" + API_KEY_ID);
  Logger.log("SECRET_PREFIX=" + API_SECRET.substring(0, 12));
  Logger.log("BODY=" + payloadStr);
  Logger.log("TS=" + timestamp + " NONCE=" + nonce);
  Logger.log("SIG=" + firmaHex);

  var opciones = {{
    method: "post",
    headers: {{
      "Content-Type": "application/json; charset=utf-8",
      "X-Key-ID": API_KEY_ID,
      "X-Signature": firmaHex,
      "X-Timestamp": timestamp,
      "X-Nonce": nonce
    }},
    payload: Utilities.newBlob(payloadStr).getBytes(),
    muteHttpExceptions: true
  }};
  var resp = UrlFetchApp.fetch(ENDPOINT_URL, opciones);
  Logger.log("HTTP " + resp.getResponseCode() + ": " + resp.getContentText());
}}

function enviarCorreosAlServidor() {{
  if (!API_SECRET || API_SECRET.indexOf("REEMPLAZA") === 0) {{
    Logger.log("Fintrack: API_SECRET inválido. Onboarding → Generar script nuevo.");
    return;
  }}

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
          conector: conectorId,
          gmail_message_id: mensaje.getId(),
          fecha_correo: mensaje.getDate().toISOString(),
          raw_text: mensaje.getPlainBody()
        }};

        try {{
          var respuesta = _postFintrack(payloadObj);
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
