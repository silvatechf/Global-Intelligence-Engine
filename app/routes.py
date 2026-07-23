from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify
from app.models import db, Noticia
from app.scraper import executar_pipeline_scraping, normalizar_chave_duplicata
from app.nlp_engine import extrair_entidades_e_topics, calcular_score_ml
from app.ml_engine import ml_engine

main_bp = Blueprint('main', __name__)

@main_bp.route('/favicon.ico')
def favicon():
    return '', 204

@main_bp.route('/')
def dashboard():
    limite_tempo = datetime.now(timezone.utc) - timedelta(hours=24)
    todas = Noticia.query.filter(Noticia.data_coleta >= limite_tempo).all()
    dict_noticias = [n.to_dict() for n in todas]
    
    # Recupera o último lote sincronizado da sessão ou usa o histórico recente
    ultimos_ids = session.get('ultimo_lote_ids', [])
    if ultimos_ids:
        lote_atual = [n.to_dict() for n in todas if n.id in ultimos_ids]
    else:
        lote_atual = dict_noticias

    # 1. NLP Dinâmico: Extrai tendências APENAS do lote mais recente
    trends = extrair_entidades_e_topics(lote_atual if lote_atual else dict_noticias)
    freq_map = {t['topico'].lower(): t['mencoes'] for t in trends}
    
    # 2. Recalcula o Score ML aplicando decaimento temporal
    for n in todas:
        cats = n.categorias.split(',') if n.categorias else []
        n.score = calcular_score_ml(n.titulo, cats, n.data_coleta, freq_map)
        
    db.session.commit()
    
    # 3. Ordena pela pontuação reclassificada
    todas_ordenadas = sorted(todas, key=lambda x: x.score, reverse=True)
    
    # 4. Distribuição balanceada (Teto de no máximo 2 por fonte nos destaques)
    noticias_balanceadas = []
    contagem_fonte = {}
    for n in todas_ordenadas:
        contagem_fonte[n.fonte] = contagem_fonte.get(n.fonte, 0) + 1
        if contagem_fonte[n.fonte] <= 2:
            noticias_balanceadas.append(n.to_dict())

    paises = list(set([n.pais for n in todas]))
    
    return render_template(
        'dashboard.html', 
        noticias=noticias_balanceadas, 
        totais=len(todas), 
        paises=paises, 
        trends=trends
    )

@main_bp.route('/sync', methods=['POST', 'GET'])
def sincronizar():
    dados = executar_pipeline_scraping()
    chaves_banco = {normalizar_chave_duplicata(n.titulo) for n in Noticia.query.all()}
    agora_utc = datetime.now(timezone.utc)
    novos_ids = []
    
    for item in dados:
        chave_item = normalizar_chave_duplicata(item['titulo'])
        if chave_item not in chaves_banco:
            score_inicial = calcular_score_ml(item['titulo'], item['categorias_list'], agora_utc, {})
            
            noticia = Noticia(
                titulo=item['titulo'],
                fonte=item['fonte'],
                pais=item['pais'],
                link=item['link'],
                categorias=item['categorias'],
                score=score_inicial,
                data_coleta=agora_utc
            )
            db.session.add(noticia)
            db.session.flush()  # Gera o ID antes do commit
            novos_ids.append(noticia.id)
            chaves_banco.add(chave_item)
            
    db.session.commit()
    
    # Guarda os IDs da varredura atual na sessão HTTP
    session['ultimo_lote_ids'] = novos_ids if novos_ids else [n.id for n in Noticia.query.order_by(Noticia.id.desc()).limit(15).all()]
    
    return redirect(url_for('main.dashboard'))

@main_bp.route('/api/chat', methods=['POST'])
def chat_api():
    dados = request.get_json() or {}
    mensagem_usuario = dados.get('message', '').strip()

    if not mensagem_usuario or len(mensagem_usuario) < 2:
        return jsonify({'response': 'Por favor, digite uma pergunta válida.'}), 400

    msg_lower = mensagem_usuario.lower()

    # 1. Tratamento de Intenções de Ajuda
    termos_ajuda = ['o que posso', 'como funciona', 'ajuda', 'help', 'o que perguntar', 'quem e voce']
    if any(termo in msg_lower for termo in termos_ajuda):
        return jsonify({
            'response': (
                "🤖 **Como posso ajudar:**\n\n"
                "Sou um assistente de inteligência geopolítica. Você pode me perguntar sobre temas presentes nas notícias recentes, como:\n\n"
                "• **Países:** *'O que aconteceu no Irã?'* ou *'Notícias da Espanha'*\n"
                "• **Conflitos e Crises:** *'Ucrânia'*, *'Guerra'*, *'Ataques'*\n"
                "• **Economia & Líderes:** *'Petróleo'*, *'Inflação'*, *'Trump'*\n\n"
                "💡 *Dica: Clique no botão **Disparar Ingestão (Sync DB)** para atualizar a base de notícias.*"
            )
        })

    # 2. Recupera as notícias ativas das últimas 24h
    limite_tempo = datetime.now(timezone.utc) - timedelta(hours=24)
    noticias_db = Noticia.query.filter(Noticia.data_coleta >= limite_tempo).all()
    
    if not noticias_db:
        noticias_db = Noticia.query.order_by(Noticia.data_coleta.desc()).limit(50).all()

    documentos = [n.to_dict() for n in noticias_db]

    if not documentos:
        return jsonify({'response': 'A base de dados está vazia no momento. Clique em **Disparar Ingestão (Sync DB)** no topo do painel.'})

    # 3. Trata apenas pedidos explícitos de panorama geral
    frases_genericas = ['resumo geral', 'principais noticias', 'panorama global', 'resumo do dia', 'noticias do mundo']
    eh_generica = any(f in msg_lower for f in frases_genericas)

    if eh_generica:
        destaques = sorted(documentos, key=lambda x: x['score'], reverse=True)[:3]
        resposta = "🤖 **Destaques Geopolíticos Mais Relevantes Hoje:**\n\n"
        for idx, noticia in enumerate(destaques, 1):
            raw_link = noticia.get('link', '')
            link_final = f"[Acessar matéria no {noticia['fonte']}]({raw_link})" if raw_link.startswith(('http://', 'https://')) else "*Link indisponível*"
            resposta += f"{idx}. **[{noticia['fonte']}]** {noticia['titulo']}\n   🔗 {link_final}\n\n"
        return jsonify({'response': resposta})

    # 4. Executa a Busca Semântica via Subwords (Char N-grams)
    matches = ml_engine.buscar_similares(mensagem_usuario, documentos, top_k=3)

    if not matches:
        return jsonify({
            'response': f'Não encontrei matérias recentes com relevância semântica sobre "{mensagem_usuario}". Tente sincronizar novas notícias no botão **Sync DB**.'
        })

    # 5. Monta a resposta RAG com links válidos
    resposta = f"🤖 **Análise Semântica (top {len(matches)} correspondências):**\n\n"
    for idx, item in enumerate(matches, 1):
        noticia = item['noticia']
        score_pct = int(item['similarity_score'] * 100)
        raw_link = noticia.get('link', '')
        
        if raw_link and raw_link.startswith(('http://', 'https://')):
            link_final = f"[Acessar matéria no {noticia['fonte']}]({raw_link})"
        else:
            link_final = "*Link indisponível no portal de origem*"

        resposta += f"{idx}. **[{noticia['fonte']}]** {noticia['titulo']}\n"
        resposta += f"   📊 Relevância Semântica: {score_pct}%\n"
        resposta += f"   🔗 {link_final}\n\n"

    return jsonify({'response': resposta})