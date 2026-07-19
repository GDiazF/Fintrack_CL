"""Plantilla completa de Google Apps Script para onboarding (Fase C)."""


def build_gas_script(*, api_key_id, api_secret, endpoint_url):
    """Devuelve el script GAS listo para pegar, con credenciales inyectadas."""
    api_key_id = api_key_id.replace('\\', '\\\\').replace('"', '\\"')
    api_secret = api_secret.replace('\\', '\\\\').replace('"', '\\"')
    endpoint_url = endpoint_url.replace('\\', '\\\\').replace('"', '\\"')

    return f'''/**
 * Fintrack CL — Cliente Gmail
 * Ejecuta primero: probarConexionFintrack
 */
var API_KEY_ID = "{api_key_id}";
var API_SECRET = "{api_secret}";
var ENDPOINT_URL = "{endpoint_url}";
var ETIQUETA_PROCESADO = "fintrack-procesado";

function _firmar(payloadStr, timestamp, nonce) {{
  var msg = payloadStr + timestamp + nonce;
  var firmaBytes = Utilities.computeHmacSha256Signature(msg, API_SECRET);
  // Base64 nativo de Apps Script (evita bugs al convertir a hex)
  return Utilities.base64Encode(firmaBytes);
}}

function _postFintrack(payloadStr) {{
  var timestamp = Math.floor(Date.now() / 1000).toString();
  var nonce = Utilities.getUuid().replace(/-/g, "").substring(0, 16);
  var firma = _firmar(payloadStr, timestamp, nonce);

  return UrlFetchApp.fetch(ENDPOINT_URL, {{
    method: "post",
    contentType: "text/plain; charset=utf-8",
    headers: {{
      "X-Key-ID": API_KEY_ID,
      "X-Signature": firma,
      "X-Timestamp": timestamp,
      "X-Nonce": nonce
    }},
    payload: payloadStr,
    muteHttpExceptions: true
  }});
}}

function probarConexionFintrack() {{
  var payloadStr = '{{"conector":"gmail_bancoestado_v1","gmail_message_id":"gas_probe_1","fecha_correo":"2026-07-18T12:00:00.000Z","raw_text":"hola fintrack"}}';
  var resp = _postFintrack(payloadStr);
  Logger.log("HTTP " + resp.getResponseCode() + ": " + resp.getContentText());
}}

function enviarCorreosAlServidor() {{
  var etiqueta = GmailApp.getUserLabelByName(ETIQUETA_PROCESADO) || GmailApp.createLabel(ETIQUETA_PROCESADO);
  var hilos = GmailApp.search("(from:bancoestado.cl OR from:santander.cl OR from:bci.cl) -label:" + ETIQUETA_PROCESADO, 0, 15);
  for (var i = 0; i < hilos.length; i++) {{
    var mensajes = hilos[i].getMessages();
    for (var j = 0; j < mensajes.length; j++) {{
      var mensaje = mensajes[j];
      if (hilos[i].getLabels().some(function(l) {{ return l.getName() === ETIQUETA_PROCESADO; }})) continue;
      var remitente = mensaje.getFrom();
      var conectorId = "gmail_bancoestado_v1";
      if (remitente.indexOf("santander.cl") !== -1) conectorId = "gmail_santander_v1";
      if (remitente.indexOf("bci.cl") !== -1) conectorId = "gmail_bci_v1";
      var payloadStr = JSON.stringify({{
        conector: conectorId,
        gmail_message_id: mensaje.getId(),
        fecha_correo: mensaje.getDate().toISOString(),
        raw_text: mensaje.getPlainBody()
      }});
      var respuesta = _postFintrack(payloadStr);
      var codigo = respuesta.getResponseCode();
      if (codigo === 200 || codigo === 201) hilos[i].addLabel(etiqueta);
      else Logger.log("Fintrack HTTP " + codigo + ": " + respuesta.getContentText());
    }}
  }}
}}
'''
