# api/__init__.py
from flask import Flask, jsonify

# ¡NO definas 'app' aquí fuera!

def create_app(config_name='default'):
    """Application Factory Function"""
    # 1. CREAR LA INSTANCIA DE APP AQUÍ DENTRO:
    app = Flask(__name__)
    print(f" * Flask App creada en {__name__}") # Mensaje para depurar

    # --- (Opcional) Cargar configuración ---
    # app.config[...] = ...

    # --- (Opcional) Inicializar Extensiones ---
    # ...

    # --- Registrar Blueprints ---
    # Importar el blueprint DENTRO o justo antes si es seguro
    from .fingerprint_routes import fingerprint_bp # ¡Esta es la importación corregida!

    # Registrar el blueprint USANDO la variable 'app' definida arriba DENTRO de esta función
    app.register_blueprint(fingerprint_bp, url_prefix='/api/v1/fingerprint')
    print(f" * Blueprint '{fingerprint_bp.name}' registrado en '{app.blueprints[fingerprint_bp.name].url_prefix}'") # Usar fingerprint_bp.name


    # --- (Opcional) Ruta Raíz ---
    @app.route('/')
    def index():
        return jsonify(message="API SecuGen Funcionando", status="ok")

    # --- (Opcional) Manejadores de Errores ---
    # ...

    # 7. DEVOLVER la instancia de la app creada y configurada
    return app

# --- ¡¡¡ASEGÚRATE DE QUE NO HAYA CÓDIGO AQUÍ FUERA QUE INTENTE USAR 'app'!!! ---
# Por ejemplo, estas líneas NO deben estar aquí fuera:
# from .fingerprint_routes import fingerprint_bp # <= NO AQUÍ
# app.register_blueprint(fingerprint_bp, url_prefix='/api/v1/fingerprint') # <= NO AQUÍ