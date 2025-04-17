# secugen_api/sdk_interface/wrapper.py

import ctypes
import platform
import time
import logging
import os
import base64
import binascii

# Configurar logger
logger = logging.getLogger(__name__)
# Evitar duplicar logs si la app principal ya configura logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constantes del SDK (Basadas en sgfplib.h / Manual) ---
SGFDX_ERROR_NONE = 0
SGFDX_ERROR_FUNCTION_FAILED = 2 # Código de error genérico que vimos
# ... (Idealmente añadir más códigos de error para mensajes detallados) ...

# Device Names
SG_DEV_AUTO = 0xFF
SG_DEV_FDU06 = 0x07 # UPx (Hamster Pro - PID 2201)

# Security Levels
SL_NORMAL = 5

# Template Formats (Default: SG400 = 0x0200)
# TEMPLATE_FORMAT_SG400 = 0x0200

# Finger Info Constants
SG_FINGPOS_UK = 0x00 # Unknown finger
SG_IMPTYPE_LP = 0x00 # Live-scan Plain

# Otros
SGDEV_SN_LEN = 15
DEFAULT_TEMPLATE_SIZE = 2000 # ¡Ajustar si se usa otro formato o se sabe el tamaño!
DEFAULT_IMAGE_WIDTH = 260 # Para UPx/FDU06
DEFAULT_IMAGE_HEIGHT = 300 # Para UPx/FDU06


# --- Variables Globales de Estado ---
sgfplib = None
hFPM = None # Handle principal del SDK
sdk_initialized = False
device_opened = False
# lock = threading.Lock() # Añadir si se necesita concurrencia

# Nombre de la librería
LIB_NAME_LINUX = "libpysgfplib.so"

# --- Estructuras ctypes ---

class SGDeviceInfoParam(ctypes.Structure):
    _fields_ = [("DeviceID", ctypes.c_ulong),
                ("DeviceSN", ctypes.c_ubyte * (SGDEV_SN_LEN + 1)),
                ("ComPort", ctypes.c_ulong),
                ("ComSpeed", ctypes.c_ulong),
                ("ImageWidth", ctypes.c_ulong),
                ("ImageHeight", ctypes.c_ulong),
                ("Contrast", ctypes.c_ulong),
                ("Brightness", ctypes.c_ulong),
                ("Gain", ctypes.c_ulong),
                ("ImageDPI", ctypes.c_ulong),
                ("FWVersion", ctypes.c_ulong)]

class SGFingerInfo(ctypes.Structure):
     _fields_ = [("FingerNumber", ctypes.c_uint16),
                 ("ViewNumber", ctypes.c_uint16),
                 ("ImpressionType", ctypes.c_uint16),
                 ("ImageQuality", ctypes.c_uint16)]


# --- Funciones Internas ---

def _load_library():
    """Carga la librería SDK si no está cargada."""
    global sgfplib
    if sgfplib: return True
    try:
        if platform.system() == "Linux":
            sgfplib = ctypes.CDLL(LIB_NAME_LINUX)
            logger.info(f"Librería SDK '{LIB_NAME_LINUX}' cargada.")
            return True
        else:
            logger.error(f"SO no soportado: {platform.system()}"); return False
    # ... (manejo de errores como antes) ...
    except OSError as e:
        logger.error(f"Error cargando librería SDK '{LIB_NAME_LINUX}': {e}"); sgfplib = None; return False
    except Exception as e:
        logger.error(f"Error inesperado cargando librería: {e}"); sgfplib = None; return False


def _define_signatures():
    """Define las firmas ctypes para todas las funciones SDK necesarias."""
    global sgfplib
    if not sgfplib: return False
    try:
        # Core
        sgfplib.SGFPM_Create.argtypes = [ctypes.POINTER(ctypes.c_void_p)]; sgfplib.SGFPM_Create.restype = ctypes.c_ulong
        sgfplib.SGFPM_Init.argtypes = [ctypes.c_void_p, ctypes.c_ulong]; sgfplib.SGFPM_Init.restype = ctypes.c_ulong
        sgfplib.SGFPM_Terminate.argtypes = [ctypes.c_void_p]; sgfplib.SGFPM_Terminate.restype = ctypes.c_ulong
        # Device
        sgfplib.SGFPM_OpenDevice.argtypes = [ctypes.c_void_p, ctypes.c_ulong]; sgfplib.SGFPM_OpenDevice.restype = ctypes.c_ulong
        sgfplib.SGFPM_CloseDevice.argtypes = [ctypes.c_void_p]; sgfplib.SGFPM_CloseDevice.restype = ctypes.c_ulong
        sgfplib.SGFPM_GetDeviceInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(SGDeviceInfoParam)]; sgfplib.SGFPM_GetDeviceInfo.restype = ctypes.c_ulong
        # LED
        sgfplib.SGFPM_SetLedOn.argtypes = [ctypes.c_void_p, ctypes.c_bool]; sgfplib.SGFPM_SetLedOn.restype = ctypes.c_ulong
        # Image / Template
        sgfplib.SGFPM_GetImage.argtypes = [ctypes.c_void_p, ctypes.c_void_p]; sgfplib.SGFPM_GetImage.restype = ctypes.c_ulong
        sgfplib.SGFPM_CreateTemplate.argtypes = [ctypes.c_void_p, ctypes.POINTER(SGFingerInfo), ctypes.c_void_p, ctypes.c_void_p]; sgfplib.SGFPM_CreateTemplate.restype = ctypes.c_ulong
        sgfplib.SGFPM_GetLastImageQuality.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]; sgfplib.SGFPM_GetLastImageQuality.restype = ctypes.c_ulong
        # Matching
        sgfplib.SGFPM_MatchTemplate.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_bool)]; sgfplib.SGFPM_MatchTemplate.restype = ctypes.c_ulong

        logger.info("Firmas de funciones SDK definidas.")
        return True
    # ... (manejo de errores como antes) ...
    except AttributeError as e:
        logger.error(f"Error definiendo firma: Función '{e.name}' no existe."); return False
    except Exception as e:
        logger.error(f"Error inesperado definiendo firmas: {e}"); return False

def _check_error(error_code, function_name="Función SDK"):
    """Devuelve True si no hay error, False y loguea si hay error."""
    if error_code == SGFDX_ERROR_NONE: return True
    else: logger.error(f"{function_name}: Falló (Código={error_code})"); return False

# --- Funciones Públicas del Wrapper ---

def initialize_sdk():
    """Inicializa el SDK y abre el dispositivo. Devuelve True/False."""
    # global lock # Descomentar si se usa
    global sgfplib, hFPM, sdk_initialized, device_opened
    # with lock: # Descomentar si se usa
    if sdk_initialized and device_opened:
        logger.info("SDK ya inicializado y dispositivo abierto.")
        return True

    if not _load_library(): return False
    if not _define_signatures(): return False

    # Crear handle si no existe
    if not hFPM:
        temp_hFPM = ctypes.c_void_p()
        error_code = sgfplib.SGFPM_Create(ctypes.byref(temp_hFPM))
        if not _check_error(error_code, "SGFPM_Create") or not temp_hFPM.value:
            logger.critical("Fallo CRÍTICO al crear objeto SDK.")
            hFPM = None
            return False
        hFPM = temp_hFPM
        logger.info(f"Objeto SDK creado con handle: {hFPM.value}")

    # Inicializar SDK si no está inicializado
    if not sdk_initialized:
        error_code = sgfplib.SGFPM_Init(hFPM, SG_DEV_FDU06) # Usar el tipo UPx
        if not _check_error(error_code, "SGFPM_Init"):
            terminate_sdk() # Intentar limpiar si Init falla
            return False
        sdk_initialized = True
        logger.info("SDK inicializado.")

    # Abrir dispositivo si no está abierto
    if not device_opened:
        error_code = sgfplib.SGFPM_OpenDevice(hFPM, 0) # Abrir dispositivo ID 0
        if not _check_error(error_code, "SGFPM_OpenDevice"):
            terminate_sdk() # Intentar limpiar si Open falla
            return False
        device_opened = True
        logger.info("Dispositivo abierto.")

    return True # Todo OK

def terminate_sdk():
    """Cierra el dispositivo y termina el SDK."""
    # global lock # Descomentar si se usa
    global sgfplib, hFPM, sdk_initialized, device_opened
    # with lock: # Descomentar si se usa
    closed_properly = True
    if device_opened and hFPM and hFPM.value and sgfplib:
        logger.info("Cerrando dispositivo...")
        error_code = sgfplib.SGFPM_CloseDevice(hFPM)
        if not _check_error(error_code, "SGFPM_CloseDevice"):
             closed_properly = False
        device_opened = False # Marcar como cerrado incluso si falla

    if hFPM and hFPM.value and sgfplib: # Terminar si el handle se creó
        logger.info("Terminando SDK...")
        error_code = sgfplib.SGFPM_Terminate(hFPM)
        if not _check_error(error_code, "SGFPM_Terminate"):
            closed_properly = False
        # Resetear estado global
        sdk_initialized = False
        device_opened = False
        hFPM = None
        # Podríamos poner sgfplib = None aquí también si quisiéramos permitir recarga
    logger.info("Terminate SDK finalizado.")
    return closed_properly

def get_device_info():
    """Obtiene info del dispositivo. Devuelve dict o None."""
    # global lock # Descomentar si se usa
    # with lock: # Descomentar si se usa
    if not (sdk_initialized and device_opened and hFPM and hFPM.value):
        logger.error("Intento de obtener info, pero SDK no listo/abierto.")
        return None
    try:
        device_info = SGDeviceInfoParam()
        error_code = sgfplib.SGFPM_GetDeviceInfo(hFPM, ctypes.byref(device_info))
        if _check_error(error_code, "SGFPM_GetDeviceInfo"):
            serial_number_bytes = bytes(device_info.DeviceSN)
            serial_number = serial_number_bytes.partition(b'\0')[0].decode('ascii', errors='ignore')
            return {
                "device_id": device_info.DeviceID,
                "serial_number": serial_number,
                "image_width": device_info.ImageWidth,
                "image_height": device_info.ImageHeight,
                "image_dpi": device_info.ImageDPI,
                "fw_version": device_info.FWVersion,
            }
        else:
            return None
    except Exception as e:
        logger.error(f"Excepción en get_device_info: {e}", exc_info=True)
        return None

def set_led(on: bool):
    """Intenta encender/apagar el LED. Devuelve True/False."""
    # global lock # Descomentar si se usa
    # with lock: # Descomentar si se usa
    if not (sdk_initialized and device_opened and hFPM and hFPM.value):
        logger.error("Intento de controlar LED, pero SDK no listo/abierto.")
        return False
    try:
        logger.info(f"Intentando poner LED en {'ON' if on else 'OFF'}...")
        error_code = sgfplib.SGFPM_SetLedOn(hFPM, on)
        # Manejo especial del error 2 que vimos antes
        if error_code == SGFDX_ERROR_FUNCTION_FAILED:
             logger.warning("SGFPM_SetLedOn falló (Código 2) - Función podría no estar soportada.")
             return False
        elif error_code == SGFDX_ERROR_NONE:
             logger.info(f"SGFPM_SetLedOn({'ON' if on else 'OFF'}) ejecutado con éxito.")
             return True
        else:
             _check_error(error_code, f"SGFPM_SetLedOn({on})")
             return False
    except Exception as e:
        logger.error(f"Excepción en set_led: {e}", exc_info=True)
        return False

def capture_template():
    """Captura imagen y extrae plantilla. Devuelve plantilla Base64 o None."""
    # global lock # Descomentar si se usa
    # with lock: # Descomentar si se usa
    if not (sdk_initialized and device_opened and hFPM and hFPM.value):
        logger.error("Intento de capturar, pero SDK no listo/abierto.")
        return None

    try:
        # Obtener dimensiones (podrían cachearse si no cambian)
        info = get_device_info() # Llama a la función wrapper
        if not info or info["image_width"] == 0 or info["image_height"] == 0:
             logger.error("No se pudieron obtener dimensiones válidas para capturar.")
             return None
        width = info["image_width"]
        height = info["image_height"]

        # Crear buffer de imagen
        image_buffer = ctypes.create_string_buffer(width * height)
        logger.info("Llamando a SGFPM_GetImage... Coloca el dedo.")
        error_code_img = sgfplib.SGFPM_GetImage(hFPM, image_buffer)

        if not _check_error(error_code_img, "SGFPM_GetImage"):
            return None # Falló la captura
        logger.info("Imagen capturada.")

        # Obtener calidad (opcional, para SGFingerInfo)
        quality = ctypes.c_ulong(0)
        error_code_qual = sgfplib.SGFPM_GetLastImageQuality(hFPM, ctypes.byref(quality))
        if not _check_error(error_code_qual, "SGFPM_GetLastImageQuality"):
             logger.warning("No se pudo obtener calidad de imagen, usando 0.")
             img_quality = 0
        else:
             img_quality = quality.value
             logger.info(f"Calidad de imagen obtenida: {img_quality}")

        # Preparar info para la plantilla
        fp_info = SGFingerInfo()
        fp_info.FingerNumber = SG_FINGPOS_UK # Dedo desconocido
        fp_info.ViewNumber = 0 # Primera (y única) vista/muestra
        fp_info.ImpressionType = SG_IMPTYPE_LP # Live scan plain
        fp_info.ImageQuality = int(img_quality) if img_quality <= 65535 else 65535 # WORD max 65535

        # Crear buffer para plantilla (usar tamaño por defecto)
        template_buffer = ctypes.create_string_buffer(DEFAULT_TEMPLATE_SIZE)

        logger.info("Llamando a SGFPM_CreateTemplate...")
        error_code_tmpl = sgfplib.SGFPM_CreateTemplate(hFPM, ctypes.byref(fp_info), image_buffer, template_buffer)

        if not _check_error(error_code_tmpl, "SGFPM_CreateTemplate"):
             return None # Falló la creación de plantilla

        # Asumir tamaño fijo SG400 (400 bytes) si no se cambió formato
        # ¡OJO! Si usas otros formatos, necesitas GetTemplateSize
        actual_template_size = 400 # ¡Asunción! Solo para SG400
        template_bytes = template_buffer.raw[:actual_template_size]
        template_b64 = base64.b64encode(template_bytes).decode('utf-8')
        logger.info(f"Plantilla creada (Base64 len: {len(template_b64)}).")

        return template_b64

    except Exception as e:
        logger.error(f"Excepción en capture_template: {e}", exc_info=True)
        return None

def verify_templates(template1_b64, template2_b64, security_level=SL_NORMAL):
    """Compara dos plantillas Base64. Devuelve True/False o None si hay error."""
    # global lock # Descomentar si se usa
    # with lock: # Descomentar si se usa
    if not (sdk_initialized and device_opened and hFPM and hFPM.value):
        logger.error("Intento de verificar, pero SDK no listo/abierto.")
        return None

    try:
        # Decodificar
        try:
            t1_bytes = base64.b64decode(template1_b64)
            t2_bytes = base64.b64decode(template2_b64)
        except (TypeError, binascii.Error) as decode_error:
            logger.warning(f"Error decodificando plantillas Base64: {decode_error}")
            return None

        # Crear buffers (asumiendo tamaño máximo o fijo SG400)
        # ¡OJO! Si usas formatos variables, necesitas el tamaño real.
        t1_buffer = ctypes.create_string_buffer(t1_bytes, DEFAULT_TEMPLATE_SIZE)
        t2_buffer = ctypes.create_string_buffer(t2_bytes, DEFAULT_TEMPLATE_SIZE)

        # Variable para resultado
        match_result_val = ctypes.c_bool(False)
        match_result_ptr = ctypes.pointer(match_result_val)

        logger.info(f"Llamando a SGFPM_MatchTemplate (Nivel Sec={security_level})...")
        error_code = sgfplib.SGFPM_MatchTemplate(hFPM, t1_buffer, t2_buffer, security_level, match_result_ptr)

        if not _check_error(error_code, "SGFPM_MatchTemplate"):
            # El fallo en MatchTemplate no necesariamente invalida el resultado booleano,
            # pero es un error que la API debería reportar. Devolvemos None para indicarlo.
             return None

        match_result = match_result_ptr.contents.value
        logger.info(f"Resultado de comparación: {'COINCIDEN' if match_result else 'NO COINCIDEN'}")
        return match_result # Devolvemos el booleano directamente

    except Exception as e:
        logger.error(f"Excepción en verify_templates: {e}", exc_info=True)
        return None

# --- Inicialización al cargar (Opcional) ---
# Descomentar para intentar inicializar al importar el módulo
# if not initialize_sdk():
#    logger.error("FALLO AL AUTO-INICIALIZAR SDK WRAPPER AL IMPORTAR.")