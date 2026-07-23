import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    # Permite migração transparente para PostgreSQL via variável de ambiente
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///news_intel.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False