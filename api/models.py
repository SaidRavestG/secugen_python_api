# api/models.py
from . import db # Importar la instancia db de __init__.py
import datetime

class User(db.Model):
    __tablename__ = 'users' # Nombre de la tabla
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # ... otros campos de usuario (password hash, etc.) ...
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Relación con las huellas
    fingerprints = db.relationship('Fingerprint', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Fingerprint(db.Model):
    __tablename__ = 'fingerprints' # Nombre de la tabla
    id = db.Column(db.Integer, primary_key=True)
    # Clave foránea a la tabla users
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    finger_position = db.Column(db.String(50), nullable=False) # ej: "Pulgar Derecho"
    template_format = db.Column(db.String(20), nullable=False, default='SG400')
    template_data = db.Column(db.Text, nullable=False) # Para guardar Base64
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<Fingerprint {self.id} User:{self.user_id} Finger:{self.finger_position}>'