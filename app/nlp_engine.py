import re
import math
from datetime import datetime, timezone
from collections import Counter
import spacy

# Carrega o modelo do spaCy se disponível
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None

# Lista de Stopwords e termos genéricos para filtros NLP
STOPWORDS_GLOBAL = {
    # Português
    'para', 'com', 'sem', 'sobre', 'depois', 'entre', 'como', 'mais', 'menos', 'novo', 'nova',
    'onde', 'quando', 'quem', 'diz', 'veja', 'saiba', 'pode', 'anos', 'após', 'durante',
    # Inglês
    'that', 'with', 'from', 'about', 'after', 'before', 'over', 'says', 'said', 'will', 'have',
    'been', 'were', 'would', 'could', 'should', 'here', 'there', 'what', 'when', 'where',
    'moment', 'come', 'world', 'first', 'second', 'more', 'some', 'many', 'like', 'live', 'news',
    # Espanhol & Italiano
    'para', 'como', 'este', 'esta', 'entre', 'sobre', 'della', 'degli', 'nella', 'pero', 'danni'
}

BLACK_LIST_RIGIDA = [
    'futebol', 'brasileirão', 'santos', 'goleia', 'poker', 'neymar', 'messi', 'bbb',
    'novela', 'carro', 'recall', 'polo', 'volkswagen', 'volvo', 'jogo', 'empatam'
]

def sanitizar_texto_html(tag_element):
    """Resolve concatenação de texto colado inserindo espaços entre nós do DOM"""
    if not tag_element:
        return ""
    for child in tag_element.find_all(True):
        child.insert_before(" ")
        child.insert_after(" ")
    texto = tag_element.get_text()
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def validar_relevancia(titulo: str) -> bool:
    """Descarta títulos contendo palavras da blacklist rígida"""
    if not titulo:
        return False
    texto_lower = titulo.lower()
    for termo in BLACK_LIST_RIGIDA:
        if termo in texto_lower:
            return False
    return True

def extrair_entidades_e_topics(noticias: list) -> list:
    """Extrai atores e lugares reais via spaCy NER com deduplicação"""
    entidades = []
    
    for n in noticias:
        titulo = n.get('titulo', '')
        doc = nlp(titulo) if nlp else None
        if doc:
            for ent in doc.ents:
                if ent.label_ in ['GPE', 'ORG', 'PERSON'] and len(ent.text) > 2:
                    val = ent.text.strip().capitalize()
                    if val.lower() not in STOPWORDS_GLOBAL:
                        entidades.append(val)
        else:
            tokens = re.findall(r'\b[A-Z][a-zA-Z]{3,}\b', titulo)
            for t in tokens:
                if t.lower() not in STOPWORDS_GLOBAL:
                    entidades.append(t)

    frequencia = Counter(entidades).most_common(6)
    return [{'topico': term, 'mencoes': count} for term, count in frequencia]

def calcular_score_ml(titulo: str, categorias: list, data_coleta: datetime, frequencia_entidades_lote: dict) -> float:
    """
    Ranking Multi-Fatorial:
    Pondera categorias, densidade de NER e aplica o amortecimento por decaimento temporal.
    """
    score_base = len(categorias) * 2.5
    
    num_entidades = 0
    if nlp and titulo:
        doc = nlp(titulo)
        entidades = [ent.text.lower() for ent in doc.ents if ent.label_ in ['GPE', 'ORG', 'PERSON']]
        num_entidades = len(entidades)
        
        for ent in entidades:
            if frequencia_entidades_lote.get(ent, 0) >= 3:
                score_base += 3.0  # Trend Boost
                
    score_base += (num_entidades * 1.5)
    
    # Tratamento seguro para comparação de datetime naive vs aware
    agora = datetime.now(timezone.utc)
    if data_coleta.tzinfo is None:
        data_coleta = data_coleta.replace(tzinfo=timezone.utc)
        
    horas_decorridas = max(0.0, (agora - data_coleta).total_seconds() / 3600.0)
    gravidade = 1.5
    score_final = score_base / math.pow((horas_decorridas + 2.0), gravidade)
    
    return round(score_final, 2)