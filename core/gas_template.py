"""Plantilla completa de Google Apps Script para onboarding (Fase C)."""


def build_gas_script(*, api_key_id, api_secret, endpoint_url):
    """Devuelve el script GAS listo para pegar, con credenciales inyectadas."""
    api_key_id = api_key_id.replace('\\', '\\\\').replace('"', '\\"')
    api_secret = api_secret.replace('\\', '\\\\').replace('"', '\\"')
    endpoint_url = endpoint_url.replace('\\', '\\\\').replace('"', '\\"')

    return f'''/**
 * Fintrack CL — Cliente Gmail
 * El JSON del mail se envía en Base64 (ASCII) para que la firma HMAC no se rompa con acentos.
 * 1) probarConexionFintrack  2) activador → enviarCorreosAlServidor
 */
var API_KEY_ID = "{api_key_id}";
var API_SECRET = "{api_secret}";
var ENDPOINT_URL = "{endpoint_url}";
var ETIQUETA_PROCESADO = "fintrack-procesado";

function _firmar(payloadStr, timestamp, nonce) {{
  var firmaBytes = Utilities.computeHmacSha256Signature(payloadStr + timestamp + nonce, API_SECRET);
  return Utilities.base64Encode(firmaBytes);
}}

/** payloadObj → JSON → Base64 → firmar/enviar (solo ASCII en el wire). */
function _postFintrack(payloadObj) {{
  var json = JSON.stringify(payloadObj);
  var payloadStr = Utilities.base64Encode(Utilities.newBlob(json).getBytes());
  var timestamp = Math.floor(Date.now() / 1000).toString();
  var nonce = Utilities.getUuid().replace(/-/g, "").substring(0, 16);
  return UrlFetchApp.fetch(ENDPOINT_URL, {{
    method: "post",
    contentType: "text/plain; charset=utf-8",
    headers: {{
      "X-Key-ID": API_KEY_ID,
      "X-Signature": _firmar(payloadStr, timestamp, nonce),
      "X-Timestamp": timestamp,
      "X-Nonce": nonce
    }},
    payload: payloadStr,
    muteHttpExceptions: true
  }});
}}

function probarConexionFintrack() {{
  var resp = _postFintrack({{
    conector: "gmail_bancoestado_v1",
    gmail_message_id: "gas_probe_" + Date.now(),
    fecha_correo: "2026-07-18T12:00:00.000Z",
    raw_text: "BancoEstado: compra de prueba por $1.590 en COPEC el 18/07/2026."
  }});
  Logger.log("HTTP " + resp.getResponseCode() + ": " + resp.getContentText());
}}

function enviarCorreosAlServidor() {{
  var etiqueta = GmailApp.getUserLabelByName(ETIQUETA_PROCESADO) || GmailApp.createLabel(ETIQUETA_PROCESADO);
  var hilos = GmailApp.search("(from:bancoestado.cl OR from:santander.cl OR from:bci.cl) -label:" + ETIQUETA_PROCESADO, 0, 15);
  Logger.log("Hilos encontrados: " + hilos.length);
  for (var i = 0; i < hilos.length; i++) {{
    var mensajes = hilos[i].getMessages();
    for (var j = 0; j < mensajes.length; j++) {{
      var mensaje = mensajes[j];
      if (hilos[i].getLabels().some(function(l) {{ return l.getName() === ETIQUETA_PROCESADO; }})) continue;
      var remitente = mensaje.getFrom();
      var conectorId = "gmail_bancoestado_v1";
      if (remitente.indexOf("santander.cl") !== -1) conectorId = "gmail_santander_v1";
      if (remitente.indexOf("bci.cl") !== -1) conectorId = "gmail_bci_v1";
      var r = _postFintrack({{
        conector: conectorId,
        gmail_message_id: mensaje.getId(),
        fecha_correo: mensaje.getDate().toISOString(),
        raw_text: mensaje.getPlainBody()
      }});
      var c = r.getResponseCode();
      Logger.log("Mail " + mensaje.getId() + " → HTTP " + c + " " + r.getContentText());
      if (c === 200 || c === 201) hilos[i].addLabel(etiqueta);
    }}
  }}
}}
'''
