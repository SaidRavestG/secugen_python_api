# Phyton_api/run.py

import os
from dotenv import load_dotenv

# --- IMPORTANTE: Importar desde TU paquete principal, que llamaste 'api' ---
from api import create_app

# Carga variables de entorno desde un archivo .env (si existe)
load_dotenv()

# Llama a la función factoría definida en api/__init__.py para crear la app
app = create_app()

# Este bloque se ejecuta solo si corres 'python3 run.py' directamente
if __name__ == '__main__':
    # Obtener host, puerto y modo debug de variables de entorno o usar defaults
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 5000))
    debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

    print(f" * Iniciando servidor Flask en http://{host}:{port}")
    print(f" * Modo Debug: {'activado' if debug_mode else 'desactivado'}")
    if debug_mode:
        print(" * ADVERTENCIA: El modo DEBUG está activado. No usar en producción.")

    # Iniciar el servidor de desarrollo de Flask
    # NOTA: Para producción, usa un servidor WSGI como Gunicorn o uWSGI.
    app.run(host=host, port=port, debug=debug_mode)