import ctypes
import platform
import time
import logging
import os

# Configuración básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constantes y Globales ---
SGFDX_ERROR_NONE = 0
SG_DEV_AUTO = 0xFF
SG_DEV_FDU06 = 0x07 # Para UPx (Hamster Pro)
SGDEV_SN_LEN = 15

sgfplib = None
sdk_initialized = False
device_opened = False # Flag para saber si abrimos el dispositivo
hFPM = None

LIB_NAME_LINUX = "libpysgfplib.so"

# --- Estructuras ---
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

# --- Funciones Auxiliares ---
def load_sdk_library():
    global sgfplib
    if sgfplib: return True
    try:
        if platform.system() == "Linux":
            lib_name = LIB_NAME_LINUX
            sgfplib = ctypes.CDLL(lib_name)
            logging.info(f"Librería SDK '{lib_name}' cargada.")
            return True
        else:
            logging.error(f"SO no soportado: {platform.system()}"); return False
    except OSError as e:
        logging.error(f"Error cargando librería SDK '{lib_name}': {e}"); sgfplib = None; return False
    except Exception as e:
        logging.error(f"Error inesperado cargando librería: {e}"); sgfplib = None; return False

def define_signatures():
    global sgfplib
    if not sgfplib: return False
    try:
        sgfplib.SGFPM_Create.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        sgfplib.SGFPM_Create.restype = ctypes.c_ulong

        sgfplib.SGFPM_Init.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        sgfplib.SGFPM_Init.restype = ctypes.c_ulong

        sgfplib.SGFPM_Terminate.argtypes = [ctypes.c_void_p]
        sgfplib.SGFPM_Terminate.restype = ctypes.c_ulong

        # --- Funciones añadidas ---
        sgfplib.SGFPM_OpenDevice.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        sgfplib.SGFPM_OpenDevice.restype = ctypes.c_ulong

        sgfplib.SGFPM_CloseDevice.argtypes = [ctypes.c_void_p]
        sgfplib.SGFPM_CloseDevice.restype = ctypes.c_ulong
        # -------------------------

        sgfplib.SGFPM_GetDeviceInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(SGDeviceInfoParam)]
        sgfplib.SGFPM_GetDeviceInfo.restype = ctypes.c_ulong

        sgfplib.SGFPM_GetImage.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        sgfplib.SGFPM_GetImage.restype = ctypes.c_ulong

        logging.info("Firmas SDK (Create, Init, Terminate, Open/CloseDevice, GetDeviceInfo, GetImage) definidas.")
        return True
    except AttributeError as e:
        logging.error(f"Error definiendo firma: Función '{e.name}' no existe."); return False
    except Exception as e:
        logging.error(f"Error inesperado definiendo firmas: {e}"); return False

def check_error(error_code, function_name="Función SDK"):
    if error_code == SGFDX_ERROR_NONE: return True
    else: logging.error(f"{function_name}: Falló (Código={error_code})"); return False

# --- Flujo Principal ---
if __name__ == "__main__":
    if not load_sdk_library(): exit(1)
    if not define_signatures(): exit(1)

    error_code = -1
    hFPM = ctypes.c_void_p()
    create_success = False
    init_success = False
    open_success = False # Flag para saber si OpenDevice funcionó

    try:
        logging.info("Intentando crear objeto SDK (SGFPM_Create)...")
        error_code = sgfplib.SGFPM_Create(ctypes.byref(hFPM))
        create_success = check_error(error_code, "SGFPM_Create")

        if create_success and hFPM.value:
            logging.info(f"Objeto SDK creado con handle: {hFPM.value}")

            logging.info("Intentando inicializar SDK (SGFPM_Init para FDU06)...")
            error_code = sgfplib.SGFPM_Init(hFPM, SG_DEV_FDU06) # Usar el tipo específico UPx
            init_success = check_error(error_code, "SGFPM_Init")

            if init_success:
                logging.info("SDK Inicializado correctamente.")
                sdk_initialized = True # Marcar para el finally

                # --- Abrir Dispositivo ---
                logging.info("Intentando abrir dispositivo (SGFPM_OpenDevice ID=0)...")
                device_id_to_open = 0 # Probar con ID 0 (primer dispositivo encontrado)
                error_code_open = sgfplib.SGFPM_OpenDevice(hFPM, device_id_to_open)
                open_success = check_error(error_code_open, "SGFPM_OpenDevice")

                if open_success:
                    logging.info("Dispositivo abierto correctamente.")
                    device_opened = True # Marcar para el finally

                    # --- Obtener Información del Dispositivo (AHORA después de Open) ---
                    logging.info("Intentando obtener info del dispositivo (SGFPM_GetDeviceInfo)...")
                    device_info = SGDeviceInfoParam()
                    error_code_di = sgfplib.SGFPM_GetDeviceInfo(hFPM, ctypes.byref(device_info))

                    if check_error(error_code_di, "SGFPM_GetDeviceInfo"):
                        width = device_info.ImageWidth
                        height = device_info.ImageHeight
                        # Obtener S/N como ejemplo
                        serial_number_bytes = bytes(device_info.DeviceSN)
                        serial_number = serial_number_bytes.partition(b'\0')[0].decode('ascii', errors='ignore')
                        logging.info(f"Info obtenida: Ancho={width}, Alto={height}, SN='{serial_number}'")

                        if width > 0 and height > 0:
                            # --- Capturar Imagen ---
                            logging.info(f"Creando buffer para imagen ({width}x{height})...")
                            image_buffer = ctypes.create_string_buffer(width * height)
                            logging.info("Intentando capturar imagen (SGFPM_GetImage)... Coloca el dedo.")
                            error_code_img = sgfplib.SGFPM_GetImage(hFPM, image_buffer)

                            if check_error(error_code_img, "SGFPM_GetImage"):
                                logging.info("¡ÉXITO! SGFPM_GetImage devolvió código 0.")
                            else:
                                logging.error("Fallo al capturar imagen.")
                        else:
                            logging.error("Dimensiones inválidas obtenidas.")
                    else:
                        logging.error("Fallo al obtener información del dispositivo.")
                else:
                    logging.error("Fallo al abrir el dispositivo.")
            else:
                logging.error("Fallo al inicializar el SDK.")
        elif create_success and not hFPM.value:
             logging.error("SGFPM_Create devolvió éxito pero el handle es NULL.")
        else:
            logging.error("Fallo al crear el objeto SDK.")

    except Exception as e:
        logging.error(f"Ocurrió un error general: {e}", exc_info=True)

    finally:
        # Cerrar dispositivo si se abrió
        if device_opened and hFPM.value and sgfplib:
            logging.info("Intentando cerrar dispositivo (SGFPM_CloseDevice)...")
            error_code_close = sgfplib.SGFPM_CloseDevice(hFPM)
            check_error(error_code_close, "SGFPM_CloseDevice")

        # Terminar SDK si se creó el handle
        if create_success and hFPM.value and sgfplib:
            logging.info("Intentando terminar SDK (SGFPM_Terminate)...")
            error_code_term = sgfplib.SGFPM_Terminate(hFPM)
            check_error(error_code_term, "SGFPM_Terminate")
            logging.info("Script finalizado.")
        elif not create_success:
             logging.warning("Objeto SDK no fue creado, no se necesita terminar.")
        else:
            logging.error("Estado inconsistente al finalizar.")