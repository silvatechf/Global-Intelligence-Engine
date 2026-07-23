import re
import unicodedata
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def remover_acentos(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])

class SemanticSearchEngine:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            analyzer='char_wb',
            ngram_range=(3, 5),
            lowercase=True
        )

    def sanitizar_query(self, texto: str) -> str:
        if not texto:
            return ""
        texto_limpo = remover_acentos(texto.lower())
        texto_limpo = re.sub(r'[^a-z0-9\s]', '', texto_limpo)
        return texto_limpo.strip()

    def buscar_similares(self, query: str, documentos: list, top_k: int = 3) -> list:
        query_limpa = self.sanitizar_query(query)
        if not query_limpa or not documentos:
            return []

        corpus_original = [doc.get('titulo', '') for doc in documentos]
        corpus_normalizado = [remover_acentos(t.lower()) for t in corpus_original]

        if not any(corpus_normalizado):
            return []

        try:
            tfidf_matrix = self.vectorizer.fit_transform(corpus_normalizado)
            query_vector = self.vectorizer.transform([query_limpa])

            similaridades = cosine_similarity(query_vector, tfidf_matrix).flatten()
            indices_ordenados = np.argsort(similaridades)[::-1]

            resultados = []
            for idx in indices_ordenados[:top_k]:
                score = float(similaridades[idx])
                # Aumentado o limiar de corte para 15% para eliminar falsos positivos de baixa relevância
                if score >= 0.15:
                    resultados.append({
                        'noticia': documentos[idx],
                        'similarity_score': round(score, 4)
                    })

            return resultados
        except Exception as e:
            return []

ml_engine = SemanticSearchEngine()