"""Plantilla completa de Google Apps Script para onboarding (Fase C)."""


def build_gas_script(*, api_key_id, api_secret, endpoint_url):
    """Devuelve el script GAS listo para pegar, con credenciales inyectadas."""
    api_key_id = api_key_id.replace('\\', '\\\\').replace('"', '\\"')
    api_secret = api_secret.replace('\\', '\\\\').replace('"', '\\"')
    endpoint_url = endpoint_url.replace('\\', '\\\\').replace('"', '\\"')

    return f'''/**
 * Fintrack CL — Cliente Gmail (mensajero).
 * 1) Ejecuta probarConexionFintrack
 * 2) Luego activador cada 10 min → enviarCorreosAlServidor
 */
var API_KEY_ID = "{api_key_id}";
var API_SECRET = "{api_secret}";
var ENDPOINT_URL = "{endpoint_url}";
var ETIQUETA_PROCESADO = "fintrack-procesado";

function _hexFromBytes(firmaBytes) {{
  var hex = "";
  for (var i = 0; i < firmaBytes.length; i++) {{
    var b = firmaBytes[i];
    if (b < 0) b += 256;
    var h = b.toString(16);
    hex += (h.length === 1 ? "0" : "") + h;
  }}
  return hex;
}}

function _firmar(payloadStr, timestamp, nonce) {{
  var msg = payloadStr + timestamp + nonce;
  var firmaBytes = Utilities.computeHmacSha256Signature(msg, API_SECRET);
  return _hexFromBytes(firmaBytes);
}}

/** Envío: text/plain para que UrlFetch NO reescriba el JSON firmado. */
function _postFintrack(payloadStr) {{
  var timestamp = Math.floor(Date.now() / 1000).toString();
  var nonce = Utilities.getUuid().replace(/-/g, "").substring(0, 16);
  var firmaHex = _firmar(payloadStr, timestamp, nonce);

  return UrlFetchApp.fetch(ENDPOINT_URL, {{
    method: "post",
    contentType: "text/plain; charset=utf-8",
    headers: {{
      "X-Key-ID": API_KEY_ID,
      "X-Signature": firmaHex,
      "X-Timestamp": timestamp,
      "X-Nonce": nonce
    }},
    payload: payloadStr,
    muteHttpExceptions: true
  }});
}}

function probarConexionFintrack() {{
  if (!API_SECRET || API_SECRET.indexOf("REEMPLAZA") === 0) {{
    Logger.log("API_SECRET invalido");
    return;
  }}
  var payloadStr = '{{"conector":"gmail_bancoestado_v1","gmail_message_id":"gas_probe_1","fecha_correo":"2026-07-18T12:00:00.000Z","raw_text":"hola fintrack"}}';
  Logger.log("KEY_ID=" + API_KEY_ID);
  Logger.log("SECRET_PREFIX=" + API_SECRET.substring(0, 16));
  var resp = _postFintrack(payloadStr);
  Logger.log("HTTP " + resp.getResponseCode() + ": " + resp.getContentText());
}}

function enviarCorreosAlServidor() {{
  if (!API_SECRET || API_SECRET.indexOf("REEMPLAZA") === 0) {{
    Logger.log("API_SECRET invalido");
    return;
  }}

  var etiqueta = GmailApp.getUserLabelByName(ETIQUETA_PROCESADO) || GmailApp.createLabel(ETIQUETA_PROCESADO);
  var query = "(from:bancoestado.cl OR from:santander.cl OR from:bci.cl) -label:" + ETIQUETA_PROCESADO;
  var hilos = GmailApp.search(query, 0, 15);

  for (var i = 0; i < hilos.length; i++) {{
    var mensajes = hilos[i].getMessages();
    for (var j = 0; j < mensajes.length; j++) {{
      var mensaje = mensajes[j];
      var revisado = hilos[i].getLabels().some(function(l) {{
        return l.getName() === ETIQUETA_PROCESADO;
      }});
      if (revisado) continue;

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

      try {{
        var respuesta = _postFintrack(payloadStr);
        var codigo = respuesta.getResponseCode();
        if (codigo === 200 || codigo === 201) {{
          hilos[i].addLabel(etiqueta);
        }} else {{
          Logger.log("Fintrack HTTP " + codigo + ": " + respuesta.getContentText());
        }}
      }} catch (e) {{
        Logger.log("Fallo: " + e);
      }}
    }}
  }}
}}
'''
