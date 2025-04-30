# secugen_api/api/fingerprint_routes.py

from flask import Blueprint, jsonify, request, current_app

# Importar el módulo wrapper con nuestras funciones SDK
from .sdk_interface import wrapper as sdk_wrapper
from . import db 
from .models import User, Fingerprint # Importar modelos de models.py
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
    
@fingerprint_bp.route('/enroll', methods=['POST'])
def enroll_fingerprint():
    """
    Endpoint para enrolar/registrar una nueva huella para un usuario.
    Espera JSON: {"user_id": <id>, "finger_position": "nombre_dedo"}
    """
    current_app.logger.info("API Request: /enroll")
    if not is_sdk_ready(): # Usar la función helper si la tienes
         current_app.logger.warning("Enroll request pero SDK no listo.")
         return jsonify({"success": False, "message": "SDK no inicializado o dispositivo no abierto."}), 503

    # 1. Validar Input JSON
    if not request.is_json:
        return jsonify({"success": False, "message": "Cuerpo de la solicitud debe ser JSON."}), 400

    data = request.get_json()
    user_id = data.get('user_id')
    finger_position = data.get('finger_position')

    if not user_id or not finger_position:
        return jsonify({"success": False, "message": "Faltan 'user_id' o 'finger_position' en el cuerpo JSON."}), 400

    # 2. Verificar que el usuario exista
    user = User.query.get(user_id) # Busca usuario por ID
    if not user:
        current_app.logger.warning(f"Intento de enrolar para user_id {user_id} no existente.")
        return jsonify({"success": False, "message": f"Usuario con ID {user_id} no encontrado."}), 404

    # 3. (Opcional) Verificar si ya existe huella para ese dedo y usuario
    existing_fp = Fingerprint.query.filter_by(user_id=user_id, finger_position=finger_position).first()
    if existing_fp:
        # Podrías permitir sobreescribir o devolver error. Devolvemos error por ahora.
        current_app.logger.warning(f"Intento de enrolar dedo '{finger_position}' que ya existe para user_id {user_id}.")
        return jsonify({"success": False, "message": f"Ya existe una huella registrada para el dedo '{finger_position}' de este usuario."}), 409 # 409 Conflict

    # 4. Capturar la plantilla de la huella
    current_app.logger.info(f"Iniciando captura para user_id={user_id}, finger='{finger_position}'. Pide al usuario colocar el dedo.")
    template_b64 = sdk_wrapper.capture_template()

    if not template_b64:
        current_app.logger.error("wrapper.capture_template() falló durante el enrolamiento.")
        return jsonify({"success": False, "message": "Fallo durante la captura o extracción de plantilla desde el lector."}), 500

    # 5. Crear y guardar el registro en la BD
    try:
        new_fingerprint = Fingerprint(
            user_id=user_id,
            finger_position=finger_position,
            template_data=template_b64,
            template_format='SG400' # Asumiendo SG400 por defecto
        )
        db.session.add(new_fingerprint)
        db.session.commit()
        current_app.logger.info(f"Huella enrolada exitosamente con ID: {new_fingerprint.id} para user_id: {user_id}")
        # Devolvemos el ID del registro creado y un mensaje
        return jsonify({
            "success": True,
            "message": "Huella registrada exitosamente.",
            "fingerprint_id": new_fingerprint.id
            }), 201 # 201 Created
    except Exception as e:
        db.session.rollback() # Revertir cambios en caso de error de BD
        current_app.logger.error(f"Error al guardar huella en BD para user_id {user_id}: {e}")
        return jsonify({"success": False, "message": "Error interno al guardar la huella en la base de datos."}), 500
