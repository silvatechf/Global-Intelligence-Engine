from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Noticia(db.Model):
    __tablename__ = 'noticias'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=False, unique=True)
    fonte = db.Column(db.String(100), nullable=False)
    pais = db.Column(db.String(50), nullable=False)
    link = db.Column(db.Text, nullable=True)
    categorias = db.Column(db.String(200), nullable=True)  # Armazenado como string separada por vírgula
    score = db.Column(db.Integer, default=0)
    data_coleta = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "titulo": self.titulo,
            "fonte": self.fonte,
            "pais": self.pais,
            "link": self.link,
            "categorias": self.categorias.split(',') if self.categorias else [],
            "score": self.score,
            "data_coleta": self.data_coleta.isoformat()
        }