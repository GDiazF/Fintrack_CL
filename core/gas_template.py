"""Plantilla completa de Google Apps Script para onboarding (Fase C)."""

BANCOS_DISPONIBLES = {
    'bancoestado': {
        'id': 'bancoestado',
        'label': 'BancoEstado',
        'from_domain': 'bancoestado.cl',
        'conector': 'gmail_bancoestado_v1',
        'probe_raw': 'BancoEstado: compra de prueba por $1.590 en COPEC el 18/07/2026.',
        # Asuntos reales de movimientos (evita marketing / avisos genéricos).
        'subject_phrases': (
            'Notificación de compra',
            'Comprobante de pago de servicios',
            'Aviso de envío o recepción de dinero',
        ),
    },
    'santander': {
        'id': 'santander',
        'label': 'Santander',
        'from_domain': 'santander.cl',
        'conector': 'gmail_santander_v1',
        'probe_raw': (
            'Santander\nComprobante\nTransferencia de fondos\n'
            '*Monto transferido*\n*$ 1.590*\n*Datos de destino*\nNombre\nPrueba'
        ),
        'subject_phrases': (
            'Comprobante Transferencia de fondos',
        ),
    },
    'bci': {
        'id': 'bci',
        'label': 'BCI',
        'from_domain': 'bci.cl',
        'conector': 'gmail_bci_v1',
        'probe_raw': 'BCI: compra por $1.590 en COPEC el 18/07/2026.',
        # Sin asuntos confirmados aún → solo filtro por remitente.
        'subject_phrases': (),
    },
}

BANCOS_DEFAULT = ('bancoestado', 'santander', 'bci')


def normalizar_bancos(seleccion):
    """Devuelve tupla ordenada de ids válidos; si vacío o inválido → todos."""
    if not seleccion:
        return BANCOS_DEFAULT
    vistos = []
    for raw in seleccion:
        key = (raw or '').strip().lower()
        if key in BANCOS_DISPONIBLES and key not in vistos:
            vistos.append(key)
    return tuple(vistos) if vistos else BANCOS_DEFAULT


def _gmail_clause_banco(meta):
    """from:dominio, y si hay asuntos conocidos: AND (subject:… OR …)."""
    domain = meta['from_domain']
    subjects = meta.get('subject_phrases') or ()
    if not subjects:
        return f'from:{domain}'
    sub_or = ' OR '.join(f'subject:"{frase}"' for frase in subjects)
    return f'(from:{domain} AND ({sub_or}))'


def build_gmail_search_query(bancos):
    """Query Gmail sin el tramo -label (eso se concatena en JS)."""
    meta = [BANCOS_DISPONIBLES[b] for b in normalizar_bancos(bancos)]
    return ' OR '.join(_gmail_clause_banco(m) for m in meta)


def build_gas_script(*, api_key_id, api_secret, endpoint_url, bancos=None):
    """Devuelve el script GAS listo para pegar, con credenciales y bancos elegidos."""
    api_key_id = api_key_id.replace('\\', '\\\\').replace('"', '\\"')
    api_secret = api_secret.replace('\\', '\\\\').replace('"', '\\"')
    endpoint_url = endpoint_url.replace('\\', '\\\\').replace('"', '\\"')

    bancos = normalizar_bancos(bancos)
    meta = [BANCOS_DISPONIBLES[b] for b in bancos]

    # Se cierra la comilla en JS y se concatena ETIQUETA_PROCESADO.
    gmail_query = f'{build_gmail_search_query(bancos)} -label:" + ETIQUETA_PROCESADO'

    default_conector = meta[0]['conector']
    probe_conector = meta[0]['conector']
    probe_raw = meta[0]['probe_raw'].replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    conector_lines = [
        f'      if (remitente.indexOf("{m["from_domain"]}") !== -1) '
        f'conectorId = "{m["conector"]}";'
        for m in meta[1:]
    ]
    conector_js = ('\n' + '\n'.join(conector_lines)) if conector_lines else ''

    bancos_comentario = ', '.join(m['label'] for m in meta)

    return f'''/**
 * Fintrack CL — Cliente Gmail
 * Bancos: {bancos_comentario}
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
    conector: "{probe_conector}",
    gmail_message_id: "gas_probe_" + Date.now(),
    fecha_correo: "2026-07-18T12:00:00.000Z",
    raw_text: "{probe_raw}"
  }});
  Logger.log("HTTP " + resp.getResponseCode() + ": " + resp.getContentText());
}}

function enviarCorreosAlServidor() {{
  var etiqueta = GmailApp.getUserLabelByName(ETIQUETA_PROCESADO) || GmailApp.createLabel(ETIQUETA_PROCESADO);
  var hilos = GmailApp.search("{gmail_query}, 0, 50);
  Logger.log("Hilos encontrados: " + hilos.length);
  for (var i = 0; i < hilos.length; i++) {{
    var mensajes = hilos[i].getMessages();
    for (var j = 0; j < mensajes.length; j++) {{
      var mensaje = mensajes[j];
      if (hilos[i].getLabels().some(function(l) {{ return l.getName() === ETIQUETA_PROCESADO; }})) continue;
      var remitente = mensaje.getFrom();
      var conectorId = "{default_conector}";{conector_js}
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
