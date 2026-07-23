import requests
from bs4 import BeautifulSoup
import logging
import re
from urllib.parse import urljoin
import urllib3
from app.nlp_engine import sanitizar_texto_html, validar_relevancia

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EnginePro")

FONTES = [
    {'nome': 'CNN International', 'url': 'https://edition.cnn.com', 'pais': '🇺🇸 EUA', 'seletor': 'h3, h2, .card__title'},
    {'nome': 'The New York Times', 'url': 'https://www.nytimes.com', 'pais': '🇺🇸 EUA', 'seletor': '.indicate-hover, h3, h2'},
    {'nome': 'Reuters', 'url': 'https://www.reuters.com', 'pais': '🌍 Global', 'seletor': 'h3, h2, .story-title'},
    {'nome': 'The Guardian', 'url': 'https://www.theguardian.com/international', 'pais': '🇬🇧 Reino Unido', 'seletor': 'h3, .fc-item__title'},
    {'nome': 'BBC World', 'url': 'https://www.bbc.com/news', 'pais': '🌍 Global', 'seletor': 'h3, .gs-c-promo-heading'},
    {'nome': 'Al Jazeera', 'url': 'https://www.aljazeera.com', 'pais': '🇶🇦 Catar', 'seletor': 'h3, .gc__title'},
    {'nome': 'El País', 'url': 'https://elpais.com', 'pais': '🇪🇸 Espanha', 'seletor': '.c_t, header h2, h3'},
    {'nome': 'El Periódico', 'url': 'https://www.elperiodico.com/es/', 'pais': '🇪🇸 Espanha', 'seletor': '.ep-title, h2, h3'},
    {'nome': 'La Vanguardia', 'url': 'https://www.lavanguardia.com', 'pais': '🇪🇸 Espanha', 'seletor': '.story-header, h2, h3'},
    {'nome': 'El Mundo', 'url': 'https://www.elmundo.es', 'pais': '🇪🇸 Espanha', 'seletor': '.ue-c-cover-snippet__headline, h2, h3'},
    {'nome': 'Corriere della Sera', 'url': 'https://www.corriere.it', 'pais': '🇮🇹 Itália', 'seletor': '.title-art, h2, h3'},
    {'nome': 'UOL Notícias', 'url': 'https://www.uol.com.br', 'pais': '🇧🇷 Brasil', 'seletor': 'h1, h2, h3'},
    {'nome': 'G1 Globo', 'url': 'https://g1.globo.com', 'pais': '🇧🇷 Brasil', 'seletor': 'h2, h3, .feed-post-body-title'}
]

PALAVRAS_CHAVE = {
    'política': [r'governo', r'president', r'election', r'minister', r'eleição', r'gobierno', r'elezioni', r'senate', r'congress'],
    'economia': [r'economy', r'inflation', r'gdp', r'dólar', r'market', r'inflación', r'disoccupazione', r'investment'],
    'guerra': [r'war', r'conflict', r'attack', r'missile', r'ukraine', r'russia', r'israel', r'guerra', r'bomba', r'military', r'strike'],
    'clima': [r'climate', r'flood', r'\bfire\b', r'environment', r'clima', r'aquecimento', r'medio ambiente', r'drought'],
    'direitos': [r'rights', r'justice', r'police', r'racism', r'justiça', r'derechos', r'diritti', r'law']
}

def normalizar_chave_duplicata(texto):
    return re.sub(r'[^a-zA-Z0-9]', '', texto).lower()

def extrair_href(tag):
    """Extrai a URL navegável da tag ou do ancestral mais próximo"""
    if tag.name == 'a' and tag.get('href'):
        return tag.get('href')
    ancora = tag.find_parent('a')
    if ancora and ancora.get('href'):
        return ancora.get('href')
    ancora_filha = tag.find('a')
    if ancora_filha and ancora_filha.get('href'):
        return ancora_filha.get('href')
    return ''

def executar_pipeline_scraping():
    noticias_coletadas = []
    titulos_vistos = set()
    
    session = requests.Session()
    session.verify = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,pt-BR;q=0.8,en;q=0.7'
    })
    
    for fonte in FONTES:
        try:
            resp = session.get(fonte['url'], timeout=10)
            if resp.status_code != 200:
                continue
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            tags = soup.select(fonte['seletor'])
            
            for tag in tags[:15]:
                texto = sanitizar_texto_html(tag)
                raw_href = extrair_href(tag)
                
                # Converte qualquer caminho relativo para URL absoluta válida
                link_absoluto = urljoin(fonte['url'], raw_href) if raw_href else ''
                
                chave_duplicada = normalizar_chave_duplicata(texto)
                if chave_duplicada in titulos_vistos or not validar_relevancia(texto):
                    continue

                if 25 < len(texto) < 180:
                    categorias = []
                    texto_lower = texto.lower()
                    
                    for cat, palavras in PALAVRAS_CHAVE.items():
                        for p in palavras:
                            if re.search(p, texto_lower):
                                if cat not in categorias:
                                    categorias.append(cat)

                    if categorias:
                        titulos_vistos.add(chave_duplicada)
                        noticias_coletadas.append({
                            'titulo': texto,
                            'fonte': fonte['nome'],
                            'pais': fonte['pais'],
                            'link': link_absoluto,
                            'categorias': ','.join(categorias),
                            'categorias_list': categorias
                        })
        except Exception as e:
            logger.error(f"Erro na fonte {fonte['nome']}: {e}")
            
    return noticias_coletadas