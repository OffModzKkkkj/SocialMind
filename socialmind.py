#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  SocialMind v5 — Analisador de Redes Sociais sem API key        ║
║  Plataformas: Instagram · YouTube · TikTok                      ║
╠══════════════════════════════════════════════════════════════════╣
║  Instalar:  pip install flask requests beautifulsoup4           ║
║  Rodar:     python socialmind.py                                ║
║  Acesso:    http://localhost:5000                               ║
╚══════════════════════════════════════════════════════════════════╝
"""
import json, sqlite3, re, math, time, os
from datetime import datetime
from collections import Counter
from pathlib import Path

import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, request, jsonify, redirect, url_for, Response

# ════════════════════════════════════════════════════════════
# DATABASE
# ════════════════════════════════════════════════════════════

DB_PATH = str(Path(__file__).parent / 'socialmind.db')

import sqlite3
import json
import os
from datetime import datetime

# DB_PATH já definido acima

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            platform TEXT NOT NULL,
            created_at TEXT NOT NULL,
            data TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_analysis(username, platform, data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO analyses (username, platform, created_at, data) VALUES (?, ?, ?, ?)",
        (username, platform, datetime.now().isoformat(), json.dumps(data, ensure_ascii=False))
    )
    analysis_id = c.lastrowid
    conn.commit()
    conn.close()
    return analysis_id

def get_history(limit=20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, username, platform, created_at FROM analyses ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "platform": r[2], "created_at": r[3]} for r in rows]

def get_analysis_by_id(analysis_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, platform, created_at, data FROM analyses WHERE id=?", (analysis_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    d = json.loads(row[4])
    d["id"] = row[0]
    d["created_at"] = row[3]
    return d


# ════════════════════════════════════════════════════════════
# ANALYZER
# ════════════════════════════════════════════════════════════

"""
Motor de análise — sem IA externa, sem API key.
Algoritmos de pontuação, heurísticas, análise estatística leve.
Otimizado para Termux / Redmi 13C (8GB RAM).
"""
from datetime import datetime
from collections import Counter
import re, math

# ─────────────────────────────────────────────
# DETECÇÃO DE NICHO / TEMA DO PERFIL
# ─────────────────────────────────────────────
NICHE_KEYWORDS = {
    "fitness": ["fitness","academia","treino","musculação","workout","gym","suplemento","emagrecimento","dieta","crossfit","corrida","hiit","proteina","bulking","cutting"],
    "gaming": ["game","gamer","gameplay","fps","rpg","stream","twitch","minecraft","free fire","valorant","lol","cs2","pubg","xbox","playstation","nintendo"],
    "gastronomia": ["receita","comida","culinária","chef","cozinha","gastronomia","food","bolo","doce","restaurante","hamburguer","pizza","vegan","saudável","nutrição"],
    "moda": ["moda","fashion","estilo","look","outfit","roupa","tendencia","ootd","streetwear","luxo","bolsa","sapato","grife","styling"],
    "viagem": ["viagem","travel","destino","turismo","mochilão","passagem","hotel","praia","montanha","voo","vistos","roteiro","férias"],
    "negócios": ["negócio","empreendedorismo","startup","marketing","vendas","renda","lucro","investimento","coaching","mentoria","gestor","ceo","freelancer"],
    "educação": ["educação","estudo","concurso","vestibular","enem","dica","aprender","curso","aula","escola","faculdade","conhecimento","resumo"],
    "música": ["música","musica","beat","instrumental","rap","funk","sertanejo","pop","rock","produção musical","letra","sample","dj","cantora","cantor"],
    "arte": ["arte","ilustração","desenho","pintura","digital art","sketchbook","aquarela","artista","criação","portfólio"],
    "comédia": ["humor","comédia","meme","engraçado","piada","esquete","stand up","paródia","viral","zuera"],
    "tecnologia": ["tech","tecnologia","programação","código","developer","python","javascript","app","ia","inteligência artificial","robô","android","ios","linux"],
    "beleza": ["beleza","makeup","maquiagem","skincare","cabelo","unhas","salão","estética","cuidados","rotina","hidratação"],
    "lifestyle": ["lifestyle","rotina","dia a dia","vlog","família","relacionamento","motivação","autoajuda","bem estar","mindset","produtividade"],
    "pets": ["pet","cachorro","gato","animal","dog","cat","adoção","veterinário","raça","filhote","tutores"],
    "finanças": ["finanças","investimento","bolsa","ação","cripto","bitcoin","renda passiva","economia","orçamento","dívida","poupança"],
}

def detect_niche(raw):
    texts = []
    texts.append(raw.get("bio", "") or "")
    texts.append(raw.get("name", "") or "")
    for p in raw.get("posts", raw.get("videos", []))[:10]:
        texts.append(p.get("description", "") or "")
        texts.append(p.get("title", "") or "")
        texts.extend(p.get("hashtags_found", []))

    full_text = " ".join(texts).lower()
    full_text = re.sub(r"[^\w\s]", " ", full_text)

    scores = {}
    for niche, keywords in NICHE_KEYWORDS.items():
        score = 0
        for kw in keywords:
            # Usa delimitadores de palavra — evita "ia" dar match em "inicianteop"
            # (?<!\w) = não precedido de letra/número; (?!\w) = não seguido
            pattern = r"(?<!\w)" + re.escape(kw) + r"(?!\w)"
            score += len(re.findall(pattern, full_text))
        if score > 0:
            scores[niche] = score

    if not scores:
        return {"primary": "Indefinido", "secondary": [], "confidence": 0,
                "tip": "Adicione palavras do seu nicho na bio e legendas para o algoritmo te categorizar corretamente."}

    sorted_niches = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_niches[0][0].title()
    secondary = [n.title() for n, _ in sorted_niches[1:3]]
    total = sum(scores.values())
    confidence = min(100, int((sorted_niches[0][1] / total) * 100)) if total > 0 else 0

    return {
        "primary": primary,
        "secondary": secondary,
        "confidence": confidence,
        "tip": _niche_tip(sorted_niches[0][0]),
    }

def _niche_tip(niche):
    tips = {
        "fitness": "Nichos de fitness são altamente competitivos — encontre um sub-nicho: 'fitness para iniciantes +40' converte mais que 'fitness' genérico.",
        "gaming": "Foque em 1-2 jogos no início. Canais generalistas crescem 3x mais devagar que especializados.",
        "gastronomia": "Receitas rápidas (<60s) explodem no TikTok e Reels. Mostre o prato final nos primeiros 2 segundos.",
        "moda": "Conteúdo de 'como montar look com X peças' tem CTR 40% maior que simples fotos de look.",
        "viagem": "Dicas práticas ('voo barato para X') crescem mais rápido que vlogs. Misture os dois formatos.",
        "negócios": "Prova social é tudo nesse nicho. Mostre resultados reais, mesmo que pequenos.",
        "educação": "Conteúdo de 'resumo em 60 segundos' domina o TikTok educacional — adapte isso ao seu assunto.",
        "música": "Bastidores e process content (como fiz essa beat) têm 2x mais engajamento que o produto final.",
        "arte": "Time-lapse do processo artístico viraliza muito mais que a obra final — mostre a jornada.",
        "comédia": "Consistência de formato é crucial. Crie uma série recorrente com personagem/situação fixa.",
        "tecnologia": "Tutoriais 'como fazer X em Y minutos' dominam o YouTube Tech. Seja específico no título.",
        "beleza": "Reviews honestos (positivos E negativos) constroem confiança e têm mais compartilhamentos.",
        "lifestyle": "A autenticidade vende mais que a perfeição. Mostre os bastidores reais.",
        "pets": "Compilações de comportamentos engraçados têm o maior potencial viral desse nicho.",
        "finanças": "Conteúdo de 'errei e aprendi' tem engajamento 3x maior que dicas de sucesso.",
    }
    return tips.get(niche, "Especialize seu conteúdo para se tornar referência em um sub-nicho específico.")

# ─────────────────────────────────────────────
# ESTIMATIVA DE CRESCIMENTO COM CENÁRIOS
# ─────────────────────────────────────────────
def estimate_growth(raw, platform, freq_analysis):
    followers = int(raw.get("followers") or raw.get("channel", {}).get("subscribers") or 0)
    posts_per_week = freq_analysis.get("posts_per_week", 1) or 1

    milestones = _next_milestones(followers)
    scenarios = {}

    for scenario_name, config in _scenarios(platform).items():
        scenario_weeks = []
        for milestone in milestones:
            weeks = _weeks_to_milestone(followers, milestone, config, platform)
            scenario_weeks.append({
                "milestone": milestone,
                "milestone_fmt": _fmt_num(milestone),
                "weeks": weeks,
                "months": round(weeks / 4.3, 1),
                "label": _milestone_label(milestone),
            })
        scenarios[scenario_name] = {
            "label": config["label"],
            "description": config["description"],
            "actions": config["actions"],
            "weekly_growth_rate": config["weekly_growth_rate"],
            "milestones": scenario_weeks,
            "color": config["color"],
            "emoji": config["emoji"],
        }

    return {
        "current_followers": followers,
        "current_followers_fmt": _fmt_num(followers),
        "scenarios": scenarios,
        "key_insight": _growth_insight(followers, posts_per_week, platform),
    }

def _next_milestones(current):
    checkpoints = [100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]
    return [m for m in checkpoints if m > current][:4]

def _scenarios(platform):
    base = {
        "pessimista": {
            "label": "Ritmo Atual",
            "description": "Continuando exatamente como está, sem mudanças.",
            "actions": ["Manter frequência atual", "Sem otimizações", "Sem estratégia de hashtag"],
            "weekly_growth_rate": 0.005,
            "color": "#FF6B6B",
            "emoji": "😴",
        },
        "moderado": {
            "label": "Melhorando",
            "description": "Aplicando boas práticas básicas de forma consistente.",
            "actions": ["Postar 5x por semana", "Responder comentários", "Usar hashtags estratégicas", "Interagir 30min/dia com o nicho"],
            "weekly_growth_rate": 0.025,
            "color": "#FFB347",
            "emoji": "📈",
        },
        "agressivo": {
            "label": "Modo Beast",
            "description": "Aplicando TUDO: frequência máxima + estratégia + colaborações.",
            "actions": ["Postar diariamente (Reels/Shorts/TikToks)", "Colaborações semanais", "Trends + nicho + CTR otimizado", "Lives semanais", "Engajamento ativo 1h/dia"],
            "weekly_growth_rate": 0.08,
            "color": "#90EE90",
            "emoji": "🚀",
        },
    }
    # Ajuste por plataforma
    if platform == "tiktok":
        base["agressivo"]["weekly_growth_rate"] = 0.20  # TikTok cresce muito mais rápido
        base["moderado"]["weekly_growth_rate"] = 0.06
    elif platform == "youtube":
        base["agressivo"]["weekly_growth_rate"] = 0.05
        base["moderado"]["weekly_growth_rate"] = 0.015
    return base

def _weeks_to_milestone(current, target, config, platform):
    rate = config["weekly_growth_rate"]
    if current == 0:
        current = 1
    if rate == 0:
        return 9999
    # Crescimento composto
    weeks = math.log(target / current) / math.log(1 + rate)
    return max(1, round(weeks))

def _milestone_label(n):
    labels = {
        100: "Primeira centena 🌱",
        500: "500 seguidores 🌿",
        1000: "1K — credibilidade 🎯",
        5000: "5K — nano creator",
        10000: "10K — desbloqueios 🔓",
        50000: "50K — micro creator ⭐",
        100000: "100K — monetização 💰",
        500000: "500K — referência 🏆",
        1000000: "1M — mega creator 👑",
    }
    return labels.get(n, f"{_fmt_num(n)} seguidores")

def _growth_insight(followers, posts_per_week, platform):
    if posts_per_week < 1:
        return "Seu maior problema não é estratégia — é frequência. Poste mais e os resultados vêm."
    if followers < 100:
        return "Fase de 0 a 1K é a mais dura. Foque 100% em qualidade e consistência, não em número."
    if followers < 1000:
        return "Você está na zona de crescimento mais lento. 1K é o divisor — depois fica mais fácil."
    if followers < 10000:
        return "Collaborações com contas do mesmo tamanho aceleram muito nessa fase. Busque parcerias."
    return "Sua conta tem tração. Agora é otimizar: CTR de thumbnail/capa e retenção são os alavancadores."

# ─────────────────────────────────────────────
# AUTOMAÇÕES SEM API KEY
# ─────────────────────────────────────────────
def get_automations(platform, niche):
    return {
        "intro": "Todas essas automações são 100% gratuitas — sem API key, sem cartão de crédito.",
        "chatgpt_prompts": _chatgpt_prompts(platform, niche),
        "local_scripts": _local_python_scripts(platform),
        "free_tools": _free_tools(platform),
        "weekly_workflow": _weekly_workflow(platform),
    }

def _chatgpt_prompts(platform, niche):
    niche_lower = niche.lower() if niche != "Indefinido" else "lifestyle"
    return [
        {
            "title": "Gerar 30 ideias de conteúdo",
            "tool": "ChatGPT (chat.openai.com) — GRÁTIS",
            "prompt": f"""Você é um especialista em criação de conteúdo para {platform}.
Gere 30 ideias de conteúdo para o nicho de {niche_lower} que:
- Tenham alto potencial viral
- Sejam fáceis de produzir com celular
- Misturem formatos: educativo, entretenimento e pessoal
- Incluam sugestão de hashtags para cada ideia
Formato: número, título chamativo, formato (reel/carrossel/story), hashtags sugeridas.""",
            "tip": "Copie o prompt acima → cole no ChatGPT → salve as ideias num bloco de notas.",
        },
        {
            "title": "Escrever legenda com gancho + CTA",
            "tool": "Claude.ai (claude.ai) — GRÁTIS",
            "prompt": f"""Escreva uma legenda para {platform} sobre [DESCREVA SEU CONTEÚDO AQUI].

Regras:
- Linha 1: gancho que pare o scroll (máx 10 palavras)
- Corpo: 3-5 linhas conversacionais, como se fosse um amigo falando
- Final: pergunta que incentiva comentário
- Hashtags: 5-8 hashtags do nicho {niche_lower}, misturando tamanhos
- Tom: autêntico, sem parecer forçado

Gere 3 versões diferentes.""",
            "tip": "Claude é melhor que ChatGPT para textos criativos e é 100% gratuito.",
        },
        {
            "title": "Analisar por que um post não performou",
            "tool": "ChatGPT (chat.openai.com) — GRÁTIS",
            "prompt": f"""Analise por que esse post de {platform} não performou bem:

Plataforma: {platform}
Nicho: {niche_lower}
Meus dados: [COLE AQUI: seguidores, curtidas, comentários, alcance]
Thumbnail/capa: [DESCREVA]
Legenda: [COLE A LEGENDA]
Horário de postagem: [EX: sábado 15h]
Hashtags usadas: [COLE]

Me dê:
1. Os 3 maiores erros cometidos
2. Como corrigir cada um
3. Versão melhorada do título/legenda
4. Melhor horário para repostar esse conteúdo""",
            "tip": "Use esse prompt TODA vez que um post decepcionante — vire o aprendizado em estratégia.",
        },
        {
            "title": "Criar roteiro de vídeo viral",
            "tool": "Gemini (gemini.google.com) — GRÁTIS",
            "prompt": f"""Crie um roteiro completo para um vídeo de {platform} sobre [SEU TEMA].

Nicho: {niche_lower}
Duração alvo: [EX: 30 segundos / 3 minutos]

Formato do roteiro:
🎬 GANCHO (primeiros 3s): [frase ou ação exata]
📖 CORPO: [divida em cenas de 5-10 segundos]
🔚 CTA FINAL: [o que pedir ao espectador]
🎵 SUGESTÃO DE SOM: [tipo de música/som]
📝 LEGENDA: [legenda pronta para copiar]
#️⃣ HASHTAGS: [10 hashtags estratégicas]""",
            "tip": "Gemini é gratuito e conectado com Google — bom para pesquisar trends atuais.",
        },
        {
            "title": "Montar calendário editorial de 30 dias",
            "tool": "ChatGPT (chat.openai.com) — GRÁTIS",
            "prompt": f"""Monte um calendário editorial de 30 dias para {platform}, nicho: {niche_lower}.

Contexto:
- Posso postar [X] vezes por semana
- Tenho [SEUS RECURSOS: celular, iluminação X, etc.]
- Meu objetivo: [EX: chegar em 1000 seguidores]
- Meu estilo: [EX: educativo, humor, motivacional]

Para cada dia inclua:
- Formato (reel, carrossel, story, live)
- Tema/título sugerido
- Nível de dificuldade (fácil/médio)
- Melhor horário para postar
Organize em tabela.""",
            "tip": "Salve o calendário no Google Keep — funciona offline no celular.",
        },
    ]

def _local_python_scripts(platform):
    scripts = [
        {
            "title": "Agendador de lembretes de postagem",
            "description": "Manda notificação no seu Termux na hora certa de postar",
            "filename": "lembrete_post.py",
            "code": """#!/usr/bin/env python3
# Rode com: python3 lembrete_post.py
# Para agendar no cron do Termux: crontab -e
# Adicione: 0 19 * * * python3 /caminho/lembrete_post.py

import subprocess
import datetime

HORARIOS = {
    0: "19:00",  # Segunda
    1: "19:00",  # Terça
    2: "18:00",  # Quarta
    3: "19:00",  # Quinta
    4: "18:00",  # Sexta
    5: "11:00",  # Sábado
    6: "11:00",  # Domingo
}

MENSAGENS = [
    "🎬 Hora de postar! Seu público está esperando.",
    "📱 Consistência é rei. Hora do conteúdo!",
    "🔥 Não deixe o algoritmo te esquecer. Poste agora!",
    "⚡ Seus concorrentes estão postando. E você?",
]

now = datetime.datetime.now()
dia = now.weekday()
msg = MENSAGENS[dia % len(MENSAGENS)]

# Notificação no Termux (instale: pkg install termux-api)
subprocess.run(["termux-notification",
    "--title", "SocialMind — Hora de Postar!",
    "--content", msg,
    "--sound"])

print(f"[{now.strftime('%H:%M')}] Lembrete enviado: {msg}")
""",
        },
        {
            "title": "Rastreador de crescimento diário",
            "description": "Salva seus dados de seguidores todo dia e gera gráfico de crescimento",
            "filename": "rastreador.py",
            "code": """#!/usr/bin/env python3
# Rode todo dia: python3 rastreador.py
# Adicione ao cron: 0 20 * * * python3 /caminho/rastreador.py

import sqlite3, datetime, os

DB = os.path.expanduser("~/crescimento.db")

def setup():
    conn = sqlite3.connect(DB)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS dados (
            data TEXT, plataforma TEXT,
            seguidores INTEGER, posts INTEGER,
            nota TEXT
        )
    ''')
    conn.commit()
    conn.close()

def registrar(plataforma, seguidores, posts, nota=""):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO dados VALUES (?,?,?,?,?)",
        (datetime.date.today().isoformat(), plataforma, seguidores, posts, nota))
    conn.commit()
    conn.close()
    print(f"✅ Registrado: {plataforma} — {seguidores} seguidores")

def mostrar_progresso(plataforma):
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT data, seguidores FROM dados WHERE plataforma=? ORDER BY data",
        (plataforma,)
    ).fetchall()
    conn.close()
    if len(rows) < 2:
        print("Sem dados suficientes ainda.")
        return
    print(f"\\n📊 Progresso — {plataforma}")
    print("-" * 30)
    for i, (data, seg) in enumerate(rows):
        diff = seg - rows[i-1][1] if i > 0 else 0
        sinal = "+" if diff >= 0 else ""
        print(f"{data}: {seg:,} seguidores  ({sinal}{diff})")

if __name__ == "__main__":
    setup()
    plataforma = input("Plataforma (instagram/youtube/tiktok): ").strip()
    seguidores = int(input("Quantos seguidores hoje? ").strip())
    posts = int(input("Quantos posts/vídeos hoje? ").strip())
    nota = input("Nota do dia (opcional): ").strip()
    registrar(plataforma, seguidores, posts, nota)
    mostrar_progresso(plataforma)
""",
        },
        {
            "title": "Gerador de hashtags por nicho (offline)",
            "description": "Sugere combinações de hashtags estratégicas sem precisar de internet",
            "filename": "hashtags.py",
            "code": r"""#!/usr/bin/env python3
# Uso: python3 hashtags.py

import random

BANCO = {
    "fitness": {
        "gigante": ["#fitness","#treino","#gym","#workout","#academia"],
        "grande":  ["#treinofuncional","#musculacao","#emagrecimento","#dieta"],
        "medio":   ["#treinodemanha","#fitnessmotivation","#gymlife","#proteina"],
        "pequeno": ["#treinoemcasa","#fitnessbrasil","#iniciante"],
        "micro":   ["#treinoparainicinates","#fitnessdodia"],
    },
    "gaming": {
        "gigante": ["#gaming","#gamer","#gameplay","#game"],
        "grande":  ["#freefire","#valorant","#minecraft","#twitch"],
        "medio":   ["#gamerbrasil","#gameplaypc","#jogos"],
        "pequeno": ["#gamerbrasileiro","#pcgaming"],
        "micro":   ["#gamercasual","#jogandocomamigos"],
    },
    "gastronomia": {
        "gigante": ["#receita","#comida","#food","#culinaria"],
        "grande":  ["#receitafacil","#comidasaudavel","#foodporn"],
        "medio":   ["#receitarapida","#cozinhando","#foodblogger"],
        "pequeno": ["#receitacaseira","#comidasimples"],
        "micro":   ["#receitadodia","#cozinhafacil"],
    },
}

def gerar_mix(nicho, plataforma="instagram"):
    nicho = nicho.lower()
    if nicho not in BANCO:
        print(f"Nicho '{nicho}' não encontrado. Disponíveis: {', '.join(BANCO.keys())}")
        return

    tags = BANCO[nicho]
    limites = {"instagram": 10, "tiktok": 5, "youtube": 8}
    total = limites.get(plataforma, 10)

    mix = (
        random.sample(tags["gigante"], min(1, len(tags["gigante"]))) +
        random.sample(tags["grande"],  min(2, len(tags["grande"])))  +
        random.sample(tags["medio"],   min(3, len(tags["medio"])))   +
        random.sample(tags["pequeno"], min(2, len(tags["pequeno"]))) +
        random.sample(tags["micro"],   min(2, len(tags["micro"])))
    )[:total]

    print(f"\n🏷️  Mix de hashtags — {nicho} / {plataforma}:")
    print(" ".join(mix))
    print(f"\n📋 Copie e cole direto na legenda!")

if __name__ == "__main__":
    nicho = input("Seu nicho: ").strip()
    plataforma = input("Plataforma (instagram/tiktok/youtube): ").strip()
    gerar_mix(nicho, plataforma)
""",
        },
    ]
    return scripts

def _free_tools(platform):
    return [
        {
            "name": "ChatGPT (chat.openai.com)",
            "preco": "GRÁTIS",
            "uso": "Gerar legendas, roteiros, ideias, análise de conteúdo",
            "como_usar": "Acesse pelo navegador do celular — sem app, sem conta paga",
        },
        {
            "name": "Claude.ai (claude.ai)",
            "preco": "GRÁTIS",
            "uso": "Melhor para textos longos e criativos — legendas, bio, carrosséis",
            "como_usar": "Crie conta gratuita, use direto no navegador",
        },
        {
            "name": "Gemini (gemini.google.com)",
            "preco": "GRÁTIS",
            "uso": "Roteiros, ideias de trends, pesquisa de concorrentes",
            "como_usar": "Login com conta Google, sem limite generoso no free",
        },
        {
            "name": "CapCut (app)",
            "preco": "GRÁTIS",
            "uso": "Edição de vídeos com IA integrada — legendas automáticas, transições",
            "como_usar": "Baixe da Play Store — IA embutida não precisa de conta paga",
        },
        {
            "name": "Canva (canva.com)",
            "preco": "GRÁTIS (versão básica)",
            "uso": "Thumbnails, carrosséis, stories — templates prontos",
            "como_usar": "Conta gratuita dá acesso a milhares de templates",
        },
        {
            "name": "Later / Buffer (plano free)",
            "preco": "GRÁTIS (limitado)",
            "uso": "Agendar posts — programa e esquece",
            "como_usar": "Buffer gratuito: 3 canais, 10 posts agendados por vez",
        },
        {
            "name": "Cron do Termux",
            "preco": "GRÁTIS (já vem no Termux)",
            "uso": "Automação local — rodar scripts em horários específicos",
            "como_usar": "pkg install cronie && crond && crontab -e",
        },
    ]

def _weekly_workflow(platform):
    return {
        "title": "Fluxo semanal automatizado (sem pagar nada)",
        "steps": [
            {
                "dia": "Segunda-feira",
                "tarefa": "Planejamento",
                "acao": "Abra o ChatGPT → use o prompt 'Gerar 30 ideias' → escolha 7 ideias para a semana",
                "tempo": "20 min",
            },
            {
                "dia": "Terça a Quinta",
                "tarefa": "Produção em lote",
                "acao": "Grave 2-3 vídeos de uma vez. Use Claude.ai para escrever legendas de todos.",
                "tempo": "1h por dia",
            },
            {
                "dia": "Sexta-feira",
                "tarefa": "Agendamento",
                "acao": "Agende os posts no Buffer (gratuito). Gere hashtags com hashtags.py no Termux.",
                "tempo": "30 min",
            },
            {
                "dia": "Domingo",
                "tarefa": "Análise",
                "acao": "Rode o SocialMind → registre no rastreador.py → use ChatGPT para analisar o que funcionou.",
                "tempo": "20 min",
            },
        ],
    }

# ─────────────────────────────────────────────
# ANÁLISE GERAL DA CONTA
# ─────────────────────────────────────────────
def analyze_account(raw, platform):
    niche_info = detect_niche(raw)
    if platform == "instagram":
        result = _analyze_instagram(raw)
    elif platform == "youtube":
        result = _analyze_youtube(raw)
    elif platform == "tiktok":
        result = _analyze_tiktok(raw)
    else:
        result = {}
    result["niche"] = niche_info

    # Propaga erros e notas do scraper para o resultado final
    if raw.get("error"):
        result["scrape_error"] = raw["error"]
    if raw.get("note"):
        result["scrape_note"] = raw["note"]
    if raw.get("scrape_errors"):
        result["scrape_errors"] = raw["scrape_errors"]
    result["scrape_method"] = raw.get("scrape_method", "unknown")

    freq = result.get("posting_frequency", {})
    result["growth_estimate"] = estimate_growth(raw, platform, freq)
    result["automations"] = get_automations(platform, niche_info.get("primary", "lifestyle"))
    return result

def _analyze_instagram(raw):
    followers = int(raw.get("followers") or 0)
    following = int(raw.get("following") or 0)
    posts_count = int(raw.get("posts_count") or 0)
    posts = raw.get("posts", [])
    scrape_failed = raw.get("scrape_method") == "failed" or bool(raw.get("error"))
    score = _score_account(followers, following, posts_count)
    growth_stage = _growth_stage(followers)
    engagement_rates, total_likes, total_comments = [], 0, 0
    for p in posts:
        likes, comments = p.get("likes", 0), p.get("comments", 0)
        total_likes += likes; total_comments += comments
        if followers > 0:
            rate = ((likes + comments) / followers) * 100
            engagement_rates.append(rate)
            p["engagement_rate"] = round(rate, 2)
    avg_engagement = round(sum(engagement_rates) / len(engagement_rates), 2) if engagement_rates else 0
    engagement_benchmark = _engagement_benchmark(followers, "instagram")
    timestamps = sorted([p["timestamp"] for p in posts if p.get("timestamp")], reverse=True)
    freq_analysis = _posting_frequency(timestamps, "instagram")
    top_posts = sorted(posts, key=lambda p: p.get("likes", 0) + p.get("comments", 0) * 3, reverse=True)[:3]
    problems, strengths = [], []
    if not scrape_failed:
        ratio = following / followers if followers > 0 else 999
        if ratio > 1.5: problems.append("Está seguindo muito mais pessoas do que te seguem — passa imagem de conta desesperada.")
        if avg_engagement < engagement_benchmark["min"] and followers > 0: problems.append(f"Engajamento baixo ({avg_engagement:.1f}%) para {_fmt_num(followers)} seguidores.")
        if posts_count < 9: problems.append("Portfólio pequeno — menos de 9 posts afugenta novos seguidores.")
        if freq_analysis.get("days_between_posts") and freq_analysis["days_between_posts"] > 7: problems.append(f"Postando pouco — 1x a cada {freq_analysis['days_between_posts']:.0f} dias. Algoritmo pune quem some.")
        if not raw.get("bio"): problems.append("Bio vazia — perde credibilidade e não aparece em buscas.")
    if avg_engagement > engagement_benchmark["good"] and followers > 0: strengths.append(f"Engajamento excelente ({avg_engagement:.1f}%)!")
    if followers > 1000: strengths.append(f"Base de {_fmt_num(followers)} seguidores sólida.")
    if freq_analysis.get("days_between_posts") and freq_analysis["days_between_posts"] <= 3: strengths.append("Frequência ótima de posts.")
    if raw.get("verified"): strengths.append("Conta verificada!")
    ratio = following / followers if followers > 0 else 0
    return {
        "score": score, "growth_stage": growth_stage,
        "followers": followers, "following": following, "posts_count": posts_count,
        "avg_likes": round(total_likes / len(posts), 1) if posts else 0,
        "avg_comments": round(total_comments / len(posts), 1) if posts else 0,
        "avg_engagement": avg_engagement, "engagement_benchmark": engagement_benchmark,
        "posting_frequency": freq_analysis, "top_posts": top_posts,
        "ratio_follow": round(ratio, 2), "problems": problems, "strengths": strengths,
        "data_available": not scrape_failed,
        "recommendations": _recommendations_instagram(raw, avg_engagement, freq_analysis, followers),
    }

def _analyze_youtube(raw):
    channel = raw.get("channel", {}); videos = raw.get("videos", [])
    subscribers = int(channel.get("subscribers") or 0)
    scrape_method = raw.get("scrape_method", "")
    channel_id = raw.get("channel_id")
    # Considera dados disponíveis se temos vídeos OU nome do canal diferente do username
    has_channel_data = bool(channel_id) or bool(videos) or channel.get("name", raw.get("username", "")) != raw.get("username", "")
    score = _score_account(subscribers, 0, len(videos))
    growth_stage = _growth_stage(subscribers)
    views_list = [v.get("views", 0) for v in videos if v.get("views", 0) > 0]
    avg_views = round(sum(views_list) / len(views_list)) if views_list else 0
    top_videos = sorted(videos, key=lambda v: v.get("views", 0), reverse=True)[:5]
    worst_videos = sorted(videos, key=lambda v: v.get("views", 0))[:3]
    title_patterns = _analyze_titles([v.get("title", "") for v in top_videos])
    all_hashtags = []
    for v in videos: all_hashtags.extend(v.get("hashtags_found", []))
    hashtag_freq = Counter(all_hashtags).most_common(10)
    timestamps = []
    for v in videos:
        pub = v.get("published", "")
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                timestamps.append(dt.timestamp())
            except: pass
    freq_analysis = _posting_frequency(sorted(timestamps, reverse=True), "youtube")
    problems, strengths = [], []
    if has_channel_data:
        if avg_views < subscribers * 0.05 and subscribers > 0: problems.append(f"Views ({_fmt_num(avg_views)}) abaixo de 5% dos inscritos — problema de CTR ou retenção.")
        if freq_analysis.get("days_between_posts") and freq_analysis["days_between_posts"] > 14: problems.append("Upload muito espaçado — YouTube pune inatividade.")
        if views_list and len(views_list) > 2 and max(views_list) > avg_views * 5: problems.append("Grande variação de views — conteúdo inconsistente.")
        if avg_views > 0: strengths.append(f"Média de {_fmt_num(avg_views)} views por vídeo.")
        if freq_analysis.get("days_between_posts") and freq_analysis["days_between_posts"] <= 7: strengths.append("Cadência de upload consistente.")
        if subscribers > 0: strengths.append(f"Canal com {_fmt_num(subscribers)} inscritos.")
    return {
        "score": score, "growth_stage": growth_stage, "subscribers": subscribers,
        "videos_analyzed": len(videos), "avg_views": avg_views,
        "max_views": max(views_list) if views_list else 0,
        "min_views": min(views_list) if views_list else 0,
        "top_videos": top_videos, "worst_videos": worst_videos,
        "title_patterns": title_patterns, "hashtag_frequency": hashtag_freq,
        "posting_frequency": freq_analysis, "problems": problems, "strengths": strengths,
        "data_available": has_channel_data,
        "recommendations": _recommendations_youtube(raw, avg_views, subscribers, freq_analysis),
    }

def _analyze_tiktok(raw):
    followers = int(raw.get("followers") or 0)
    following = int(raw.get("following") or 0)
    likes_total = int(raw.get("likes_total") or 0)
    videos = raw.get("videos") or []
    video_count = int(raw.get("video_count") or len(videos))
    scrape_failed = raw.get("scrape_method") == "failed" or bool(raw.get("error"))
    score = _score_account(followers, following, video_count)
    growth_stage = _growth_stage(followers)
    engagement_list = []
    for v in videos:
        views = v.get("views", 0); likes = v.get("likes", 0)
        comments = v.get("comments", 0); shares = v.get("shares", 0)
        if views > 0:
            rate = ((likes + comments + shares) / views) * 100
            v["engagement_rate"] = round(rate, 2); engagement_list.append(rate)
    avg_engagement = round(sum(engagement_list) / len(engagement_list), 2) if engagement_list else 0
    top_videos = sorted(videos, key=lambda v: v.get("views", 0), reverse=True)[:5]
    for v in top_videos: v["viral_score"] = _viral_score_tiktok(v)
    all_hashtags = []
    for v in videos: all_hashtags.extend(v.get("hashtags_found", []))
    hashtag_freq = Counter(all_hashtags).most_common(10)
    timestamps = [v.get("timestamp", 0) for v in videos if v.get("timestamp")]
    freq_analysis = _posting_frequency(sorted(timestamps, reverse=True), "tiktok")
    problems, strengths = [], []
    if not scrape_failed:
        if avg_engagement < 3 and followers > 0: problems.append(f"Engajamento baixo ({avg_engagement:.1f}%) — TikTok precisa de 3-5% mínimo.")
        if freq_analysis.get("days_between_posts") and freq_analysis["days_between_posts"] > 3: problems.append("TikTok exige ao menos 1 post por dia para crescer rápido.")
    if avg_engagement >= 5: strengths.append(f"Engajamento ótimo ({avg_engagement:.1f}%)!")
    if top_videos and top_videos[0].get("views", 0) > 10000: strengths.append(f"Melhor vídeo com {_fmt_num(top_videos[0]['views'])} views!")
    if followers > 0: strengths.append(f"Conta com {_fmt_num(followers)} seguidores.")
    return {
        "score": score, "growth_stage": growth_stage,
        "followers": followers, "following": following,
        "likes_total": likes_total, "video_count": video_count,
        "avg_engagement": avg_engagement, "top_videos": top_videos,
        "hashtag_frequency": hashtag_freq, "posting_frequency": freq_analysis,
        "problems": problems, "strengths": strengths,
        "data_available": not scrape_failed,
        "recommendations": _recommendations_tiktok(raw, avg_engagement, freq_analysis, followers),
    }

def analyze_warming(raw, platform):
    followers = int(raw.get("followers") or raw.get("channel", {}).get("subscribers") or 0)
    posts = raw.get("posts") or raw.get("videos") or []
    posts_count = int(raw.get("posts_count") or raw.get("video_count") or len(posts))
    stage = _warming_stage(followers, posts_count)
    plan = _warming_plan(stage, platform)
    return {
        "stage": stage, "stage_name": _warming_stage_name(stage),
        "stage_description": _warming_stage_description(stage),
        "daily_plan": plan,
        "do_list": _warming_dos(stage),
        "dont_list": _warming_donts(stage),
        "red_flags": _warming_red_flags(raw),
    }

def analyze_hashtag(hashtags, raw):
    results = []
    posts = raw.get("posts", raw.get("videos", []))
    for tag in hashtags:
        tag_clean = tag.lstrip("#").lower()
        usage_count = sum(1 for p in posts if tag_clean in [h.lower() for h in p.get("hashtags_found", [])])
        size_class = _classify_hashtag(tag_clean)
        results.append({
            "hashtag": f"#{tag_clean}", "size_class": size_class,
            "size_label": _size_label(size_class), "used_in_posts": usage_count,
            "recommendation": _hashtag_recommendation(size_class),
        })
    return results

# ─────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────
def _score_account(followers, following, posts):
    # Se todos os dados são zero, não há dados reais para pontuar
    if followers == 0 and following == 0 and posts == 0:
        return 0
    score = 0
    if followers >= 100000: score += 40
    elif followers >= 10000: score += 30
    elif followers >= 1000: score += 20
    elif followers >= 100: score += 10
    else: score += max(0, followers // 10)
    if posts >= 50: score += 30
    elif posts >= 20: score += 20
    elif posts >= 9: score += 10
    else: score += posts
    if following > 0:
        ratio = followers / following
        if ratio >= 2: score += 30
        elif ratio >= 1: score += 20
        elif ratio >= 0.5: score += 10
    elif followers > 0:
        # Canal/conta que não segue ninguém (ex: YouTube) — bônus de autoridade
        score += 15
    # Se following=0 e followers=0, não adiciona nada
    return min(100, score)

def _growth_stage(followers):
    if followers < 100: return {"label": "Iniciante", "color": "#FF6B6B", "next": 100}
    if followers < 1000: return {"label": "Crescendo", "color": "#FFB347", "next": 1000}
    if followers < 10000: return {"label": "Nano Creator", "color": "#87CEEB", "next": 10000}
    if followers < 100000: return {"label": "Micro Creator", "color": "#90EE90", "next": 100000}
    if followers < 1000000: return {"label": "Macro Creator", "color": "#DDA0DD", "next": 1000000}
    return {"label": "Mega Creator", "color": "#FFD700", "next": None}

def _engagement_benchmark(followers, platform):
    if platform == "instagram":
        if followers < 1000: return {"min": 5, "good": 8, "excellent": 12}
        if followers < 10000: return {"min": 3, "good": 6, "excellent": 10}
        if followers < 100000: return {"min": 1.5, "good": 3, "excellent": 6}
        return {"min": 0.5, "good": 1.5, "excellent": 3}
    if platform == "tiktok": return {"min": 3, "good": 6, "excellent": 10}
    return {"min": 1, "good": 3, "excellent": 6}

def _posting_frequency(timestamps, platform):
    if len(timestamps) < 2:
        return {"posts_per_week": 0, "days_between_posts": None, "consistency": "Dados insuficientes"}
    diffs = [(timestamps[i] - timestamps[i+1]) / 86400 for i in range(len(timestamps)-1)]
    avg_days = sum(diffs) / len(diffs)
    posts_per_week = round(7 / avg_days, 1) if avg_days > 0 else 0
    b = {"instagram": 3, "youtube": 7, "tiktok": 1}.get(platform, 3)
    consistency = "Consistente" if avg_days <= b else ("Irregular" if avg_days <= b*2 else "Inativo")
    return {"posts_per_week": posts_per_week, "days_between_posts": round(avg_days, 1), "consistency": consistency}

def _warming_stage(followers, posts_count):
    if followers == 0 and posts_count < 3: return 1
    if followers < 100: return 2
    if followers < 1000: return 3
    if followers < 10000: return 4
    return 5

def _warming_stage_name(stage):
    return {1:"Conta Nova",2:"Iniciante",3:"Crescendo",4:"Em Tração",5:"Estabelecida"}.get(stage,"")

def _warming_stage_description(stage):
    return {
        1:"Conta criada há pouco. O algoritmo ainda não te conhece.",
        2:"Fase crítica. Consistência é tudo aqui.",
        3:"Você passou da fase difícil! Agora otimize e acelere.",
        4:"Crescimento real acontecendo. Profissionalize o conteúdo.",
        5:"Conta com autoridade. Foque em monetização e parcerias.",
    }.get(stage,"")

def _warming_plan(stage, platform):
    planos = {
        "instagram": {
            1:["Dia 1-3: Complete perfil 100% — foto, bio, link. Siga 10-20 contas do nicho. NÃO poste ainda.",
               "Dia 4-7: Curta 20-30 posts/dia. Deixe 5-10 comentários genuínos. Poste 1 story.",
               "Dia 8-14: Poste seu 1º conteúdo. Continue curtindo/comentando. Responda TODOS os comentários.",
               "Semana 3-4: 1 post + 1-2 reels/semana. Use hashtags do nicho."],
            2:["Poste 3-5x/semana. Horário fixo (ex: 18h-20h).",
               "Curta 30-50 posts/dia de contas do nicho.",
               "Responda todos os comentários em até 1h após postar.",
               "Use 5-10 hashtags mistas (grandes + médias + pequenas)."],
            3:["Poste 5-7x/semana incluindo Reels diários.",
               "Analise seus top 3 posts e replique o formato.",
               "Interaja com contas maiores do nicho (comentários estratégicos)."],
            4:["Foque em Reels — motor principal de alcance.",
               "Colaborações e duetos com contas do mesmo tamanho.",
               "Stories diários com caixas de perguntas."],
            5:["Lives semanais.","Parcerias pagas.","UGC e repost de fãs."],
        },
        "youtube": {
            1:["Semana 1: Configure canal, foto, banner, descrição.",
               "Semana 2-3: Publique 2-3 vídeos piloto de teste.",
               "Semana 4: Analise retenção e ajuste o formato."],
            2:["1 vídeo/semana, mesmo horário.","Títulos com palavra-chave + gancho emocional.",
               "Shorts diários para alcance gratuito."],
            3:["2 vídeos/semana.","Cards e telas finais em todos os vídeos.",
               "Responda comentários nas primeiras 24h."],
            4:["Série de vídeos para reter inscritos.","Colaborações.","Membros do canal."],
            5:["Monetização ativa.","Patrocínios.","Produtos digitais."],
        },
        "tiktok": {
            1:["Dia 1-2: Configure perfil. Assista conteúdo do nicho por 30min.",
               "Dia 3-5: Poste 1 vídeo teste.",
               "Dia 6-7: Analise e poste mais 2."],
            2:["1-3 vídeos por dia.","Durações variadas: 7s, 15s, 30s, 60s — teste tudo.",
               "Participe de trends adaptando ao seu nicho."],
            3:["Manter 2-3 vídeos/dia.","Duets e Stitch com contas maiores.",
               "Lives de 30 min para boost do algoritmo."],
            4:["Séries e episódios.","TikTok Creator Fund.","Parcerias."],
            5:["Brand deals.","Live gifts.","Expansão para outras plataformas."],
        },
    }
    return planos.get(platform, {}).get(stage, ["Continue postando consistentemente."])

def _warming_dos(stage):
    base = [
        "Responda TODOS os comentários nas primeiras 2h após postar",
        "Interaja com contas do mesmo nicho todos os dias",
        "Mantenha horário fixo de postagem",
        "Use hashtags do seu nicho (misture tamanhos diferentes)",
        "Estude seus melhores conteúdos e replique o que funcionou",
    ]
    if stage <= 2:
        base.insert(0, "Complete 100% do perfil antes de qualquer coisa")
        base.insert(1, "Seja paciente — crescimento real leva 3-6 meses")
    return base

def _warming_donts(stage):
    donts = [
        "NÃO compre seguidores — destroem o engajamento e marcam a conta",
        "NÃO use bots ou automações de follow/unfollow — risco de ban",
        "NÃO mude o nicho de repente — confunde o algoritmo",
        "NÃO delete posts ruins — afeta o histórico",
        "NÃO poste em horários aleatórios — consistência é lei",
        "NÃO ignore comentários — cada um não respondido é alcance perdido",
    ]
    if stage == 1:
        donts.insert(0, "NÃO siga/dessiga em massa — shadowban em conta nova")
    return donts

def _warming_red_flags(raw):
    flags = []
    followers = int(raw.get("followers") or 0)
    following = int(raw.get("following") or 0)
    posts = raw.get("posts") or raw.get("videos") or []
    if following > 0 and followers / max(following, 1) < 0.3:
        flags.append("⚠️ Proporção seguindo/seguidores ruim — pode estar na lista negra do algoritmo.")
    likes = [p.get("likes", 0) for p in posts]
    if likes and max(likes) > 0 and min(likes) == 0:
        flags.append("⚠️ Posts com 0 curtidas — possível shadowban ou conteúdo rejeitado.")
    if raw.get("private"):
        flags.append("⚠️ Conta privada — impossível crescer organicamente.")
    return flags

def _analyze_titles(titles):
    all_words = []
    for t in titles: all_words.extend(re.findall(r'\b\w{4,}\b', t.lower()))
    common_words = Counter(all_words).most_common(5)
    has_numbers = sum(1 for t in titles if re.search(r'\d', t))
    has_question = sum(1 for t in titles if "?" in t)
    avg_len = round(sum(len(t) for t in titles) / len(titles)) if titles else 0
    patterns = []
    if has_numbers >= len(titles) * 0.6: patterns.append("Usa números — aumenta CTR")
    if has_question >= len(titles) * 0.4: patterns.append("Usa perguntas — gera curiosidade")
    if avg_len < 50: patterns.append(f"Títulos curtos (média {avg_len} chars) — bom para mobile")
    elif avg_len > 70: patterns.append(f"Títulos longos (média {avg_len} chars) — pode cortar em mobile")
    return {"patterns": patterns, "common_words": [w for w, _ in common_words]}

def _viral_score_tiktok(video):
    views = video.get("views", 0); likes = video.get("likes", 0)
    comments = video.get("comments", 0); shares = video.get("shares", 0)
    if views == 0: return 0
    engagement = (likes + comments * 2 + shares * 3) / views
    score = min(100, int(engagement * 1000))
    if views > 1_000_000: score = min(100, score + 30)
    elif views > 100_000: score = min(100, score + 15)
    return score

def _classify_hashtag(tag):
    if len(tag) <= 4: return "huge"
    if any(kw in tag for kw in ["fyp","viral","trending","foryou","explore","reels"]): return "huge"
    if len(tag) >= 15: return "micro"
    if len(tag) <= 7: return "large"
    return "medium"

def _size_label(size_class):
    return {"huge":"Gigante (100M+ posts) — difícil","large":"Grande (10M-100M) — difícil",
            "medium":"Média (1M-10M) — balanceada","small":"Pequena (100K-1M) — boa",
            "micro":"Micro (< 100K) — nicho, fácil"}.get(size_class,"")

def _hashtag_recommendation(size_class):
    return {"huge":"Use com moderação — post vai se perder no volume.",
            "large":"Use 1-2, mas não dependa delas.",
            "medium":"Boa escolha — equilíbrio entre alcance e competição.",
            "small":"Ótima para nichos — alto potencial de aparecer.",
            "micro":"Perfeita para comunidade específica — use sempre."}.get(size_class,"")

def _recommendations_instagram(raw, avg_engagement, freq, followers):
    recs = []
    if avg_engagement < 3: recs.append("📌 Faça perguntas nas legendas — comentários dobram seu alcance.")
    if (freq.get("days_between_posts") or 99) > 4: recs.append("📌 Aumente a frequência para pelo menos 4-5x por semana.")
    if followers < 1000: recs.append("📌 Reels crescem 3x mais rápido que fotos — priorize vídeos curtos.")
    recs.append("📌 Poste nos horários de pico: 11h-13h ou 19h-21h (horário de Brasília).")
    recs.append("📌 Stories diários — mantém você no topo da timeline.")
    return recs

def _recommendations_youtube(raw, avg_views, subscribers, freq):
    recs = []
    recs.append("📌 Thumbnail é tudo — rostos com emoção + texto em contraste alto.")
    recs.append("📌 Os primeiros 30s definem a retenção. Vai direto ao ponto.")
    if (freq.get("days_between_posts") or 99) > 10: recs.append("📌 Aumente a cadência — 1 vídeo/semana é o mínimo.")
    recs.append("📌 Use Shorts diários para alcance gratuito.")
    recs.append("📌 Títulos com 'Como fazer', 'Por que', 'X razões' têm mais cliques.")
    return recs

def _recommendations_tiktok(raw, avg_engagement, freq, followers):
    recs = []
    recs.append("📌 Hook nos primeiros 1-3 segundos — se não prende, o algoritmo para.")
    if (freq.get("days_between_posts") or 99) > 2: recs.append("📌 Poste 1-2x por dia para o algoritmo te testar em públicos novos.")
    recs.append("📌 Use o som em alta da semana — aumenta 40% a chance de cair no FYP.")
    recs.append("📌 Caption curta com pergunta — gera comentários que impulsionam o vídeo.")
    return recs

def _fmt_num(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return str(n)


# ════════════════════════════════════════════════════════════
# SCRAPER
# ════════════════════════════════════════════════════════════

"""
Scraper sem API key — usa yt-dlp (YouTube) e instaloader (Instagram).
Fallback para requests+BS4 se as libs não estiverem instaladas.
Otimizado para Termux / Android.
"""
import requests
import re
import json
import time
import itertools
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Redmi 13C) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.6367.82 Mobile Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _get(url, timeout=15):
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r
        except requests.exceptions.Timeout:
            if attempt == 2:
                raise RuntimeError(f"Timeout ao acessar {url}")
            time.sleep(1)
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"HTTP {e.response.status_code} ao acessar {url}")
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"Erro ao acessar {url}: {e}")
            time.sleep(1)


def _fmt_subscribers(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M inscritos"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K inscritos"
    return f"{n} inscritos"


# ─────────────────────────────────────────────
# YOUTUBE — usa yt-dlp (sem API key, sem login)
# ─────────────────────────────────────────────
def scrape_youtube(username_or_handle, hashtags=None):
    # FIX: captura erros de conversão do username antes de qualquer uso
    try:
        handle = username_or_handle.lstrip("@")
    except Exception:
        handle = str(username_or_handle)

    ytdlp_error = None

    # Tenta yt-dlp primeiro (melhor qualidade de dados)
    try:
        return _scrape_youtube_ytdlp(handle, hashtags)
    except ImportError:
        pass  # yt-dlp não instalado → usa fallback RSS
    except NameError as e:
        # FIX: captura NameError (username_or_handle ou outro var nao definido)
        ytdlp_error = f"NameError: {e}"
    except Exception as e:
        ytdlp_error = str(e)

    # Fallback: RSS + scraping HTML (unico ponto de retorno)
    return _scrape_youtube_rss(handle, hashtags, ytdlp_error=ytdlp_error)


def _scrape_youtube_ytdlp(handle, hashtags=None):
    """Usa yt-dlp para extrair inscritos + vídeos recentes. Sem API key."""
    import yt_dlp  # noqa

    url = f"https://www.youtube.com/@{handle}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,   # Não baixa vídeo individual — só metadados
        "playlistend": 15,      # Máximo 15 vídeos — economia de dados
        "skip_download": True,
        "ignoreerrors": True,
        "socket_timeout": 20,
        "http_headers": HEADERS,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise ValueError(f"Canal @{handle} não encontrado")

    channel_name = (
        info.get("channel") or info.get("uploader") or
        info.get("title") or handle
    )
    channel_id = info.get("channel_id") or info.get("uploader_id") or ""
    # yt-dlp retorna inscritos em channel_follower_count
    subscribers = int(info.get("channel_follower_count") or
                      info.get("subscriber_count") or 0)
    description = (info.get("description") or "")[:500]

    videos = []
    for entry in (info.get("entries") or []):
        if not entry:
            continue

        # Converte upload_date YYYYMMDD → ISO 8601
        upload_date = entry.get("upload_date") or ""
        if upload_date and len(upload_date) == 8:
            published = (
                f"{upload_date[:4]}-{upload_date[4:6]}-"
                f"{upload_date[6:8]}T00:00:00+00:00"
            )
        else:
            ts = entry.get("timestamp")
            if ts:
                published = datetime.fromtimestamp(
                    float(ts), tz=timezone.utc
                ).isoformat()
            else:
                published = ""

        title = (entry.get("title") or "")
        desc = (entry.get("description") or "")[:300]
        found_tags = re.findall(r"#(\w+)", f"{title} {desc}")

        videos.append({
            "video_id": entry.get("id") or "",
            "title": title,
            "published": published,
            "views": int(entry.get("view_count") or 0),
            "description": desc,
            "thumbnail": entry.get("thumbnail") or "",
            "url": (
                entry.get("webpage_url") or
                f"https://www.youtube.com/watch?v={entry.get('id', '')}"
            ),
            "hashtags_found": found_tags[:10],
            "type": "video",
        })

    return {
        "platform": "youtube",
        "username": username_or_handle,
        "channel_id": channel_id,
        "channel": {
            "name": channel_name,
            "subscribers": subscribers,
            "subscribers_text": _fmt_subscribers(subscribers),
            "description": description,
            "views_total": int(info.get("view_count") or 0),
        },
        "videos": videos,
        "videos_analyzed": len(videos),
        "hashtags_searched": hashtags or [],
        "scraped_at": datetime.now().isoformat(),
        "scrape_method": "yt-dlp",
    }


def _scrape_youtube_rss(handle, hashtags=None, ytdlp_error=None):
    """Fallback: RSS público do YouTube + scraping de página para inscritos."""
    channel_info = {
        "name": handle,
        "subscribers": 0,
        "subscribers_text": "",
        "description": "",
        "views_total": 0,
    }
    scrape_errors = []
    if ytdlp_error:
        scrape_errors.append(f"yt-dlp: {ytdlp_error}")

    # Resolve channel_id via scraping da página
    channel_id, page_html = _resolve_channel_id(handle)

    if page_html:
        _extract_channel_info_from_html(page_html, channel_info)
    else:
        scrape_errors.append(f"Não foi possível acessar a página do canal @{handle}")

    # RSS para lista de vídeos (gratuito, sem key)
    videos = []
    if channel_id:
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            r = _get(rss_url)
            root = ET.fromstring(r.text)
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "media": "http://search.yahoo.com/mrss/",
                "yt": "http://www.youtube.com/xml/schemas/2015",
            }
            ch_title = root.find("atom:title", ns)
            if ch_title is not None and ch_title.text:
                channel_info["name"] = ch_title.text

            for entry in root.findall("atom:entry", ns)[:15]:
                vid_id_el = entry.find("yt:videoId", ns)
                title_el = entry.find("atom:title", ns)
                pub_el = entry.find("atom:published", ns)
                # RSS usa <media:statistics views="N"/> (atributo "views")
                stats_el = entry.find(".//media:statistics", ns)
                desc_el = entry.find(".//media:description", ns)
                thumb_el = entry.find(".//media:thumbnail", ns)

                video_id = (vid_id_el.text or "") if vid_id_el is not None else ""
                title = (title_el.text or "") if title_el is not None else ""
                published = (pub_el.text or "") if pub_el is not None else ""
                views = int(stats_el.attrib.get("views", 0)) if stats_el is not None else 0
                desc = (desc_el.text or "") if desc_el is not None else ""
                thumb = thumb_el.attrib.get("url", "") if thumb_el is not None else ""
                found_tags = re.findall(r"#(\w+)", f"{title} {desc}")

                videos.append({
                    "video_id": video_id,
                    "title": title,
                    "published": published,
                    "views": views,
                    "description": desc[:300],
                    "thumbnail": thumb,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "hashtags_found": found_tags[:10],
                    "type": "video",
                })
        except Exception as e:
            scrape_errors.append(f"Erro no RSS: {e}")
    else:
        scrape_errors.append(
            f"Canal '@{handle}' não encontrado. "
            "Instale yt-dlp para melhor compatibilidade: pip install yt-dlp"
        )

    result = {
        "platform": "youtube",
        "username": handle,
        "channel_id": channel_id,
        "channel": channel_info,
        "videos": videos,
        "videos_analyzed": len(videos),
        "hashtags_searched": hashtags or [],
        "scraped_at": datetime.now().isoformat(),
        "scrape_method": "rss+html",
    }
    if scrape_errors:
        result["scrape_errors"] = scrape_errors
    return result


def _resolve_channel_id(handle):
    """Tenta múltiplas URLs para encontrar o channel ID. Retorna (id, html)."""
    patterns = [
        r'"channelId":"(UC[a-zA-Z0-9_-]{22})"',
        r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
        r'"browseId":"(UC[a-zA-Z0-9_-]{22})"',
        r'youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})',
        r'"(UC[a-zA-Z0-9_-]{22})"',
    ]
    for url in [
        f"https://www.youtube.com/@{handle}",
        f"https://www.youtube.com/c/{handle}",
        f"https://www.youtube.com/user/{handle}",
    ]:
        try:
            r = _get(url)
            html = r.text
            for pat in patterns:
                m = re.search(pat, html)
                if m:
                    cid = m.group(1)
                    if cid.startswith("UC") and len(cid) == 24:
                        return cid, html
            if "ytInitialData" in html:
                return None, html
        except Exception:
            continue
    return None, None


def _extract_channel_info_from_html(html, info):
    """Extrai nome, inscritos e descrição do HTML da página do canal."""
    subs_patterns = [
        r'"subscriberCountText":\{"simpleText":"([^"]+)"',
        r'"subscriberCountText":\{[^}]*"simpleText":"([^"]+)"',
        r'"subscribers":\{"simpleText":"([^"]+)"',
        r'"subscriberCount":"(\d+)"',
    ]
    for pat in subs_patterns:
        m = re.search(pat, html)
        if m:
            raw = m.group(1)
            parsed = _parse_number(raw)
            if parsed > 0:
                info["subscribers"] = parsed
                info["subscribers_text"] = raw
                break

    for pat in [
        r'"channelMetadataRenderer":\{"title":"([^"]+)"',
        r'<title>([^<]+) - YouTube</title>',
    ]:
        m = re.search(pat, html)
        if m:
            name = m.group(1).replace(" - YouTube", "").strip()
            if name:
                info["name"] = name
                break

    m = re.search(r'"description":\{"simpleText":"([^"]{10,500})"', html)
    if m:
        info["description"] = m.group(1)


# ─────────────────────────────────────────────
# INSTAGRAM — usa instaloader (sem login, perfis públicos)
# ─────────────────────────────────────────────
def scrape_instagram(username, hashtags=None):
    username = username.lstrip("@")

    # Tenta instaloader primeiro
    try:
        return _scrape_instagram_instaloader(username, hashtags)
    except ImportError:
        pass
    except Exception as e:
        return _scrape_instagram_fallback(username, hashtags, error=str(e))

    return _scrape_instagram_fallback(username, hashtags)


def _scrape_instagram_instaloader(username, hashtags=None):
    """Usa instaloader para scraping sem login de perfis públicos."""
    import instaloader  # noqa

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        request_timeout=20,
    )

    profile = instaloader.Profile.from_username(L.context, username)

    posts = []
    for post in itertools.islice(profile.get_posts(), 12):
        captions = post.caption or ""
        tags = list(post.caption_hashtags) if captions else []
        posts.append({
            "shortcode": post.shortcode,
            "likes": post.likes,
            "comments": post.comments,
            "timestamp": int(post.date_utc.timestamp()),
            "url": f"https://www.instagram.com/p/{post.shortcode}/",
            "type": "video" if post.is_video else "post",
            "hashtags_found": tags[:10],
        })

    return {
        "platform": "instagram",
        "username": username,
        "name": profile.full_name or username,
        "bio": profile.biography or "",
        "followers": profile.followers,
        "following": profile.followees,
        "posts_count": profile.mediacount,
        "reels_count": sum(1 for p in posts if p["type"] == "video"),
        "verified": profile.is_verified,
        "private": profile.is_private,
        "website": profile.external_url or "",
        "posts": posts,
        "hashtags_searched": hashtags or [],
        "scraped_at": datetime.now().isoformat(),
        "scrape_method": "instaloader",
    }


def _scrape_instagram_fallback(username, hashtags=None, error=None):
    """Fallback: tenta múltiplos endpoints Instagram com headers mobile corretos."""
    note_parts = []
    if error:
        note_parts.append(f"instaloader: {error}")

    # Headers mobile corretos para Instagram (FIX: adicionados headers obrigatórios)
    ig_session = requests.Session()
    ig_mobile_headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "X-IG-App-ID": "936619743392459",
        "X-IG-WWW-Claim": "0",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.instagram.com/{username}/",
        "Origin": "https://www.instagram.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive",
    }
    ig_session.headers.update(ig_mobile_headers)

    # Estratégia 1: api/v1/users/web_profile_info
    try:
        url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        r = ig_session.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            user = data.get("data", {}).get("user", {})
            if user:
                return _ig_build_result(username, user, hashtags, "api_v1")
        else:
            note_parts.append(f"api_v1: HTTP {r.status_code}")
    except Exception as e2:
        note_parts.append(f"api_v1: {e2}")

    # Estratégia 2: graphql/query (endpoint legado)
    try:
        gql_url = (
            f"https://www.instagram.com/graphql/query/"
            f"?query_hash=c9100bf9110dd6361671f113dd02e7d&variables="
            + json.dumps({"user_id": username, "include_reel": True, "fetch_mutual": False, "count": 12})
        )
        # Primeiro visita o perfil para pegar cookies
        ig_session.get(f"https://www.instagram.com/{username}/", timeout=10)
        r2 = ig_session.get(gql_url, timeout=15)
        if r2.status_code == 200:
            gdata = r2.json()
            user = gdata.get("data", {}).get("user", {})
            if user:
                return _ig_build_result(username, user, hashtags, "graphql")
        else:
            note_parts.append(f"graphql: HTTP {r2.status_code}")
    except Exception as e3:
        note_parts.append(f"graphql: {e3}")

    # Estratégia 3: scraping HTML da página do perfil
    try:
        ig_html_headers = {**ig_mobile_headers}
        ig_html_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        del ig_html_headers["X-Requested-With"]
        r3 = requests.get(
            f"https://www.instagram.com/{username}/",
            headers=ig_html_headers, timeout=15
        )
        if r3.status_code == 200:
            html = r3.text
            # Extrai shared_data ou dados JSON do HTML
            m = re.search(r'window\\._sharedData = ({.*?});</script>', html, re.DOTALL)
            if m:
                shared = json.loads(m.group(1))
                u = (shared.get("entry_data", {})
                           .get("ProfilePage", [{}])[0]
                           .get("graphql", {})
                           .get("user", {}))
                if u:
                    return _ig_build_result(username, u, hashtags, "html_shared_data")
            # Tenta extrair dados via regex simples
            followers_m = re.search(r'"edge_followed_by":\{"count":(\d+)\}', html)
            name_m = re.search(r'"full_name":"([^"]+)"', html)
            bio_m = re.search(r'"biography":"([^"]*)"', html)
            if followers_m:
                return {
                    "platform": "instagram",
                    "username": username,
                    "name": name_m.group(1) if name_m else username,
                    "bio": bio_m.group(1) if bio_m else "",
                    "followers": int(followers_m.group(1)),
                    "following": 0, "posts_count": 0, "reels_count": 0,
                    "verified": False, "private": False, "website": "",
                    "posts": [],
                    "note": "Dados parciais — scraping limitado",
                    "hashtags_searched": hashtags or [],
                    "scraped_at": datetime.now().isoformat(),
                    "scrape_method": "html_regex",
                }
        else:
            note_parts.append(f"html: HTTP {r3.status_code}")
    except Exception as e4:
        note_parts.append(f"html: {e4}")

    note_parts.append(
        "Instagram bloqueia scraping sem login. "
        "Instale instaloader: pip install instaloader"
    )
    return {
        "platform": "instagram",
        "username": username,
        "name": username,
        "bio": "",
        "note": " | ".join(note_parts),
        "followers": 0, "following": 0, "posts_count": 0,
        "reels_count": 0, "verified": False, "private": False,
        "posts": [],
        "hashtags_searched": hashtags or [],
        "scraped_at": datetime.now().isoformat(),
        "scrape_method": "failed",
    }


def _ig_build_result(username, user, hashtags, method):
    """Constrói resultado padronizado de dados do Instagram."""
    followers = (
        user.get("edge_followed_by", {}).get("count", 0) or
        user.get("follower_count", 0)
    )
    following = (
        user.get("edge_follow", {}).get("count", 0) or
        user.get("following_count", 0)
    )
    posts_count = (
        user.get("edge_owner_to_timeline_media", {}).get("count", 0) or
        user.get("media_count", 0)
    )
    posts = []
    for e in user.get("edge_owner_to_timeline_media", {}).get("edges", [])[:12]:
        node = e.get("node", {})
        sc = node.get("shortcode", "")
        posts.append({
            "shortcode": sc,
            "likes": node.get("edge_liked_by", {}).get("count", 0),
            "comments": node.get("edge_media_to_comment", {}).get("count", 0),
            "timestamp": node.get("taken_at_timestamp", 0),
            "url": f"https://www.instagram.com/p/{sc}/",
            "type": "video" if node.get("is_video") else "post",
            "hashtags_found": re.findall(r"#(\w+)", node.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node", {}).get("text", "") if node.get("edge_media_to_caption", {}).get("edges") else "")[:10],
        })
    return {
        "platform": "instagram",
        "username": username,
        "name": user.get("full_name", username),
        "bio": user.get("biography", ""),
        "followers": followers,
        "following": following,
        "posts_count": posts_count,
        "reels_count": sum(1 for p in posts if p["type"] == "video"),
        "verified": user.get("is_verified", False),
        "private": user.get("is_private", False),
        "website": user.get("external_url", ""),
        "posts": posts,
        "hashtags_searched": hashtags or [],
        "scraped_at": datetime.now().isoformat(),
        "scrape_method": method,
    }


# ─────────────────────────────────────────────
# TIKTOK — scraping direto (melhor opção leve no Termux)
# ─────────────────────────────────────────────
def scrape_tiktok(username, hashtags=None):
    username = username.lstrip("@")
    url = f"https://www.tiktok.com/@{username}"
    try:
        # FIX: TikTok exige headers mobile + sec-ch-ua + Referer corretos
        tiktok_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; Redmi 13C) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.6367.82 Mobile Safari/537.36 TikTok/30.5.3"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "Referer": "https://www.tiktok.com/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive",
        }
        tiktok_session = requests.Session()
        tiktok_session.headers.update(tiktok_headers)
        # Visita homepage primeiro para pegar cookies
        try:
            tiktok_session.get("https://www.tiktok.com/", timeout=8)
        except Exception:
            pass
        r = tiktok_session.get(url, timeout=20, allow_redirects=True)
        r.raise_for_status()
        html = r.text

        # Estratégia 1: __UNIVERSAL_DATA__ (formato 2024+)
        uni_match = re.search(
            r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        if uni_match:
            try:
                udata = json.loads(uni_match.group(1))
                user_detail = (
                    udata.get("__DEFAULT_SCOPE__", {})
                        .get("webapp.user-detail", {})
                )
                user_info = user_detail.get("userInfo", {})
                user_data = user_info.get("user", {})
                stats_data = user_info.get("stats", {})
                if stats_data.get("followerCount") is not None:
                    return _tiktok_result(username, user_data, stats_data, [], hashtags, "universal_data")
            except Exception:
                pass

        # Estratégia 2: SIGI_STATE
        sigi_match = re.search(
            r'<script id="SIGI_STATE"[^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        if sigi_match:
            try:
                sigi = json.loads(sigi_match.group(1))
                user_info = sigi.get("UserModule", {}).get("users", {})
                stats_info = sigi.get("UserModule", {}).get("stats", {})
                video_list = sigi.get("ItemModule", {})
                user_data = list(user_info.values())[0] if user_info else {}
                stats_data = list(stats_info.values())[0] if stats_info else {}
                videos = []
                for vid_id, vid in list(video_list.items())[:15]:
                    s = vid.get("stats", {})
                    desc = vid.get("desc", "") or ""
                    videos.append({
                        "video_id": vid_id,
                        "description": desc[:200],
                        "views": s.get("playCount", 0),
                        "likes": s.get("diggCount", 0),
                        "comments": s.get("commentCount", 0),
                        "shares": s.get("shareCount", 0),
                        "timestamp": vid.get("createTime", 0),
                        "hashtags_found": re.findall(r"#(\w+)", desc)[:10],
                        "url": f"https://www.tiktok.com/@{username}/video/{vid_id}",
                        "type": "video",
                    })
                if stats_data:
                    return _tiktok_result(username, user_data, stats_data, videos, hashtags, "sigi_state")
            except Exception:
                pass

        # Estratégia 3: regex simples
        followers_m = re.search(r'"followerCount":(\d+)', html)
        following_m = re.search(r'"followingCount":(\d+)', html)
        name_m = re.search(r'"nickname":"([^"]+)"', html)
        likes_m = re.search(r'"heartCount":(\d+)', html)
        count_m = re.search(r'"videoCount":(\d+)', html)
        return {
            "platform": "tiktok",
            "username": username,
            "name": name_m.group(1) if name_m else username,
            "bio": "",
            "followers": int(followers_m.group(1)) if followers_m else 0,
            "following": int(following_m.group(1)) if following_m else 0,
            "likes_total": int(likes_m.group(1)) if likes_m else 0,
            "video_count": int(count_m.group(1)) if count_m else 0,
            "verified": False,
            "videos": [],
            "note": "Dados parciais — TikTok usa proteção anti-scraping",
            "hashtags_searched": hashtags or [],
            "scraped_at": datetime.now().isoformat(),
            "scrape_method": "html_regex",
        }

    except Exception as e:
        return {
            "platform": "tiktok",
            "username": username,
            "name": username,
            "error": str(e),
            "followers": 0, "following": 0, "likes_total": 0, "video_count": 0,
            "videos": [],
            "hashtags_searched": hashtags or [],
            "scraped_at": datetime.now().isoformat(),
            "scrape_method": "failed",
        }


def _tiktok_result(username, user_data, stats_data, videos, hashtags, method):
    return {
        "platform": "tiktok",
        "username": username,
        "name": user_data.get("nickname", username),
        "bio": user_data.get("signature", ""),
        "followers": stats_data.get("followerCount", 0),
        "following": stats_data.get("followingCount", 0),
        "likes_total": stats_data.get("heartCount", 0),
        "video_count": stats_data.get("videoCount", 0),
        "verified": user_data.get("verified", False),
        "videos": videos,
        "hashtags_searched": hashtags or [],
        "scraped_at": datetime.now().isoformat(),
        "scrape_method": method,
    }


# ─────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────
def _parse_number(text):
    if not text:
        return 0
    text = str(text).strip().upper()
    text = re.sub(r'[^\d.,KMB]', '', text)
    for suffix, mult in [("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)]:
        if text.endswith(suffix):
            try:
                return int(float(text[:-1].replace(",", ".")) * mult)
            except ValueError:
                return 0
    try:
        clean = re.sub(r"[^\d]", "", text)
        return int(clean) if clean else 0
    except (ValueError, OverflowError):
        return 0


# ════════════════════════════════════════════════════════════
# TEMPLATES HTML (inline)
# ════════════════════════════════════════════════════════════

INDEX_HTML = '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="UTF-8"/>\n<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover"/>\n<title>SocialMind — by @o.inicianteop</title>\n<link rel="stylesheet" href="/static/css/style.css"/>\n<link rel="preconnect" href="https://fonts.googleapis.com"/>\n<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>\n</head>\n<body>\n\n<!-- STATUS BAR FAKE iOS -->\n<div class="status-bar">\n  <span class="status-time" id="clock">9:41</span>\n  <div class="status-icons">\n    <svg width="16" height="12" fill="currentColor" viewBox="0 0 16 12"><rect x="0" y="3" width="3" height="9" rx="1"/><rect x="4.5" y="2" width="3" height="10" rx="1"/><rect x="9" y="0" width="3" height="12" rx="1"/><rect x="13.5" y="0" width="2.5" height="12" rx="1" opacity=".3"/></svg>\n    <svg width="16" height="12" fill="currentColor" viewBox="0 0 24 12"><path d="M1 4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V4zm18 1h1a1 1 0 0 1 1 1v0a1 1 0 0 1-1 1h-1V5zM3 4v4h14V4H3zm0 0"/><rect x="3" y="4" width="9" height="4" rx="1" fill="currentColor"/></svg>\n  </div>\n</div>\n\n<!-- HERO HEADER -->\n<div class="hero">\n  <div class="hero-blur"></div>\n  <div class="hero-content">\n    <div class="logo-badge">SM</div>\n    <h1 class="hero-title">SocialMind</h1>\n    <p class="hero-sub">Análise de redes sociais sem API key</p>\n    <div class="creator-tag">\n      <div class="creator-avatar">OP</div>\n      <span>by <strong>@o.inicianteop</strong></span>\n    </div>\n  </div>\n  <div class="hero-orbs">\n    <div class="orb orb-1"></div>\n    <div class="orb orb-2"></div>\n    <div class="orb orb-3"></div>\n  </div>\n</div>\n\n<!-- MAIN FORM CARD -->\n<div class="container">\n  <div class="card glass form-card animate-up">\n    <div class="card-header">\n      <h2>Analisar Perfil</h2>\n      <p>Cole o @ e escolha a plataforma</p>\n    </div>\n\n    <form action="/analyze" method="post" id="analyzeForm">\n      <!-- PLATFORM SELECTOR -->\n      <div class="platform-selector">\n        <label class="platform-btn active" data-platform="instagram">\n          <input type="radio" name="platform" value="instagram" checked hidden/>\n          <span class="platform-icon">\n            <svg width="22" height="22" fill="none" viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="20" rx="6" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="2"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor"/></svg>\n          </span>\n          <span>Instagram</span>\n        </label>\n        <label class="platform-btn" data-platform="youtube">\n          <input type="radio" name="platform" value="youtube" hidden/>\n          <span class="platform-icon">\n            <svg width="22" height="22" fill="none" viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="4" stroke="currentColor" stroke-width="2"/><polygon points="10,8 16,12 10,16" fill="currentColor"/></svg>\n          </span>\n          <span>YouTube</span>\n        </label>\n        <label class="platform-btn" data-platform="tiktok">\n          <input type="radio" name="platform" value="tiktok" hidden/>\n          <span class="platform-icon">\n            <svg width="22" height="22" fill="currentColor" viewBox="0 0 24 24"><path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.28 0 .54.04.79.1V9.01a6.33 6.33 0 0 0-.79-.05 6.34 6.34 0 0 0-6.34 6.34 6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.33-6.34V8.69a8.17 8.17 0 0 0 4.78 1.52V6.76a4.84 4.84 0 0 1-1.01-.07z"/></svg>\n          </span>\n          <span>TikTok</span>\n        </label>\n      </div>\n\n      <!-- USERNAME -->\n      <div class="input-group">\n        <div class="input-prefix">@</div>\n        <input\n          type="text"\n          name="username"\n          id="username"\n          class="input-field"\n          placeholder="seuusuario"\n          autocomplete="off"\n          autocorrect="off"\n          spellcheck="false"\n          required\n        />\n      </div>\n\n      <!-- HASHTAGS -->\n      <div class="input-group">\n        <div class="input-prefix">#</div>\n        <input\n          type="text"\n          name="hashtags"\n          id="hashtags"\n          class="input-field"\n          placeholder="hashtag1, hashtag2 (opcional)"\n          autocomplete="off"\n          autocorrect="off"\n          spellcheck="false"\n        />\n      </div>\n\n      <!-- SUBMIT -->\n      <button type="submit" class="btn-primary" id="submitBtn">\n        <span class="btn-text">Analisar Agora</span>\n        <span class="btn-icon">\n          <svg width="18" height="18" fill="none" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>\n        </span>\n        <div class="btn-loader hidden">\n          <div class="spinner"></div>\n        </div>\n      </button>\n    </form>\n  </div>\n\n  <!-- INFO CHIPS -->\n  <div class="chips-row animate-up" style="animation-delay:.1s">\n    <div class="chip">\n      <span class="chip-dot green"></span> Sem API key\n    </div>\n    <div class="chip">\n      <span class="chip-dot blue"></span> 100% Grátis\n    </div>\n    <div class="chip">\n      <span class="chip-dot purple"></span> Offline ok\n    </div>\n  </div>\n\n  <!-- FEATURES GRID -->\n  <div class="features-grid animate-up" style="animation-delay:.2s">\n    <div class="feature-card">\n      <div class="feature-icon" style="background:linear-gradient(135deg,#FF6B6B,#FF8E53)">📊</div>\n      <h3>Score da Conta</h3>\n      <p>Avaliação completa do perfil com pontuação e diagnóstico</p>\n    </div>\n    <div class="feature-card">\n      <div class="feature-icon" style="background:linear-gradient(135deg,#A18CD1,#FBC2EB)">🎯</div>\n      <h3>Detecta Nicho</h3>\n      <p>Identifica automaticamente o tema do perfil</p>\n    </div>\n    <div class="feature-card">\n      <div class="feature-icon" style="background:linear-gradient(135deg,#43E97B,#38F9D7)">🚀</div>\n      <h3>Crescimento</h3>\n      <p>Estimativas reais de tempo por cenário de esforço</p>\n    </div>\n    <div class="feature-card">\n      <div class="feature-icon" style="background:linear-gradient(135deg,#F7971E,#FFD200)">🔥</div>\n      <h3>Esquenta Conta</h3>\n      <p>Plano diário para aquecer sem risco de shadowban</p>\n    </div>\n    <div class="feature-card">\n      <div class="feature-icon" style="background:linear-gradient(135deg,#4FACFE,#00F2FE)">🤖</div>\n      <h3>Automação Grátis</h3>\n      <p>Prompts prontos e scripts Python sem API key</p>\n    </div>\n    <div class="feature-card">\n      <div class="feature-icon" style="background:linear-gradient(135deg,#F953C6,#B91D73)">🎬</div>\n      <h3>Análise de Vídeos</h3>\n      <p>Top e piores vídeos com score de viral</p>\n    </div>\n  </div>\n\n  <!-- HISTÓRICO -->\n  {% if history %}\n  <div class="section animate-up" style="animation-delay:.3s">\n    <div class="section-header">\n      <h2>Histórico</h2>\n      <span class="badge">{{ history|length }}</span>\n    </div>\n    <div class="history-list">\n      {% for item in history %}\n      <a href="/result/{{ item.id }}" class="history-item">\n        <div class="history-avatar {{ item.platform }}">\n          {{ item.username[0]|upper }}\n        </div>\n        <div class="history-info">\n          <span class="history-user">@{{ item.username }}</span>\n          <span class="history-meta">{{ item.platform }} · {{ item.created_at[:10] }}</span>\n        </div>\n        <div class="history-arrow">\n          <svg width="16" height="16" fill="none" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>\n        </div>\n      </a>\n      {% endfor %}\n    </div>\n  </div>\n  {% endif %}\n\n  <!-- FOOTER -->\n  <div class="footer animate-up" style="animation-delay:.4s">\n    <p>Feito com 💜 por <a href="https://instagram.com/o.inicianteop" target="_blank">@o.inicianteop</a></p>\n    <p class="footer-sub">Roda 100% local no Termux · Sem internet para análise</p>\n  </div>\n</div>\n\n<script>/* SocialMind — by @o.inicianteop */\n\n// ─── CLOCK ───\nfunction updateClock() {\n  const el = document.getElementById(\'clock\');\n  if (!el) return;\n  const now = new Date();\n  el.textContent = now.getHours() + \':\' + String(now.getMinutes()).padStart(2, \'0\');\n}\nupdateClock();\nsetInterval(updateClock, 10000);\n\n// ─── PLATFORM SELECTOR ───\ndocument.querySelectorAll(\'.platform-btn\').forEach(btn => {\n  btn.addEventListener(\'click\', () => {\n    document.querySelectorAll(\'.platform-btn\').forEach(b => b.classList.remove(\'active\'));\n    btn.classList.add(\'active\');\n    btn.querySelector(\'input[type=radio]\').checked = true;\n    // haptic-like visual pulse\n    btn.style.transform = \'scale(0.93)\';\n    setTimeout(() => { btn.style.transform = \'\'; }, 150);\n  });\n});\n\n// ─── FORM SUBMIT → LOADING ───\nconst form = document.getElementById(\'analyzeForm\');\nif (form) {\n  form.addEventListener(\'submit\', (e) => {\n    const username = document.getElementById(\'username\')?.value?.trim();\n    if (!username) { e.preventDefault(); shakeInput(); return; }\n    document.body.classList.add(\'loading\');\n    const btn = document.getElementById(\'submitBtn\');\n    if (btn) {\n      btn.querySelector(\'.btn-text\').style.display = \'none\';\n      btn.querySelector(\'.btn-icon\').style.display = \'none\';\n      btn.querySelector(\'.btn-loader\').classList.remove(\'hidden\');\n    }\n  });\n}\n\nfunction shakeInput() {\n  const inp = document.getElementById(\'username\');\n  if (!inp) return;\n  const group = inp.closest(\'.input-group\');\n  if (!group) return;\n  group.style.animation = \'none\';\n  group.style.borderColor = \'rgba(248,113,113,0.7)\';\n  group.style.boxShadow = \'0 0 0 3px rgba(248,113,113,0.15)\';\n  let x = 0;\n  const steps = [8, -8, 6, -6, 4, -4, 0];\n  let i = 0;\n  const shake = setInterval(() => {\n    group.style.transform = `translateX(${steps[i]}px)`;\n    i++;\n    if (i >= steps.length) {\n      clearInterval(shake);\n      group.style.transform = \'\';\n      setTimeout(() => {\n        group.style.borderColor = \'\';\n        group.style.boxShadow = \'\';\n      }, 600);\n    }\n  }, 50);\n  inp.focus();\n}\n\n// ─── STAGGERED ANIMATIONS ───\nfunction initAnimations() {\n  const els = document.querySelectorAll(\'.animate-up\');\n  const observer = new IntersectionObserver((entries) => {\n    entries.forEach(entry => {\n      if (entry.isIntersecting) {\n        entry.target.style.animationPlayState = \'running\';\n        observer.unobserve(entry.target);\n      }\n    });\n  }, { threshold: 0.1, rootMargin: \'0px 0px -20px 0px\' });\n\n  els.forEach((el, i) => {\n    if (!el.style.animationDelay) {\n      el.style.animationDelay = `${i * 0.04}s`;\n    }\n    observer.observe(el);\n  });\n}\n\n// ─── SCORE RING ANIMATION ───\nfunction animateScoreRing() {\n  const ring = document.querySelector(\'.score-ring-fill\');\n  if (!ring) return;\n  const targetDash = ring.getAttribute(\'stroke-dasharray\');\n  ring.setAttribute(\'stroke-dasharray\', \'0 263.8\');\n  setTimeout(() => {\n    ring.style.transition = \'stroke-dasharray 1.4s cubic-bezier(.4,0,.2,1)\';\n    ring.setAttribute(\'stroke-dasharray\', targetDash);\n  }, 300);\n}\n\n// ─── CONFIDENCE BAR ANIMATION ───\nfunction animateConfidenceBar() {\n  const bars = document.querySelectorAll(\'.confidence-bar\');\n  bars.forEach(bar => {\n    const targetWidth = bar.style.width;\n    bar.style.width = \'0%\';\n    setTimeout(() => { bar.style.width = targetWidth; }, 400);\n  });\n}\n\n// ─── SCROLL-TRIGGERED COUNTER ───\nfunction animateCounters() {\n  const statValues = document.querySelectorAll(\'.stat-value\');\n  statValues.forEach(el => {\n    const text = el.textContent.replace(/\\./g, \'\').replace(\',\', \'.\');\n    const num = parseFloat(text);\n    if (isNaN(num) || num === 0) return;\n    const suffix = el.textContent.replace(/[\\d.,]/g, \'\');\n    let start = 0;\n    const duration = 900;\n    const startTime = performance.now();\n    const animate = (now) => {\n      const progress = Math.min((now - startTime) / duration, 1);\n      const eased = 1 - Math.pow(1 - progress, 3);\n      const current = Math.floor(eased * num);\n      el.textContent = current.toLocaleString(\'pt-BR\') + suffix;\n      if (progress < 1) requestAnimationFrame(animate);\n      else el.textContent = el.dataset.original || el.textContent;\n    };\n    el.dataset.original = el.textContent;\n    requestAnimationFrame(animate);\n  });\n}\n\n// ─── SMOOTH SCROLL TOP ON BACK ───\ndocument.querySelectorAll(\'.nav-back\').forEach(btn => {\n  btn.addEventListener(\'click\', (e) => {\n    btn.style.opacity = \'0.5\';\n    btn.style.transform = \'translateX(-4px)\';\n  });\n});\n\n// ─── TOUCH RIPPLE ───\nfunction addRipple(el) {\n  el.addEventListener(\'click\', function(e) {\n    const rect = el.getBoundingClientRect();\n    const ripple = document.createElement(\'div\');\n    ripple.style.cssText = `\n      position:absolute; border-radius:50%; background:rgba(255,255,255,0.15);\n      width:100px; height:100px;\n      left:${e.clientX - rect.left - 50}px;\n      top:${e.clientY - rect.top - 50}px;\n      transform:scale(0); animation:ripple .5s ease-out forwards;\n      pointer-events:none;\n    `;\n    el.style.position = \'relative\';\n    el.style.overflow = \'hidden\';\n    el.appendChild(ripple);\n    setTimeout(() => ripple.remove(), 500);\n  });\n}\ndocument.querySelectorAll(\'.btn-primary, .history-item, .platform-btn\').forEach(addRipple);\n\n// ─── CSS RIPPLE KEYFRAME ───\nconst style = document.createElement(\'style\');\nstyle.textContent = \'@keyframes ripple { to { transform: scale(4); opacity: 0; } }\';\ndocument.head.appendChild(style);\n\n// ─── INIT ───\ndocument.addEventListener(\'DOMContentLoaded\', () => {\n  initAnimations();\n  animateScoreRing();\n  animateConfidenceBar();\n  setTimeout(animateCounters, 200);\n});\n\n// Also run if DOM already loaded\nif (document.readyState !== \'loading\') {\n  initAnimations();\n  animateScoreRing();\n  animateConfidenceBar();\n  setTimeout(animateCounters, 200);\n}\n</script>\n</body>\n</html>\n'

RESULT_HTML = '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="UTF-8"/>\n<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover"/>\n<title>@{{ data.username }} — SocialMind</title>\n<link rel="stylesheet" href="/static/css/style.css"/>\n<link rel="preconnect" href="https://fonts.googleapis.com"/>\n<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>\n</head>\n<body>\n\n<div class="status-bar">\n  <span class="status-time" id="clock">9:41</span>\n  <div class="status-icons">\n    <svg width="16" height="12" fill="currentColor" viewBox="0 0 16 12"><rect x="0" y="3" width="3" height="9" rx="1"/><rect x="4.5" y="2" width="3" height="10" rx="1"/><rect x="9" y="0" width="3" height="12" rx="1"/><rect x="13.5" y="0" width="2.5" height="12" rx="1" opacity=".3"/></svg>\n    <svg width="16" height="12" fill="currentColor" viewBox="0 0 24 12"><path d="M1 4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V4zm18 1h1a1 1 0 0 1 1 1v0a1 1 0 0 1-1 1h-1V5zM3 4v4h14V4H3zm0 0"/><rect x="3" y="4" width="9" height="4" rx="1" fill="currentColor"/></svg>\n  </div>\n</div>\n\n<!-- NAV -->\n<div class="nav-bar">\n  <a href="/" class="nav-back">\n    <svg width="20" height="20" fill="none" viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>\n    Voltar\n  </a>\n  <span class="nav-title">Resultado</span>\n  <span class="nav-badge {{ data.platform }}">{{ data.platform }}</span>\n</div>\n\n{% set acc = data.account %}\n{% set warm = data.warming %}\n\n<!-- PROFILE HERO -->\n<div class="profile-hero {{ data.platform }}-gradient">\n  <div class="profile-hero-blur"></div>\n  <div class="profile-hero-content">\n    <div class="profile-avatar-ring">\n      <div class="profile-avatar">{{ data.username[0]|upper }}</div>\n    </div>\n    <h1 class="profile-name">@{{ data.username }}</h1>\n    {% if acc.niche %}\n    <div class="niche-chip">\n      {{ acc.niche.primary }}\n      {% if acc.niche.secondary %}· {{ acc.niche.secondary|join(\' · \') }}{% endif %}\n    </div>\n    {% endif %}\n    {% if acc.growth_stage %}\n    <div class="stage-badge" style="background:{{ acc.growth_stage.color }}22; color:{{ acc.growth_stage.color }}; border:1px solid {{ acc.growth_stage.color }}44">\n      {{ acc.growth_stage.label }}\n    </div>\n    {% endif %}\n  </div>\n</div>\n\n<div class="container result-container">\n\n  <!-- AVISO DE DADOS INDISPONÍVEIS -->\n  {% if acc.scrape_error or acc.scrape_errors or acc.data_available == false %}\n  <div class="card animate-up" style="border:1px solid #FFB34755; background:#FFB34710; margin-bottom:12px;">\n    <div style="display:flex; align-items:flex-start; gap:10px; padding:4px 0;">\n      <span style="font-size:1.4rem; flex-shrink:0;">⚠️</span>\n      <div>\n        <p style="font-weight:600; margin:0 0 4px; color:#FFB347;">Dados parciais — scraping limitado</p>\n        {% if acc.scrape_error %}\n        <p style="font-size:.8rem; color:var(--text-secondary); margin:0 0 4px;">{{ acc.scrape_error }}</p>\n        {% endif %}\n        {% if acc.scrape_note %}\n        <p style="font-size:.8rem; color:var(--text-secondary); margin:0 0 4px;">{{ acc.scrape_note }}</p>\n        {% endif %}\n        {% if acc.scrape_errors %}\n        {% for err in acc.scrape_errors %}\n        <p style="font-size:.8rem; color:var(--text-secondary); margin:0 0 2px;">• {{ err }}</p>\n        {% endfor %}\n        {% endif %}\n        <p style="font-size:.75rem; color:var(--text-secondary); margin:4px 0 0; opacity:.7;">\n          O score e a análise refletem apenas o que foi possível coletar.\n          Instagram, YouTube e TikTok protegem seus dados contra scraping automático.\n        </p>\n      </div>\n    </div>\n  </div>\n  {% endif %}\n\n  <!-- SCORE CARD -->\n  <div class="card glass animate-up">\n    <div class="score-row">\n      <div class="score-circle-wrap">\n        <svg class="score-ring" viewBox="0 0 100 100">\n          <circle class="score-ring-bg" cx="50" cy="50" r="42" fill="none" stroke-width="8"/>\n          <circle class="score-ring-fill" cx="50" cy="50" r="42" fill="none" stroke-width="8"\n            stroke-dasharray="{{ (acc.score or 0) * 2.638 }} 263.8"\n            style="stroke:{% if (acc.score or 0) >= 70 %}#43E97B{% elif (acc.score or 0) >= 40 %}#FFB347{% else %}#FF6B6B{% endif %}"/>\n        </svg>\n        <div class="score-value">{{ acc.score or 0 }}</div>\n      </div>\n      <div class="score-info">\n        <h2>Score da Conta</h2>\n        <p class="score-label {% if (acc.score or 0) >= 70 %}green{% elif (acc.score or 0) >= 40 %}yellow{% else %}red{% endif %}">\n          {% if (acc.score or 0) >= 70 %}Conta saudável ✅\n          {% elif (acc.score or 0) >= 40 %}Pode melhorar ⚡\n          {% else %}Precisa de atenção 🚨{% endif %}\n        </p>\n        <p class="score-sub">Análise em {{ data.created_at[:10] }}</p>\n      </div>\n    </div>\n  </div>\n\n  <!-- STATS GRID -->\n  <div class="stats-grid animate-up" style="animation-delay:.05s">\n    {% if data.platform == \'instagram\' %}\n      {% set followers = acc.followers or 0 %}\n      {% set following = acc.following or 0 %}\n      <div class="stat-card">\n        <div class="stat-value">{{ "{:,}".format(followers).replace(",",".") }}</div>\n        <div class="stat-label">Seguidores</div>\n      </div>\n      <div class="stat-card">\n        <div class="stat-value">{{ "{:,}".format(following).replace(",",".") }}</div>\n        <div class="stat-label">Seguindo</div>\n      </div>\n      <div class="stat-card">\n        <div class="stat-value">{{ acc.posts_count or 0 }}</div>\n        <div class="stat-label">Posts</div>\n      </div>\n      <div class="stat-card">\n        <div class="stat-value">{{ acc.avg_engagement or 0 }}%</div>\n        <div class="stat-label">Engajamento</div>\n      </div>\n    {% elif data.platform == \'youtube\' %}\n      <div class="stat-card">\n        <div class="stat-value">{{ "{:,}".format(acc.subscribers or 0).replace(",",".") }}</div>\n        <div class="stat-label">Inscritos</div>\n      </div>\n      <div class="stat-card">\n        <div class="stat-value">{{ acc.videos_analyzed or 0 }}</div>\n        <div class="stat-label">Vídeos Analisados</div>\n      </div>\n      <div class="stat-card">\n        <div class="stat-value">{{ "{:,}".format(acc.avg_views or 0).replace(",",".") }}</div>\n        <div class="stat-label">Média Views</div>\n      </div>\n      <div class="stat-card">\n        <div class="stat-value">{{ acc.posting_frequency.posts_per_week or 0 }}/sem</div>\n        <div class="stat-label">Frequência</div>\n      </div>\n    {% elif data.platform == \'tiktok\' %}\n      <div class="stat-card">\n        <div class="stat-value">{{ "{:,}".format(acc.followers or 0).replace(",",".") }}</div>\n        <div class="stat-label">Seguidores</div>\n      </div>\n      <div class="stat-card">\n        <div class="stat-value">{{ "{:,}".format(acc.likes_total or 0).replace(",",".") }}</div>\n        <div class="stat-label">Likes Total</div>\n      </div>\n      <div class="stat-card">\n        <div class="stat-value">{{ acc.video_count or 0 }}</div>\n        <div class="stat-label">Vídeos</div>\n      </div>\n      <div class="stat-card">\n        <div class="stat-value">{{ acc.avg_engagement or 0 }}%</div>\n        <div class="stat-label">Engajamento</div>\n      </div>\n    {% endif %}\n  </div>\n\n  <!-- NICHO CARD -->\n  {% if acc.niche %}\n  <div class="card glass animate-up" style="animation-delay:.08s">\n    <div class="section-label">🎯 Tema / Nicho Detectado</div>\n    <div class="niche-result">\n      <div class="niche-primary">{{ acc.niche.primary }}</div>\n      {% if acc.niche.secondary %}\n      <div class="niche-secondary">\n        {% for s in acc.niche.secondary %}<span class="tag">{{ s }}</span>{% endfor %}\n      </div>\n      {% endif %}\n      <div class="confidence-bar-wrap">\n        <div class="confidence-bar" style="width:{{ acc.niche.confidence }}%"></div>\n        <span>{{ acc.niche.confidence }}% de certeza</span>\n      </div>\n      {% if acc.niche.tip %}\n      <div class="niche-tip">💡 {{ acc.niche.tip }}</div>\n      {% endif %}\n    </div>\n  </div>\n  {% endif %}\n\n  <!-- PROBLEMAS E FORÇAS -->\n  {% if acc.problems or acc.strengths %}\n  <div class="two-col animate-up" style="animation-delay:.1s">\n    {% if acc.strengths %}\n    <div class="card glass strengths-card">\n      <div class="section-label">✅ Pontos Fortes</div>\n      <ul class="check-list green">\n        {% for s in acc.strengths %}<li>{{ s }}</li>{% endfor %}\n      </ul>\n    </div>\n    {% endif %}\n    {% if acc.problems %}\n    <div class="card glass problems-card">\n      <div class="section-label">⚠️ Problemas</div>\n      <ul class="check-list red">\n        {% for p in acc.problems %}<li>{{ p }}</li>{% endfor %}\n      </ul>\n    </div>\n    {% endif %}\n  </div>\n  {% endif %}\n\n  <!-- RECOMENDAÇÕES -->\n  {% if acc.recommendations %}\n  <div class="card glass animate-up" style="animation-delay:.12s">\n    <div class="section-label">📋 Recomendações</div>\n    <ul class="rec-list">\n      {% for r in acc.recommendations %}<li>{{ r }}</li>{% endfor %}\n    </ul>\n  </div>\n  {% endif %}\n\n  <!-- CRESCIMENTO ESTIMADO -->\n  {% if acc.growth_estimate %}\n  {% set ge = acc.growth_estimate %}\n  <div class="card glass animate-up" style="animation-delay:.15s">\n    <div class="section-label">📈 Estimativa de Crescimento</div>\n    <p class="growth-insight">{{ ge.key_insight }}</p>\n    <div class="scenarios">\n      {% for key, sc in ge.scenarios.items() %}\n      <div class="scenario-card" style="border-top:3px solid {{ sc.color }}">\n        <div class="scenario-header">\n          <span class="scenario-emoji">{{ sc.emoji }}</span>\n          <span class="scenario-label">{{ sc.label }}</span>\n        </div>\n        <p class="scenario-desc">{{ sc.description }}</p>\n        <div class="scenario-actions">\n          {% for a in sc.actions %}<div class="action-chip">{{ a }}</div>{% endfor %}\n        </div>\n        <div class="milestones">\n          {% for m in sc.milestones %}\n          <div class="milestone-row">\n            <div class="milestone-label">{{ m.label }}</div>\n            <div class="milestone-time" style="color:{{ sc.color }}">\n              {% if m.weeks > 520 %}Muito longo — mude a estratégia\n              {% elif m.months >= 12 %}~{{ (m.months / 12)|round(1) }} anos\n              {% elif m.months >= 1 %}~{{ m.months }} meses\n              {% else %}~{{ m.weeks }} semanas\n              {% endif %}\n            </div>\n          </div>\n          {% endfor %}\n        </div>\n      </div>\n      {% endfor %}\n    </div>\n  </div>\n  {% endif %}\n\n  <!-- TOP VÍDEOS / POSTS -->\n  {% set top = acc.top_videos or acc.top_posts %}\n  {% if top %}\n  <div class="card glass animate-up" style="animation-delay:.18s">\n    <div class="section-label">🏆 Melhores Conteúdos</div>\n    <div class="video-list">\n      {% for v in top %}\n      <a href="{{ v.url }}" target="_blank" class="video-item">\n        <div class="video-rank">#{{ loop.index }}</div>\n        <div class="video-info">\n          <div class="video-title">{{ v.title or v.description or v.shortcode or "Post" }}</div>\n          <div class="video-meta">\n            {% if v.views %}<span>👁 {{ "{:,}".format(v.views).replace(",",".") }}</span>{% endif %}\n            {% if v.likes %}<span>❤️ {{ "{:,}".format(v.likes).replace(",",".") }}</span>{% endif %}\n            {% if v.comments %}<span>💬 {{ "{:,}".format(v.comments).replace(",",".") }}</span>{% endif %}\n            {% if v.engagement_rate %}<span>📊 {{ v.engagement_rate }}%</span>{% endif %}\n            {% if v.viral_score %}<span class="viral-badge">🔥 {{ v.viral_score }}/100</span>{% endif %}\n          </div>\n        </div>\n        <div class="video-arrow">↗</div>\n      </a>\n      {% endfor %}\n    </div>\n  </div>\n  {% endif %}\n\n  <!-- HASHTAG ANALYSIS -->\n  {% if data.hashtag_analysis %}\n  <div class="card glass animate-up" style="animation-delay:.2s">\n    <div class="section-label">#️⃣ Análise de Hashtags</div>\n    {% for h in data.hashtag_analysis %}\n    <div class="hashtag-row">\n      <div class="hashtag-name">{{ h.hashtag }}</div>\n      <div class="hashtag-info">\n        <span class="hashtag-size size-{{ h.size_class }}">{{ h.size_label }}</span>\n        <p class="hashtag-rec">{{ h.recommendation }}</p>\n      </div>\n    </div>\n    {% endfor %}\n  </div>\n  {% endif %}\n\n  <!-- ESQUENTAR CONTA -->\n  {% if warm %}\n  <div class="card glass animate-up" style="animation-delay:.22s">\n    <div class="section-label">🔥 Esquentar Conta</div>\n    <div class="warming-stage-badge">\n      Fase {{ warm.stage }}: {{ warm.stage_name }}\n    </div>\n    <p class="warming-desc">{{ warm.stage_description }}</p>\n\n    {% if warm.red_flags %}\n    <div class="red-flags">\n      {% for f in warm.red_flags %}<div class="red-flag-item">{{ f }}</div>{% endfor %}\n    </div>\n    {% endif %}\n\n    <div class="warming-plan">\n      <h4>📅 Plano de Ação</h4>\n      {% for step in warm.daily_plan %}\n      <div class="plan-step">\n        <div class="plan-step-num">{{ loop.index }}</div>\n        <div class="plan-step-text">{{ step }}</div>\n      </div>\n      {% endfor %}\n    </div>\n\n    <div class="dos-donts">\n      <div class="dos">\n        <h4>✅ Faça Isso</h4>\n        {% for d in warm.do_list %}<div class="dos-item">{{ d }}</div>{% endfor %}\n      </div>\n      <div class="donts">\n        <h4>🚫 Nunca Faça</h4>\n        {% for d in warm.dont_list %}<div class="donts-item">{{ d }}</div>{% endfor %}\n      </div>\n    </div>\n  </div>\n  {% endif %}\n\n  <!-- AUTOMAÇÕES GRÁTIS -->\n  {% if acc.automations %}\n  {% set auto = acc.automations %}\n  <div class="card glass animate-up" style="animation-delay:.25s">\n    <div class="section-label">🤖 Automações 100% Grátis</div>\n    <div class="auto-intro">{{ auto.intro }}</div>\n\n    <!-- ChatGPT Prompts -->\n    <h4 class="auto-sub">Prompts Prontos para Copiar</h4>\n    {% for prompt in auto.chatgpt_prompts %}\n    <div class="prompt-card">\n      <div class="prompt-header">\n        <span class="prompt-title">{{ prompt.title }}</span>\n        <span class="prompt-tool">{{ prompt.tool }}</span>\n      </div>\n      <pre class="prompt-code">{{ prompt.prompt }}</pre>\n      <button class="copy-btn" onclick="copyText(this)" data-text="{{ prompt.prompt }}">\n        📋 Copiar Prompt\n      </button>\n      <p class="prompt-tip">💡 {{ prompt.tip }}</p>\n    </div>\n    {% endfor %}\n\n    <!-- Ferramentas Grátis -->\n    <h4 class="auto-sub">Ferramentas Gratuitas</h4>\n    <div class="tools-list">\n      {% for tool in auto.free_tools %}\n      <div class="tool-item">\n        <div class="tool-header">\n          <span class="tool-name">{{ tool.name }}</span>\n          <span class="tool-price free">{{ tool.preco }}</span>\n        </div>\n        <p class="tool-uso">{{ tool.uso }}</p>\n        <p class="tool-como">📱 {{ tool.como_usar }}</p>\n      </div>\n      {% endfor %}\n    </div>\n\n    <!-- Scripts Python -->\n    <h4 class="auto-sub">Scripts Python para Termux</h4>\n    {% for script in auto.local_scripts %}\n    <div class="script-card">\n      <div class="script-header">\n        <span class="script-title">{{ script.title }}</span>\n        <span class="script-file">{{ script.filename }}</span>\n      </div>\n      <p class="script-desc">{{ script.description }}</p>\n      <pre class="code-block">{{ script.code }}</pre>\n      <button class="copy-btn" onclick="copyText(this)" data-text="{{ script.code }}">\n        📋 Copiar Script\n      </button>\n    </div>\n    {% endfor %}\n\n    <!-- Fluxo Semanal -->\n    {% set wf = auto.weekly_workflow %}\n    <h4 class="auto-sub">{{ wf.title }}</h4>\n    {% for step in wf.steps %}\n    <div class="workflow-step">\n      <div class="wf-header">\n        <span class="wf-dia">{{ step.dia }}</span>\n        <span class="wf-tempo">{{ step.tempo }}</span>\n      </div>\n      <div class="wf-tarefa">{{ step.tarefa }}</div>\n      <div class="wf-acao">{{ step.acao }}</div>\n    </div>\n    {% endfor %}\n  </div>\n  {% endif %}\n\n  <!-- DOWNLOAD JSON -->\n  <div class="card animate-up" style="text-align:center; padding:16px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08);">\n    <p style="font-size:.8rem; color:var(--text-secondary); margin:0 0 10px;">Salve os dados completos desta análise no seu celular</p>\n    <a href="/result/{{ data.id }}/json"\n       style="display:inline-flex; align-items:center; gap:8px; background:linear-gradient(135deg,#43E97B22,#38F9D722); border:1px solid #43E97B55; color:#43E97B; padding:11px 22px; border-radius:24px; font-size:.85rem; font-weight:600; text-decoration:none; letter-spacing:.01em;">\n      ⬇ Baixar análise (.json)\n    </a>\n    <p style="font-size:.72rem; color:var(--text-secondary); margin:8px 0 0; opacity:.6;">Funciona offline · abre em qualquer editor de texto</p>\n  </div>\n\n  <!-- FOOTER -->\n  <div class="footer animate-up">\n    <p>SocialMind by <a href="https://instagram.com/o.inicianteop" target="_blank">@o.inicianteop</a></p>\n    <p class="footer-sub">yt-dlp + instaloader · Sem API key paga · Roda no Termux</p>\n  </div>\n\n</div>\n\n<script>/* SocialMind — by @o.inicianteop */\n\n// ─── CLOCK ───\nfunction updateClock() {\n  const el = document.getElementById(\'clock\');\n  if (!el) return;\n  const now = new Date();\n  el.textContent = now.getHours() + \':\' + String(now.getMinutes()).padStart(2, \'0\');\n}\nupdateClock();\nsetInterval(updateClock, 10000);\n\n// ─── PLATFORM SELECTOR ───\ndocument.querySelectorAll(\'.platform-btn\').forEach(btn => {\n  btn.addEventListener(\'click\', () => {\n    document.querySelectorAll(\'.platform-btn\').forEach(b => b.classList.remove(\'active\'));\n    btn.classList.add(\'active\');\n    btn.querySelector(\'input[type=radio]\').checked = true;\n    // haptic-like visual pulse\n    btn.style.transform = \'scale(0.93)\';\n    setTimeout(() => { btn.style.transform = \'\'; }, 150);\n  });\n});\n\n// ─── FORM SUBMIT → LOADING ───\nconst form = document.getElementById(\'analyzeForm\');\nif (form) {\n  form.addEventListener(\'submit\', (e) => {\n    const username = document.getElementById(\'username\')?.value?.trim();\n    if (!username) { e.preventDefault(); shakeInput(); return; }\n    document.body.classList.add(\'loading\');\n    const btn = document.getElementById(\'submitBtn\');\n    if (btn) {\n      btn.querySelector(\'.btn-text\').style.display = \'none\';\n      btn.querySelector(\'.btn-icon\').style.display = \'none\';\n      btn.querySelector(\'.btn-loader\').classList.remove(\'hidden\');\n    }\n  });\n}\n\nfunction shakeInput() {\n  const inp = document.getElementById(\'username\');\n  if (!inp) return;\n  const group = inp.closest(\'.input-group\');\n  if (!group) return;\n  group.style.animation = \'none\';\n  group.style.borderColor = \'rgba(248,113,113,0.7)\';\n  group.style.boxShadow = \'0 0 0 3px rgba(248,113,113,0.15)\';\n  let x = 0;\n  const steps = [8, -8, 6, -6, 4, -4, 0];\n  let i = 0;\n  const shake = setInterval(() => {\n    group.style.transform = `translateX(${steps[i]}px)`;\n    i++;\n    if (i >= steps.length) {\n      clearInterval(shake);\n      group.style.transform = \'\';\n      setTimeout(() => {\n        group.style.borderColor = \'\';\n        group.style.boxShadow = \'\';\n      }, 600);\n    }\n  }, 50);\n  inp.focus();\n}\n\n// ─── STAGGERED ANIMATIONS ───\nfunction initAnimations() {\n  const els = document.querySelectorAll(\'.animate-up\');\n  const observer = new IntersectionObserver((entries) => {\n    entries.forEach(entry => {\n      if (entry.isIntersecting) {\n        entry.target.style.animationPlayState = \'running\';\n        observer.unobserve(entry.target);\n      }\n    });\n  }, { threshold: 0.1, rootMargin: \'0px 0px -20px 0px\' });\n\n  els.forEach((el, i) => {\n    if (!el.style.animationDelay) {\n      el.style.animationDelay = `${i * 0.04}s`;\n    }\n    observer.observe(el);\n  });\n}\n\n// ─── SCORE RING ANIMATION ───\nfunction animateScoreRing() {\n  const ring = document.querySelector(\'.score-ring-fill\');\n  if (!ring) return;\n  const targetDash = ring.getAttribute(\'stroke-dasharray\');\n  ring.setAttribute(\'stroke-dasharray\', \'0 263.8\');\n  setTimeout(() => {\n    ring.style.transition = \'stroke-dasharray 1.4s cubic-bezier(.4,0,.2,1)\';\n    ring.setAttribute(\'stroke-dasharray\', targetDash);\n  }, 300);\n}\n\n// ─── CONFIDENCE BAR ANIMATION ───\nfunction animateConfidenceBar() {\n  const bars = document.querySelectorAll(\'.confidence-bar\');\n  bars.forEach(bar => {\n    const targetWidth = bar.style.width;\n    bar.style.width = \'0%\';\n    setTimeout(() => { bar.style.width = targetWidth; }, 400);\n  });\n}\n\n// ─── SCROLL-TRIGGERED COUNTER ───\nfunction animateCounters() {\n  const statValues = document.querySelectorAll(\'.stat-value\');\n  statValues.forEach(el => {\n    const text = el.textContent.replace(/\\./g, \'\').replace(\',\', \'.\');\n    const num = parseFloat(text);\n    if (isNaN(num) || num === 0) return;\n    const suffix = el.textContent.replace(/[\\d.,]/g, \'\');\n    let start = 0;\n    const duration = 900;\n    const startTime = performance.now();\n    const animate = (now) => {\n      const progress = Math.min((now - startTime) / duration, 1);\n      const eased = 1 - Math.pow(1 - progress, 3);\n      const current = Math.floor(eased * num);\n      el.textContent = current.toLocaleString(\'pt-BR\') + suffix;\n      if (progress < 1) requestAnimationFrame(animate);\n      else el.textContent = el.dataset.original || el.textContent;\n    };\n    el.dataset.original = el.textContent;\n    requestAnimationFrame(animate);\n  });\n}\n\n// ─── SMOOTH SCROLL TOP ON BACK ───\ndocument.querySelectorAll(\'.nav-back\').forEach(btn => {\n  btn.addEventListener(\'click\', (e) => {\n    btn.style.opacity = \'0.5\';\n    btn.style.transform = \'translateX(-4px)\';\n  });\n});\n\n// ─── TOUCH RIPPLE ───\nfunction addRipple(el) {\n  el.addEventListener(\'click\', function(e) {\n    const rect = el.getBoundingClientRect();\n    const ripple = document.createElement(\'div\');\n    ripple.style.cssText = `\n      position:absolute; border-radius:50%; background:rgba(255,255,255,0.15);\n      width:100px; height:100px;\n      left:${e.clientX - rect.left - 50}px;\n      top:${e.clientY - rect.top - 50}px;\n      transform:scale(0); animation:ripple .5s ease-out forwards;\n      pointer-events:none;\n    `;\n    el.style.position = \'relative\';\n    el.style.overflow = \'hidden\';\n    el.appendChild(ripple);\n    setTimeout(() => ripple.remove(), 500);\n  });\n}\ndocument.querySelectorAll(\'.btn-primary, .history-item, .platform-btn\').forEach(addRipple);\n\n// ─── CSS RIPPLE KEYFRAME ───\nconst style = document.createElement(\'style\');\nstyle.textContent = \'@keyframes ripple { to { transform: scale(4); opacity: 0; } }\';\ndocument.head.appendChild(style);\n\n// ─── INIT ───\ndocument.addEventListener(\'DOMContentLoaded\', () => {\n  initAnimations();\n  animateScoreRing();\n  animateConfidenceBar();\n  setTimeout(animateCounters, 200);\n});\n\n// Also run if DOM already loaded\nif (document.readyState !== \'loading\') {\n  initAnimations();\n  animateScoreRing();\n  animateConfidenceBar();\n  setTimeout(animateCounters, 200);\n}\n</script>\n<script>\nfunction copyText(btn) {\n  const text = btn.dataset.text;\n  if (navigator.clipboard) {\n    navigator.clipboard.writeText(text).then(() => {\n      const orig = btn.innerHTML;\n      btn.innerHTML = \'✅ Copiado!\';\n      btn.style.background = \'rgba(67,233,123,0.2)\';\n      setTimeout(() => { btn.innerHTML = orig; btn.style.background = \'\'; }, 2000);\n    });\n  } else {\n    const ta = document.createElement(\'textarea\');\n    ta.value = text; document.body.appendChild(ta);\n    ta.select(); document.execCommand(\'copy\');\n    document.body.removeChild(ta);\n    const orig = btn.innerHTML;\n    btn.innerHTML = \'✅ Copiado!\';\n    setTimeout(() => { btn.innerHTML = orig; }, 2000);\n  }\n}\n</script>\n</body>\n</html>\n'

ERROR_HTML = '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="UTF-8"/>\n<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover"/>\n<title>Erro — SocialMind</title>\n<link rel="stylesheet" href="/static/css/style.css"/>\n<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>\n</head>\n<body>\n<div class="status-bar">\n  <span class="status-time" id="clock">9:41</span>\n</div>\n<div class="nav-bar">\n  <a href="/" class="nav-back">\n    <svg width="20" height="20" fill="none" viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>\n    Voltar\n  </a>\n  <span class="nav-title">Erro</span>\n</div>\n<div class="container" style="padding-top:60px;text-align:center">\n  <div class="card glass animate-up" style="padding:40px 24px">\n    <div style="font-size:56px;margin-bottom:16px">😕</div>\n    <h2 style="margin-bottom:8px">Não consegui analisar</h2>\n    <p style="color:var(--text-secondary);margin-bottom:8px">\n      <strong>@{{ username }}</strong> no {{ platform }}\n    </p>\n    <div class="error-box">{{ error }}</div>\n    <div class="error-tips">\n      <h4>Possíveis causas:</h4>\n      <ul>\n        <li>Conta privada ou inexistente</li>\n        <li>Plataforma bloqueou o acesso temporariamente</li>\n        <li>Sem conexão com a internet</li>\n        <li>Nome de usuário com erro de digitação</li>\n      </ul>\n      <h4>O que fazer:</h4>\n      <ul>\n        <li>Verifique se o @ está correto</li>\n        <li>Confirme que a conta é pública</li>\n        <li>Aguarde 2-3 minutos e tente de novo</li>\n        <li>Use VPN se estiver sendo bloqueado</li>\n      </ul>\n    </div>\n    <a href="/" class="btn-primary" style="display:inline-flex;margin-top:20px;text-decoration:none">\n      Tentar Novamente\n    </a>\n  </div>\n  <div class="footer">\n    <p>SocialMind by <a href="https://instagram.com/o.inicianteop" target="_blank">@o.inicianteop</a></p>\n  </div>\n</div>\n<script>/* SocialMind — by @o.inicianteop */\n\n// ─── CLOCK ───\nfunction updateClock() {\n  const el = document.getElementById(\'clock\');\n  if (!el) return;\n  const now = new Date();\n  el.textContent = now.getHours() + \':\' + String(now.getMinutes()).padStart(2, \'0\');\n}\nupdateClock();\nsetInterval(updateClock, 10000);\n\n// ─── PLATFORM SELECTOR ───\ndocument.querySelectorAll(\'.platform-btn\').forEach(btn => {\n  btn.addEventListener(\'click\', () => {\n    document.querySelectorAll(\'.platform-btn\').forEach(b => b.classList.remove(\'active\'));\n    btn.classList.add(\'active\');\n    btn.querySelector(\'input[type=radio]\').checked = true;\n    // haptic-like visual pulse\n    btn.style.transform = \'scale(0.93)\';\n    setTimeout(() => { btn.style.transform = \'\'; }, 150);\n  });\n});\n\n// ─── FORM SUBMIT → LOADING ───\nconst form = document.getElementById(\'analyzeForm\');\nif (form) {\n  form.addEventListener(\'submit\', (e) => {\n    const username = document.getElementById(\'username\')?.value?.trim();\n    if (!username) { e.preventDefault(); shakeInput(); return; }\n    document.body.classList.add(\'loading\');\n    const btn = document.getElementById(\'submitBtn\');\n    if (btn) {\n      btn.querySelector(\'.btn-text\').style.display = \'none\';\n      btn.querySelector(\'.btn-icon\').style.display = \'none\';\n      btn.querySelector(\'.btn-loader\').classList.remove(\'hidden\');\n    }\n  });\n}\n\nfunction shakeInput() {\n  const inp = document.getElementById(\'username\');\n  if (!inp) return;\n  const group = inp.closest(\'.input-group\');\n  if (!group) return;\n  group.style.animation = \'none\';\n  group.style.borderColor = \'rgba(248,113,113,0.7)\';\n  group.style.boxShadow = \'0 0 0 3px rgba(248,113,113,0.15)\';\n  let x = 0;\n  const steps = [8, -8, 6, -6, 4, -4, 0];\n  let i = 0;\n  const shake = setInterval(() => {\n    group.style.transform = `translateX(${steps[i]}px)`;\n    i++;\n    if (i >= steps.length) {\n      clearInterval(shake);\n      group.style.transform = \'\';\n      setTimeout(() => {\n        group.style.borderColor = \'\';\n        group.style.boxShadow = \'\';\n      }, 600);\n    }\n  }, 50);\n  inp.focus();\n}\n\n// ─── STAGGERED ANIMATIONS ───\nfunction initAnimations() {\n  const els = document.querySelectorAll(\'.animate-up\');\n  const observer = new IntersectionObserver((entries) => {\n    entries.forEach(entry => {\n      if (entry.isIntersecting) {\n        entry.target.style.animationPlayState = \'running\';\n        observer.unobserve(entry.target);\n      }\n    });\n  }, { threshold: 0.1, rootMargin: \'0px 0px -20px 0px\' });\n\n  els.forEach((el, i) => {\n    if (!el.style.animationDelay) {\n      el.style.animationDelay = `${i * 0.04}s`;\n    }\n    observer.observe(el);\n  });\n}\n\n// ─── SCORE RING ANIMATION ───\nfunction animateScoreRing() {\n  const ring = document.querySelector(\'.score-ring-fill\');\n  if (!ring) return;\n  const targetDash = ring.getAttribute(\'stroke-dasharray\');\n  ring.setAttribute(\'stroke-dasharray\', \'0 263.8\');\n  setTimeout(() => {\n    ring.style.transition = \'stroke-dasharray 1.4s cubic-bezier(.4,0,.2,1)\';\n    ring.setAttribute(\'stroke-dasharray\', targetDash);\n  }, 300);\n}\n\n// ─── CONFIDENCE BAR ANIMATION ───\nfunction animateConfidenceBar() {\n  const bars = document.querySelectorAll(\'.confidence-bar\');\n  bars.forEach(bar => {\n    const targetWidth = bar.style.width;\n    bar.style.width = \'0%\';\n    setTimeout(() => { bar.style.width = targetWidth; }, 400);\n  });\n}\n\n// ─── SCROLL-TRIGGERED COUNTER ───\nfunction animateCounters() {\n  const statValues = document.querySelectorAll(\'.stat-value\');\n  statValues.forEach(el => {\n    const text = el.textContent.replace(/\\./g, \'\').replace(\',\', \'.\');\n    const num = parseFloat(text);\n    if (isNaN(num) || num === 0) return;\n    const suffix = el.textContent.replace(/[\\d.,]/g, \'\');\n    let start = 0;\n    const duration = 900;\n    const startTime = performance.now();\n    const animate = (now) => {\n      const progress = Math.min((now - startTime) / duration, 1);\n      const eased = 1 - Math.pow(1 - progress, 3);\n      const current = Math.floor(eased * num);\n      el.textContent = current.toLocaleString(\'pt-BR\') + suffix;\n      if (progress < 1) requestAnimationFrame(animate);\n      else el.textContent = el.dataset.original || el.textContent;\n    };\n    el.dataset.original = el.textContent;\n    requestAnimationFrame(animate);\n  });\n}\n\n// ─── SMOOTH SCROLL TOP ON BACK ───\ndocument.querySelectorAll(\'.nav-back\').forEach(btn => {\n  btn.addEventListener(\'click\', (e) => {\n    btn.style.opacity = \'0.5\';\n    btn.style.transform = \'translateX(-4px)\';\n  });\n});\n\n// ─── TOUCH RIPPLE ───\nfunction addRipple(el) {\n  el.addEventListener(\'click\', function(e) {\n    const rect = el.getBoundingClientRect();\n    const ripple = document.createElement(\'div\');\n    ripple.style.cssText = `\n      position:absolute; border-radius:50%; background:rgba(255,255,255,0.15);\n      width:100px; height:100px;\n      left:${e.clientX - rect.left - 50}px;\n      top:${e.clientY - rect.top - 50}px;\n      transform:scale(0); animation:ripple .5s ease-out forwards;\n      pointer-events:none;\n    `;\n    el.style.position = \'relative\';\n    el.style.overflow = \'hidden\';\n    el.appendChild(ripple);\n    setTimeout(() => ripple.remove(), 500);\n  });\n}\ndocument.querySelectorAll(\'.btn-primary, .history-item, .platform-btn\').forEach(addRipple);\n\n// ─── CSS RIPPLE KEYFRAME ───\nconst style = document.createElement(\'style\');\nstyle.textContent = \'@keyframes ripple { to { transform: scale(4); opacity: 0; } }\';\ndocument.head.appendChild(style);\n\n// ─── INIT ───\ndocument.addEventListener(\'DOMContentLoaded\', () => {\n  initAnimations();\n  animateScoreRing();\n  animateConfidenceBar();\n  setTimeout(animateCounters, 200);\n});\n\n// Also run if DOM already loaded\nif (document.readyState !== \'loading\') {\n  initAnimations();\n  animateScoreRing();\n  animateConfidenceBar();\n  setTimeout(animateCounters, 200);\n}\n</script>\n</body>\n</html>\n'


# ════════════════════════════════════════════════════════════════
# FLASK APP
# ════════════════════════════════════════════════════════════════
app = Flask(__name__)
init_db()

@app.route("/")
def index():
    history = get_history(limit=20)
    return render_template_string(INDEX_HTML, history=history)

@app.route("/analyze", methods=["POST"])
def analyze():
    platform = request.form.get("platform", "instagram")
    username = request.form.get("username", "").strip().lstrip("@")
    hashtags_raw = request.form.get("hashtags", "").strip()
    hashtags = [h.strip().lstrip("#") for h in hashtags_raw.split(",") if h.strip()]
    if not username:
        return jsonify({"error": "Usuário não informado"}), 400
    try:
        if platform == "instagram":
            raw = scrape_instagram(username, hashtags)
        elif platform == "youtube":
            raw = scrape_youtube(username, hashtags)
        elif platform == "tiktok":
            raw = scrape_tiktok(username, hashtags)
        else:
            return jsonify({"error": "Plataforma inválida"}), 400
        result_data = analyze_account(raw, platform)
        warming = analyze_warming(raw, platform)
        hashtag_analysis = analyze_hashtag(hashtags, raw) if hashtags else []
        full = {"platform": platform, "username": username, "hashtags": hashtags,
                "account": result_data, "warming": warming,
                "hashtag_analysis": hashtag_analysis, "raw": raw}
        analysis_id = save_analysis(username, platform, full)
        return redirect(url_for("result", analysis_id=analysis_id))
    except Exception as e:
        return render_template_string(ERROR_HTML, error=str(e), username=username, platform=platform)

@app.route("/result/<int:analysis_id>")
def result(analysis_id):
    data = get_analysis_by_id(analysis_id)
    if not data:
        return redirect(url_for("index"))
    return render_template_string(RESULT_HTML, data=data)

@app.route("/result/<int:analysis_id>/json")
def download_json(analysis_id):
    data = get_analysis_by_id(analysis_id)
    if not data:
        return jsonify({"error": "análise não encontrada"}), 404
    username = data.get("username", "analysis")
    platform = data.get("platform", "social")
    filename = f"socialmind_{platform}_{username}_{analysis_id}.json"
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    body = request.get_json(force=True)
    platform = body.get("platform", "instagram")
    username = body.get("username", "").strip().lstrip("@")
    hashtags = body.get("hashtags", [])
    if not username:
        return jsonify({"error": "username required"}), 400
    try:
        if platform == "instagram": raw = scrape_instagram(username, hashtags)
        elif platform == "youtube": raw = scrape_youtube(username, hashtags)
        elif platform == "tiktok": raw = scrape_tiktok(username, hashtags)
        else: return jsonify({"error": "invalid platform"}), 400
        return jsonify({
            "username": username, "platform": platform,
            "account": analyze_account(raw, platform),
            "warming": analyze_warming(raw, platform),
            "hashtag_analysis": analyze_hashtag(hashtags, raw) if hashtags else []
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("=" * 52)
    print("  SocialMind — Analisador de Redes Sociais")
    print("  Acesse: http://localhost:5000")
    print("=" * 52)
    app.run(host="0.0.0.0", port=5000, debug=False)
