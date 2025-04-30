# api/__init__.py
import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy # Importar
from flask_cors import CORS  # Importar CORS
import logging

# Importar el wrapper
from .sdk_interface import wrapper as sdk_wrapper

# Crear instancia de SQLAlchemy FUERA de la factoría
db = SQLAlchemy()

def create_app(config_name='default'):
    """Application Factory Function"""
    app = Flask(__name__)
    # Configurar CORS de manera completamente permisiva
    CORS(app, 
         resources={r"/*": {
             "origins": "*",
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
             "allow_headers": "*",
             "expose_headers": "*",
             "supports_credentials": True,
             "max_age": 600
         }})
    
    app.logger.setLevel(logging.INFO)
    app.logger.info(f"Creando Flask app '{__name__}'...")

    # --- Configuración de la Base de Datos ---
    # Cargar desde variable de entorno o usar default. ¡PON TU CONTRASEÑA REAL AQUÍ o en .env!
    db_user = os.getenv('DB_USER', 'secugen_user')
    db_password = os.getenv('DB_PASSWORD', 'tu_contraseña_segura') # <- ¡IMPORTANTE!
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5433')
    db_name = os.getenv('DB_NAME', 'secugen_db')
    # Construir URI (asegúrate de que la contraseña no se loguee accidentalmente)
    app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Recomendado desactivar
    app.logger.info(f"Configurando BD en: postgresql://{db_user}:***@{db_host}:{db_port}/{db_name}")

    # Inicializar SQLAlchemy con la app
    db.init_app(app)
    app.logger.info("SQLAlchemy inicializado.")

    # --- Registrar Blueprints ---
    from .fingerprint_routes import fingerprint_bp
    app.register_blueprint(fingerprint_bp, url_prefix='/api/v1/fingerprint')
    app.logger.info(f"Blueprint '{fingerprint_bp.name}' registrado.")


    # --- Inicialización SDK (Manual a través de endpoint) ---
    # (Mantenemos la inicialización manual por ahora)


    # --- Ruta Raíz ---
    @app.route('/')
    def index():
        # Ejemplo de verificación de conexión a BD
        try:
            db.session.execute(db.text('SELECT 1')) # Intenta ejecutar una consulta simple
            db_status = "conectada"
        except Exception as e:
            app.logger.error(f"Error conectando a la BD: {e}")
            db_status = "desconectada"
        return jsonify(message="API SecuGen Funcionando", status="ok", database=db_status)


    return app