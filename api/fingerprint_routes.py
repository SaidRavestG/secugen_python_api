# secugen_api/api/fingerprint_routes.py

from flask import Blueprint, jsonify, request, current_app

# Importar el módulo wrapper con nuestras funciones SDK
from .sdk_interface import wrapper as sdk_wrapper

# Crear el Blueprint para estas rutas
# Usaremos 'fingerprint_api' como nombre interno para el blueprint
fingerprint_bp = Blueprint('fingerprint_api', __name__)

# Helper para verificar si el SDK está listo
def is_sdk_ready():
    return sdk_wrapper.sdk_initialized and sdk_wrapper.device_opened

@fingerprint_bp.route('/initialize', methods=['POST'])
def initialize():
    """Inicializa el SDK y abre el dispositivo."""
    current_app.logger.info("API Request: /initialize")
    init_success = sdk_wrapper.initialize_sdk() # Asigna el resultado booleano a UNA variable

    if init_success:
        # Si la inicialización fue exitosa, creamos un mensaje de éxito
        message = "SDK inicializado y dispositivo abierto correctamente."
        return jsonify({"success": True, "message": message}), 200
    else:
        # Si falló, creamos un mensaje de error genérico (los detalles estarán en el log del servidor)
        message = "Fallo al inicializar SDK o abrir dispositivo (ver logs del servidor)."
        return jsonify({"success": False, "message": message}), 503

@fingerprint_bp.route('/terminate', methods=['POST'])
def terminate():
    """Cierra el dispositivo y termina el SDK."""
    current_app.logger.info("API Request: /terminate")
    success, message = sdk_wrapper.terminate_sdk()
    # Terminate usualmente no debería fallar críticamente
    return jsonify({"success": success, "message": message}), 200

@fingerprint_bp.route('/status', methods=['GET'])
def get_status():
    """Obtiene información y estado del lector conectado."""
    current_app.logger.info("API Request: /status")
    if not is_sdk_ready():
         current_app.logger.warning("Status request pero SDK no listo.")
         return jsonify({"success": False, "message": "SDK no inicializado o dispositivo no abierto."}), 503

    info = sdk_wrapper.get_device_info()
    if info:
        return jsonify({"success": True, "status": "ok", "device_info": info}), 200
    else:
        current_app.logger.error("wrapper.get_device_info() devolvió None.")
        return jsonify({"success": False, "message": "Fallo al obtener información del dispositivo desde el wrapper."}), 500

@fingerprint_bp.route('/led', methods=['POST'])
def control_led():
    """Enciende o apaga el LED del lector."""
    current_app.logger.info("API Request: /led")
    if not is_sdk_ready():
         current_app.logger.warning("LED control request pero SDK no listo.")
         return jsonify({"success": False, "message": "SDK no inicializado o dispositivo no abierto."}), 503

    if not request.is_json:
        return jsonify({"success": False, "message": "Cuerpo de la solicitud debe ser JSON."}), 400

    data = request.get_json()
    led_state = data.get('state')

    if not isinstance(led_state, bool):
        return jsonify({"success": False, "message": "El cuerpo JSON debe contener el campo 'state' con valor true o false."}), 400

    current_app.logger.info(f"Solicitud para poner LED en: {'ON' if led_state else 'OFF'}")
    success = sdk_wrapper.set_led(led_state)

    if success:
        return jsonify({"success": True, "message": f"Comando para poner LED en {'ON' if led_state else 'OFF'} enviado."}), 200
    else:
        # Recordar que esto puede fallar con Código 2 indicando no soportado
        current_app.logger.warning("wrapper.set_led() devolvió False.")
        return jsonify({"success": False, "message": "Fallo al enviar comando LED al lector (podría no ser soportado)."}), 500

@fingerprint_bp.route('/capture', methods=['POST'])
def capture():
    """Captura una huella y devuelve la plantilla extraída en Base64."""
    current_app.logger.info("API Request: /capture")
    if not is_sdk_ready():
         current_app.logger.warning("Capture request pero SDK no listo.")
         return jsonify({"success": False, "message": "SDK no inicializado o dispositivo no abierto."}), 503

    # Añadir un pequeño delay antes de capturar, puede ayudar
    # time.sleep(0.1)

    template_b64 = sdk_wrapper.capture_template()

    if template_b64:
        return jsonify({"success": True, "template": template_b64}), 200
    else:
        current_app.logger.error("wrapper.capture_template() devolvió None.")
        # Podría ser error de captura (dedo mal puesto, etc) o error de extracción
        return jsonify({"success": False, "message": "Fallo durante la captura o extracción de plantilla."}), 500

@fingerprint_bp.route('/verify', methods=['POST'])
def verify():
    """Compara/Verifica dos plantillas enviadas en formato Base64."""
    current_app.logger.info("API Request: /verify")
    if not is_sdk_ready():
         current_app.logger.warning("Verify request pero SDK no listo.")
         return jsonify({"success": False, "message": "SDK no inicializado o dispositivo no abierto."}), 503

    if not request.is_json:
        return jsonify({"success": False, "message": "Cuerpo de la solicitud debe ser JSON."}), 400

    data = request.get_json()
    template1 = data.get('template1')
    template2 = data.get('template2')
    # Podrías añadir un nivel de seguridad opcional:
    # security_level = data.get('security_level', sdk_wrapper.SL_NORMAL)

    if not template1 or not template2:
        return jsonify({"success": False, "message": "El cuerpo JSON debe contener 'template1' y 'template2'."}), 400

    current_app.logger.info("Verificando plantillas...")
    match_result = sdk_wrapper.verify_templates(template1, template2) # Podrías pasar security_level aquí

    if match_result is None:
        current_app.logger.error("wrapper.verify_templates() devolvió None.")
        return jsonify({"success": False, "message": "Error durante el proceso de verificación."}), 500
    else:
        # verify_templates devuelve True si coinciden, False si no.
        return jsonify({"success": True, "match": match_result}), 200