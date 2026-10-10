import html
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Generator
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


DATABASE_PATH = Path(__file__).resolve().with_name("meu_treino.db")
PASSWORD_ITERATIONS = 310_000
ADMIN_USERNAME = "JJadm"
TRAINING_PROFILES = {
    "Levantar mais pesado": {
        "objetivo": "aumentar gradualmente a força",
        "repeticoes_multiarticulares": "5-8",
        "repeticoes_isolados": "10-15",
        "series_multiarticulares": 4,
        "series_isolados": 2,
        "descanso_multiarticulares": 150,
        "descanso_isolados": 60,
    },
    "Ganhar massa muscular": {
        "objetivo": "ganho de massa muscular",
        "repeticoes_multiarticulares": "6-10",
        "repeticoes_isolados": "10-15",
        "series_multiarticulares": 4,
        "series_isolados": 3,
        "descanso_multiarticulares": 120,
        "descanso_isolados": 75,
    },
    "Ficar magro e definido": {
        "objetivo": "definição com manutenção de força e massa muscular",
        "repeticoes_multiarticulares": "8-12",
        "repeticoes_isolados": "12-15",
        "series_multiarticulares": 3,
        "series_isolados": 2,
        "descanso_multiarticulares": 75,
        "descanso_isolados": 45,
    },
    "Perder peso": {
        "objetivo": "perda de peso e recomposição corporal",
        "repeticoes_multiarticulares": "8-12",
        "repeticoes_isolados": "10-15",
        "series_multiarticulares": 3,
        "series_isolados": 2,
        "descanso_multiarticulares": 90,
        "descanso_isolados": 60,
    },
}

EQUIPMENT_OPTIONS = [
    "Academia completa",
    "Halteres",
    "Barra e discos",
    "Máquinas",
    "Elásticos",
    "Kettlebell",
    "Peso corporal",
]

EXPERIENCE_OPTIONS = ["Iniciante", "1-2 anos", "3-5 anos", "Mais de 5 anos"]
CONSISTENCY_OPTIONS = [
    "A começar agora",
    "Irregular nos últimos meses",
    "Treino com regularidade",
    "A regressar após uma pausa",
]
CARDIO_OPTIONS = [
    "Sem cardio",
    "Caminhada",
    "Esteira",
    "Ciclismo",
    "Bicicleta estática",
    "Elíptica",
    "Remo",
]
SMART_WORKOUTS = {
    "Push A": [
        ("Supino reto com halteres", "multiarticular"),
        ("Press de ombros na máquina", "multiarticular"),
        ("Supino inclinado com halteres", "multiarticular"),
        ("Elevação lateral", "isolado"),
        ("Extensão de tríceps na polia", "isolado"),
    ],
    "Push B": [
        ("Supino inclinado na máquina", "multiarticular"),
        ("Press de ombros com halteres", "multiarticular"),
        ("Flexões", "multiarticular"),
        ("Crucifixo na polia", "isolado"),
        ("Extensão de tríceps acima da cabeça", "isolado"),
    ],
    "Pull A": [
        ("Remada sentada", "multiarticular"),
        ("Puxada na frente", "multiarticular"),
        ("Remada unilateral com halter", "multiarticular"),
        ("Face pull", "isolado"),
        ("Curl de bíceps com halteres", "isolado"),
    ],
    "Pull B": [
        ("Remada com apoio no peito", "multiarticular"),
        ("Puxada com pega neutra", "multiarticular"),
        ("Remada baixa na polia", "multiarticular"),
        ("Crucifixo inverso", "isolado"),
        ("Curl martelo", "isolado"),
    ],
    "Legs A": [
        ("Agachamento goblet", "multiarticular"),
        ("Peso morto romeno com halteres", "multiarticular"),
        ("Leg press", "multiarticular"),
        ("Extensão de pernas", "isolado"),
        ("Elevação de gémeos em pé", "isolado"),
    ],
    "Legs B": [
        ("Hip thrust", "multiarticular"),
        ("Agachamento búlgaro", "multiarticular"),
        ("Peso morto com kettlebell", "multiarticular"),
        ("Flexão de pernas", "isolado"),
        ("Elevação de gémeos sentado", "isolado"),
    ],
    "Upper": [
        ("Supino com halteres", "multiarticular"),
        ("Remada sentada", "multiarticular"),
        ("Puxada na frente", "multiarticular"),
        ("Press de ombros na máquina", "multiarticular"),
        ("Elevação lateral", "isolado"),
        ("Curl de bíceps na polia", "isolado"),
        ("Extensão de tríceps na polia", "isolado"),
    ],
    "Lower": [
        ("Leg press", "multiarticular"),
        ("Peso morto romeno com halteres", "multiarticular"),
        ("Agachamento goblet", "multiarticular"),
        ("Hip thrust", "multiarticular"),
        ("Extensão de pernas", "isolado"),
        ("Flexão de pernas", "isolado"),
    ],
    "Full Body": [
        ("Agachamento goblet", "multiarticular"),
        ("Supino com halteres", "multiarticular"),
        ("Remada sentada", "multiarticular"),
        ("Peso morto romeno com halteres", "multiarticular"),
        ("Puxada na frente", "multiarticular"),
        ("Elevação lateral", "isolado"),
    ],
    "HIIT & Abdómen": [
        ("Bicicleta estática (intervalos)", "hiit"),
        ("Thruster com halteres", "multiarticular"),
        ("Step-ups alternados", "hiit"),
        ("Mountain climbers", "hiit"),
        ("Prancha", "abdomen"),
        ("Dead bug", "abdomen"),
        ("Crunch na polia", "isolado"),
    ],
    "Ombros & Trapézio": [
        ("Press de ombros com halteres", "multiarticular"),
        ("Remada alta com halteres", "multiarticular"),
        ("Encolhimento de ombros com halteres", "multiarticular"),
        ("Elevação lateral", "isolado"),
        ("Elevação frontal", "isolado"),
        ("Crucifixo inverso", "isolado"),
    ],
}

SMART_WORKOUTS.update({
    "Pernas Completo": SMART_WORKOUTS["Legs A"] + SMART_WORKOUTS["Legs B"][:2],
    "Ombros": SMART_WORKOUTS["Ombros & Trapézio"],
    "Braços": [
        ("Curl de bíceps com halteres", "isolado"),
        ("Curl de bíceps na polia", "isolado"),
        ("Curl martelo", "isolado"),
        ("Extensão de tríceps na polia", "isolado"),
        ("Extensão de tríceps acima da cabeça", "isolado"),
    ],
    "Abdómen": [
        ("Prancha", "abdomen"),
        ("Dead bug", "abdomen"),
        ("Mountain climbers", "hiit"),
        ("Crunch na polia", "isolado"),
    ],
    "Peito": [
        ("Supino reto com halteres", "multiarticular"),
        ("Supino inclinado com halteres", "multiarticular"),
        ("Flexões", "multiarticular"),
        ("Crucifixo na polia", "isolado"),
    ],
    "Costas": [
        ("Puxada na frente", "multiarticular"),
        ("Remada sentada", "multiarticular"),
        ("Remada unilateral com halter", "multiarticular"),
        ("Remada baixa na polia", "multiarticular"),
        ("Face pull", "isolado"),
    ],
})

WEEKDAY_NAMES = (
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
)
WEEKLY_WORKOUT_SCHEDULE = (
    "Pull A",
    "Push A",
    "Legs A",
    "Upper",
    "Pull B",
    "Legs B",
    "Recuperação",
)

EXERCISE_GUIDES = {
    "puxada alta na barra": {
        "musculo": "Costas (latíssimo do dorso); bíceps como auxiliares",
        "equipamento": "Polia alta com barra longa e banco com apoio para as pernas",
        "passos": [
            "Ajusta o apoio para as pernas, senta-te e segura a barra um pouco além da largura dos ombros.",
            "Mantém o tronco alto, abdómen firme e ombros afastados das orelhas.",
            "Puxa a barra em direção à parte superior do peito, conduzindo os cotovelos para baixo.",
            "Faz uma breve pausa sem inclinar excessivamente o tronco.",
            "Deixa a barra subir devagar até estender os braços sem perder o controlo.",
        ],
    },
    "puxada na frente": {
        "musculo": "Costas (latíssimo do dorso); bíceps como auxiliares",
        "equipamento": "Máquina de puxada alta e barra ou pega adequada",
        "passos": [
            "Ajusta o apoio das coxas e agarra a barra com as mãos ligeiramente mais afastadas que os ombros.",
            "Senta-te com o peito aberto, abdómen firme e uma ligeira inclinação natural do tronco.",
            "Puxa a barra à frente em direção à parte superior do peito, levando os cotovelos para baixo.",
            "Não puxes a barra atrás da nuca nem uses balanço para completar a repetição.",
            "Regressa lentamente à posição inicial, mantendo tensão e controlo.",
        ],
    },
    "remada no cabo": {
        "musculo": "Costas (romboides e latíssimo do dorso); bíceps como auxiliares",
        "equipamento": "Polia baixa, cabo e pega neutra",
        "passos": [
            "Senta-te com os pés apoiados e segura a pega com os braços estendidos.",
            "Mantém a coluna neutra, o peito aberto e os ombros longe das orelhas.",
            "Puxa a pega em direção ao abdómen, aproximando as omoplatas sem encolher os ombros.",
            "Evita balançar o tronco ou arredondar a lombar.",
            "Estende os braços lentamente, deixando as omoplatas avançarem de forma controlada.",
        ],
    },
    "remada sentada": {
        "musculo": "Costas (romboides e latíssimo do dorso); bíceps como auxiliares",
        "equipamento": "Máquina de remada sentada ou polia baixa com pega",
        "passos": [
            "Ajusta o assento e apoia os pés; segura a pega com os braços estendidos.",
            "Mantém o tronco estável, peito aberto e coluna neutra.",
            "Puxa os cotovelos para trás e aproxima as omoplatas sem elevar os ombros.",
            "Faz a contração sem inclinar o tronco para trás.",
            "Regressa devagar até estender os braços mantendo o controlo.",
        ],
    },
    "rosca com barra": {
        "musculo": "Bíceps braquial e braquial",
        "equipamento": "Barra reta ou barra EZ",
        "passos": [
            "Fica de pé com os pés à largura da anca e segura a barra com as palmas viradas para a frente.",
            "Mantém cotovelos junto ao tronco, ombros relaxados e abdómen firme.",
            "Dobra os cotovelos para elevar a barra sem balançar o tronco.",
            "Pára antes de os cotovelos avançarem ou os ombros compensarem.",
            "Baixa a barra lentamente até quase estender os braços.",
        ],
    },
    "curl de biceps com halteres": {
        "musculo": "Bíceps braquial",
        "equipamento": "Halteres",
        "passos": [
            "Fica de pé ou sentado com um halter em cada mão e os braços junto ao corpo.",
            "Mantém o tronco estável e os ombros relaxados.",
            "Dobra os cotovelos para aproximar os halteres dos ombros, sem balançar.",
            "Desce devagar até quase estender os braços.",
            "Podes alternar os braços ou executar ambos em simultâneo, mantendo a mesma técnica.",
        ],
    },
    "curl de biceps na polia": {
        "musculo": "Bíceps braquial",
        "equipamento": "Polia baixa com barra curta ou pega individual",
        "passos": [
            "Coloca a polia na posição baixa e segura a pega com as palmas para cima.",
            "Mantém os cotovelos junto ao tronco e os ombros relaxados.",
            "Dobra os cotovelos para elevar a pega sem mover os braços para a frente.",
            "Contrai o bíceps brevemente no topo sem inclinar o corpo.",
            "Estende os cotovelos lentamente, mantendo tensão no cabo.",
        ],
    },
    "rosca com barra": {
        "musculo": "Bíceps braquial e braquial",
        "equipamento": "Barra reta ou barra EZ",
        "passos": [
            "Fica de pé com os pés à largura da anca e segura a barra com as palmas viradas para a frente.",
            "Mantém os cotovelos junto ao tronco, os ombros relaxados e o abdómen firme.",
            "Dobra os cotovelos para elevar a barra sem balançar o tronco.",
            "Pára antes de os cotovelos avançarem ou os ombros compensarem.",
            "Baixa a barra lentamente até quase estender os braços.",
        ],
    },
    "curl martelo": {
        "musculo": "Braquial, braquiorradial e bíceps",
        "equipamento": "Halteres",
        "passos": [
            "Segura um halter em cada mão com as palmas voltadas uma para a outra.",
            "Mantém os cotovelos junto ao tronco e o pulso alinhado.",
            "Dobra os cotovelos elevando os halteres sem rodar os punhos.",
            "Evita balançar o tronco ou encolher os ombros.",
            "Baixa os halteres lentamente até à posição inicial.",
        ],
    },
    "supino": {
        "musculo": "Peitoral; tríceps e deltoide anterior como auxiliares",
        "equipamento": "Banco plano e barra ou halteres",
        "passos": [
            "Deita-te no banco, apoia os pés no chão e mantém as omoplatas estáveis contra o banco.",
            "Segura a barra ou os halteres sobre o peito com os punhos alinhados.",
            "Baixa o peso com controlo em direção ao meio do peito, mantendo os cotovelos num ângulo confortável.",
            "Mantém os pés apoiados e evita arquear excessivamente a lombar.",
            "Empurra o peso para cima até perto de estender os cotovelos, sem perder a estabilidade.",
        ],
    },
    "supino reto com halteres": {
        "musculo": "Peitoral; tríceps e deltoide anterior como auxiliares",
        "equipamento": "Banco plano e par de halteres",
        "passos": [
            "Deita-te no banco com os pés firmes no chão e as omoplatas apoiadas.",
            "Segura os halteres sobre o peito, com punhos alinhados e palmas para a frente.",
            "Baixa os halteres lateralmente até uma amplitude confortável, mantendo os antebraços controlados.",
            "Empurra os halteres para cima sem os bater e sem perder a posição dos ombros.",
            "Usa uma carga que consigas colocar e retirar em segurança.",
        ],
    },
    "supino com halteres": {
        "musculo": "Peitoral; tríceps e deltoide anterior como auxiliares",
        "equipamento": "Banco plano e par de halteres",
        "passos": [
            "Deita-te no banco com os pés firmes e as omoplatas estáveis.",
            "Posiciona os halteres sobre o peito com os punhos alinhados.",
            "Baixa os pesos devagar até uma amplitude confortável, sem deixar os ombros avançarem.",
            "Empurra para cima mantendo os cotovelos ligeiramente fletidos no final.",
            "Termina com controlo e pede ajuda para cargas que não consigas posicionar em segurança.",
        ],
    },
    "supino inclinado com halteres": {
        "musculo": "Peitoral superior; deltoide anterior e tríceps como auxiliares",
        "equipamento": "Banco inclinado e par de halteres",
        "passos": [
            "Ajusta o banco a uma inclinação moderada, apoia os pés e estabiliza as omoplatas.",
            "Segura os halteres acima da parte superior do peito.",
            "Baixa-os de forma controlada até uma amplitude confortável.",
            "Empurra para cima sem encostar os halteres com força.",
            "Mantém o tronco apoiado no banco durante toda a série.",
        ],
    },
    "agachamento goblet": {
        "musculo": "Quadríceps e glúteos; tronco como estabilizador",
        "equipamento": "Halter ou kettlebell",
        "passos": [
            "Segura o halter junto ao peito e coloca os pés aproximadamente à largura dos ombros.",
            "Mantém o peito aberto, abdómen firme e os pés totalmente apoiados.",
            "Dobra anca e joelhos para descer, acompanhando a direção dos dedos dos pés.",
            "Desce apenas até uma profundidade que consigas controlar sem arredondar a lombar.",
            "Empurra o chão para regressar à posição de pé, mantendo os joelhos alinhados.",
        ],
    },
    "peso morto romeno com halteres": {
        "musculo": "Isquiotibiais e glúteos; músculos do tronco estabilizam",
        "equipamento": "Par de halteres",
        "passos": [
            "Fica de pé com os halteres junto às coxas, joelhos ligeiramente fletidos e coluna neutra.",
            "Leva a anca para trás, mantendo os halteres próximos das pernas.",
            "Desce até sentires alongamento na parte posterior das coxas, sem arredondar as costas.",
            "Empurra a anca para a frente para regressar à posição de pé.",
            "Evita transformar o movimento num agachamento ou hiperestender a lombar no topo.",
        ],
    },
    "leg press": {
        "musculo": "Quadríceps e glúteos",
        "equipamento": "Máquina de leg press",
        "passos": [
            "Ajusta o assento para manter as costas e a bacia apoiadas.",
            "Coloca os pés na plataforma à largura dos ombros, com os joelhos alinhados aos pés.",
            "Desbloqueia a plataforma e baixa-a devagar até uma amplitude sem levantar a bacia.",
            "Empurra a plataforma sem bloquear bruscamente os joelhos.",
            "Mantém as mãos nas pegas e segue as instruções de segurança da máquina.",
        ],
    },
    "hip thrust": {
        "musculo": "Glúteo máximo; isquiotibiais como auxiliares",
        "equipamento": "Banco estável e peso opcional com proteção acolchoada",
        "passos": [
            "Apoia a parte superior das costas num banco firme e coloca os pés no chão.",
            "Mantém o queixo ligeiramente recolhido e a bacia neutra.",
            "Eleva a anca contraindo os glúteos até o tronco ficar aproximadamente alinhado com as coxas.",
            "Evita arquear a lombar no topo e mantém os joelhos alinhados com os pés.",
            "Desce a anca lentamente até à posição inicial.",
        ],
    },
    "press de ombros com halteres": {
        "musculo": "Deltoides; tríceps como auxiliares",
        "equipamento": "Halteres e banco com encosto (opcional)",
        "passos": [
            "Senta-te ou fica de pé com o tronco firme e os halteres à altura dos ombros.",
            "Mantém os punhos sobre os cotovelos e evita encolher os ombros.",
            "Empurra os halteres para cima num percurso confortável, sem arquear a lombar.",
            "Pára antes de bloquear os cotovelos com força.",
            "Baixa lentamente os halteres até à altura inicial.",
        ],
    },
    "elevacao lateral": {
        "musculo": "Deltoide lateral",
        "equipamento": "Halteres leves ou polia",
        "passos": [
            "Fica de pé com um halter em cada mão e os braços ao lado do corpo.",
            "Mantém os cotovelos ligeiramente fletidos e o tronco estável.",
            "Eleva os braços lateralmente até perto da altura dos ombros, sem encolher.",
            "Controla a descida; não uses balanço para subir os pesos.",
            "Usa uma carga leve que permita manter o movimento suave.",
        ],
    },
    "extensao de triceps na polia": {
        "musculo": "Tríceps",
        "equipamento": "Polia alta com corda ou barra",
        "passos": [
            "Fica de frente para a polia e segura a pega com os cotovelos junto ao tronco.",
            "Mantém o peito aberto e o abdómen firme.",
            "Estende os cotovelos para baixo sem mover os braços para a frente.",
            "No final, separa ligeiramente as pontas da corda se estiveres a usar uma.",
            "Regressa lentamente até fletir os cotovelos sem perder a posição.",
        ],
    },
    "prancha": {
        "musculo": "Abdómen e estabilizadores do tronco",
        "equipamento": "Tapete ou superfície confortável",
        "passos": [
            "Apoia os antebraços e as pontas dos pés, mantendo os cotovelos sob os ombros.",
            "Alinha cabeça, tronco e pernas e contrai suavemente o abdómen e os glúteos.",
            "Respira de forma contínua, sem deixar a lombar afundar.",
            "Mantém a posição apenas enquanto conservares o alinhamento.",
            "Ajoelha para terminar a série quando a postura começar a falhar.",
        ],
    },
    "dead bug": {
        "musculo": "Abdómen e estabilizadores profundos do tronco",
        "equipamento": "Tapete",
        "passos": [
            "Deita-te de costas com os braços apontados para cima e as ancas e joelhos fletidos.",
            "Mantém a lombar suavemente apoiada no tapete e contrai o abdómen.",
            "Estende lentamente um braço e a perna oposta sem perder o contacto lombar.",
            "Regressa ao centro e repete do outro lado.",
            "Reduz a amplitude se a lombar começar a arquear.",
        ],
    },
    "mountain climbers": {
        "musculo": "Abdómen, ombros e flexores da anca",
        "equipamento": "Peso corporal e tapete opcional",
        "passos": [
            "Começa em posição de prancha alta, mãos sob os ombros e corpo alinhado.",
            "Contrai o abdómen e aproxima um joelho do peito.",
            "Alterna as pernas com um ritmo controlado, sem elevar excessivamente a bacia.",
            "Mantém as mãos firmes e os ombros estáveis.",
            "Abranda ou pára se perderes o alinhamento ou sentires dor.",
        ],
    },
    "remada unilateral com halter": {
        "musculo": "Costas; bíceps como auxiliares",
        "equipamento": "Halter e banco de apoio",
        "passos": [
            "Apoia uma mão e um joelho no banco, mantendo a coluna neutra.",
            "Segura o halter com o braço livre e deixa-o estender sem rodar o tronco.",
            "Puxa o cotovelo em direção à anca, aproximando a omoplata das costas.",
            "Evita encolher o ombro ou rodar o tronco para ganhar balanço.",
            "Desce o halter lentamente e completa o outro lado.",
        ],
    },
    "remada com apoio no peito": {
        "musculo": "Costas; bíceps como auxiliares",
        "equipamento": "Banco inclinado e halteres ou máquina com apoio peitoral",
        "passos": [
            "Ajusta o apoio para o peito ficar firme e confortável.",
            "Segura as pegas ou halteres com os braços estendidos e ombros relaxados.",
            "Puxa os cotovelos para trás sem levantar o peito do apoio.",
            "Aproxima as omoplatas sem encolher os ombros.",
            "Regressa devagar à posição inicial.",
        ],
    },
    "remada baixa na polia": {
        "musculo": "Costas (romboides e latíssimo do dorso); bíceps como auxiliares",
        "equipamento": "Polia baixa e pega",
        "passos": [
            "Senta-te com os pés apoiados e segura a pega com os braços estendidos.",
            "Mantém coluna neutra e tronco estável.",
            "Puxa os cotovelos para trás até à zona do tronco, aproximando as omoplatas.",
            "Evita balançar para trás ou arredondar a lombar.",
            "Estende os braços lentamente e mantém o controlo do cabo.",
        ],
    },
}

EXERCISE_GUIDES.update({
    "press de ombros na máquina": {
        "musculo": "Deltoides; tríceps como auxiliares",
        "equipamento": "Máquina de press de ombros",
        "passos": [
            "Ajusta o assento para as pegas ficarem aproximadamente à altura dos ombros.",
            "Apoia as costas, mantém os pés firmes e segura as pegas com os punhos alinhados.",
            "Empurra as pegas para cima sem arquear a lombar nem elevar os ombros.",
            "Pára antes de bloquear os cotovelos com força.",
            "Regressa lentamente até à posição inicial, seguindo o percurso da máquina.",
        ],
    },
    "supino inclinado na máquina": {
        "musculo": "Peitoral superior; deltoide anterior e tríceps como auxiliares",
        "equipamento": "Máquina de supino inclinado",
        "passos": [
            "Ajusta o assento para as pegas ficarem à altura da parte superior do peito.",
            "Apoia as costas e os pés e mantém os ombros estáveis.",
            "Empurra as pegas para a frente sem levantar as costas do encosto.",
            "Mantém os cotovelos num ângulo confortável e não bloqueies as articulações.",
            "Deixa as pegas regressarem lentamente até uma amplitude confortável.",
        ],
    },
    "flexões": {
        "musculo": "Peitoral; tríceps e deltoide anterior como auxiliares",
        "equipamento": "Peso corporal e tapete opcional",
        "passos": [
            "Coloca as mãos ligeiramente além da largura dos ombros e alinha o corpo da cabeça aos calcanhares.",
            "Contrai o abdómen e os glúteos para manter o tronco estável.",
            "Dobra os cotovelos e baixa o peito de forma controlada.",
            "Mantém os cotovelos num ângulo confortável em relação ao tronco.",
            "Empurra o chão para regressar; usa uma variante inclinada se necessário para preservar a técnica.",
        ],
    },
    "crucifixo na polia": {
        "musculo": "Peitoral",
        "equipamento": "Duas polias ajustáveis com pegas",
        "passos": [
            "Coloca as polias à altura adequada e fica ao centro, com um pé ligeiramente à frente.",
            "Segura as pegas com cotovelos ligeiramente fletidos e tronco firme.",
            "Aproxima as mãos à frente do peito num arco controlado.",
            "Não deixes os ombros avançarem nem transformes o movimento num supino.",
            "Abre os braços lentamente até sentires um alongamento confortável.",
        ],
    },
    "extensão de tríceps acima da cabeça": {
        "musculo": "Tríceps, especialmente a cabeça longa",
        "equipamento": "Polia baixa com corda ou um halter",
        "passos": [
            "Segura a corda ou o halter acima ou atrás da cabeça, mantendo os cotovelos apontados para a frente.",
            "Estabiliza o tronco e evita arquear a lombar.",
            "Estende os cotovelos sem afastá-los excessivamente.",
            "Mantém os braços relativamente imóveis durante a repetição.",
            "Flete os cotovelos lentamente até uma amplitude confortável.",
        ],
    },
    "face pull": {
        "musculo": "Deltoide posterior, trapézio médio e rotadores externos do ombro",
        "equipamento": "Polia alta com corda",
        "passos": [
            "Prende a corda à polia alta e segura as pontas com os polegares voltados para trás.",
            "Afasta-te o suficiente para manter tensão no cabo e estabiliza o tronco.",
            "Puxa a corda em direção ao rosto, separando as mãos e levando os cotovelos para fora.",
            "Mantém os ombros afastados das orelhas e evita inclinar o tronco para trás.",
            "Estende os braços lentamente até à posição inicial.",
        ],
    },
    "crucifixo inverso": {
        "musculo": "Deltoide posterior e parte superior das costas",
        "equipamento": "Halteres, máquina inversa ou polias",
        "passos": [
            "Inclina o tronco com as costas neutras ou ajusta a máquina para apoiar o peito.",
            "Começa com os braços abaixo dos ombros e cotovelos ligeiramente fletidos.",
            "Abre os braços lateralmente, aproximando as omoplatas sem encolher os ombros.",
            "Pára quando os braços se aproximarem da linha do tronco.",
            "Regressa devagar, usando carga leve e movimento controlado.",
        ],
    },
    "peso morto com kettlebell": {
        "musculo": "Glúteos e isquiotibiais; tronco como estabilizador",
        "equipamento": "Kettlebell",
        "passos": [
            "Coloca o kettlebell entre os pés e posiciona os pés aproximadamente à largura da anca.",
            "Leva a anca para trás, flete ligeiramente os joelhos e segura a pega com ambas as mãos.",
            "Mantém a coluna neutra e o kettlebell próximo do corpo.",
            "Empurra o chão e estende a anca para te levantares sem puxar com a lombar.",
            "Baixa o kettlebell com controlo, levando novamente a anca para trás.",
        ],
    },
    "agachamento búlgaro": {
        "musculo": "Quadríceps e glúteos",
        "equipamento": "Banco estável e peso corporal ou halteres",
        "passos": [
            "Coloca o peito do pé de trás num banco estável e posiciona o pé da frente numa distância confortável.",
            "Mantém o tronco firme e o pé da frente totalmente apoiado.",
            "Dobra o joelho da frente para descer verticalmente, alinhando-o com o pé.",
            "Desce apenas até manter equilíbrio e conforto, sem rodar a bacia.",
            "Empurra o chão com o pé da frente para subir e troca de lado.",
        ],
    },
    "extensão de pernas": {
        "musculo": "Quadríceps",
        "equipamento": "Máquina de extensão de pernas",
        "passos": [
            "Ajusta o encosto e o rolo para que o eixo da máquina fique alinhado com o joelho.",
            "Senta-te com as costas apoiadas e segura as pegas.",
            "Estende os joelhos de forma controlada sem dar impulso.",
            "Pára antes de bloquear os joelhos e mantém a contração sem dor.",
            "Baixa o rolo lentamente até à posição inicial.",
        ],
    },
    "flexão de pernas": {
        "musculo": "Isquiotibiais",
        "equipamento": "Máquina de flexão de pernas sentada ou deitada",
        "passos": [
            "Ajusta o rolo à parte inferior das pernas e alinha o eixo da máquina com os joelhos.",
            "Segura as pegas e mantém a bacia apoiada no banco.",
            "Flete os joelhos para aproximar os calcanhares das coxas.",
            "Evita levantar a bacia ou usar balanço.",
            "Estende as pernas lentamente sem deixar os pesos baterem.",
        ],
    },
    "elevação de gémeos em pé": {
        "musculo": "Gastrocnémio e sóleo",
        "equipamento": "Máquina de gémeos em pé ou degrau estável",
        "passos": [
            "Posiciona a parte da frente dos pés na plataforma e apoia-te nas pegas.",
            "Mantém os joelhos estendidos sem os bloquear e o tronco estável.",
            "Eleva os calcanhares até ficares na ponta dos pés.",
            "Faz uma pausa breve no topo sem saltar.",
            "Baixa os calcanhares lentamente até sentires alongamento confortável.",
        ],
    },
    "elevação de gémeos sentado": {
        "musculo": "Sóleo e gastrocnémio",
        "equipamento": "Máquina de gémeos sentado",
        "passos": [
            "Senta-te com a parte da frente dos pés na plataforma e o apoio sobre as coxas.",
            "Mantém os joelhos alinhados com os pés e segura as pegas.",
            "Eleva os calcanhares ao máximo sem levantar a parte da frente dos pés.",
            "Pára brevemente no topo e evita movimentos bruscos.",
            "Desce os calcanhares devagar até à amplitude confortável.",
        ],
    },
    "elevação frontal": {
        "musculo": "Deltoide anterior",
        "equipamento": "Halteres, disco ou polia",
        "passos": [
            "Fica de pé com os braços à frente das coxas e o tronco estável.",
            "Mantém os cotovelos ligeiramente fletidos e os ombros relaxados.",
            "Eleva os braços à frente até aproximadamente à altura dos ombros.",
            "Não uses balanço nem eleves os ombros em direção às orelhas.",
            "Baixa o peso lentamente até à posição inicial.",
        ],
    },
    "bicicleta estática (intervalos)": {
        "musculo": "Sistema cardiovascular; quadríceps e glúteos participam no pedalar",
        "equipamento": "Bicicleta estática",
        "passos": [
            "Ajusta o selim para que o joelho fique ligeiramente fletido quando o pedal está no ponto mais baixo.",
            "Começa com alguns minutos de pedalada leve para aquecer.",
            "Alterna os intervalos de esforço e recuperação definidos no treino, aumentando o ritmo sem perder o controlo.",
            "Mantém o tronco estável e evita resistência que prejudique a pedalada.",
            "Termina com pedalada fácil para baixar gradualmente o ritmo.",
        ],
    },
    "thruster com halteres": {
        "musculo": "Quadríceps, glúteos, ombros e tríceps",
        "equipamento": "Par de halteres",
        "passos": [
            "Segura os halteres à altura dos ombros e coloca os pés aproximadamente à largura dos ombros.",
            "Desce num agachamento controlado, mantendo o peito aberto e os joelhos alinhados com os pés.",
            "Empurra o chão para te levantares e usa esse movimento para iniciar o press.",
            "Empurra os halteres acima da cabeça sem arquear a lombar.",
            "Baixa os halteres de volta aos ombros com controlo antes da repetição seguinte.",
        ],
    },
    "step-ups alternados": {
        "musculo": "Quadríceps e glúteos",
        "equipamento": "Caixa ou degrau estável; halteres opcionais",
        "passos": [
            "Escolhe um degrau baixo e estável e coloca um pé completamente sobre a plataforma.",
            "Mantém o tronco firme e o joelho alinhado com o pé.",
            "Empurra através do pé elevado para subir sem impulsionar excessivamente com a perna de trás.",
            "Desce devagar e com controlo até ao chão.",
            "Alterna a perna de início, mantendo a mesma altura e qualidade de movimento.",
        ],
    },
    "crunch na polia": {
        "musculo": "Abdómen, especialmente o reto abdominal",
        "equipamento": "Polia alta com corda",
        "passos": [
            "Ajoelha-te de frente para a polia e segura a corda junto à cabeça.",
            "Mantém a bacia estável e começa com o tronco alinhado.",
            "Aproxima as costelas da bacia fletindo o tronco, sem puxar com os braços.",
            "Evita sentar-te sobre os calcanhares ou fazer força com o pescoço.",
            "Regressa lentamente à posição inicial mantendo a tensão no abdómen.",
        ],
    },
    "remada alta com halteres": {
        "musculo": "Deltoide lateral e trapézio superior",
        "equipamento": "Par de halteres leves",
        "passos": [
            "Fica de pé com os halteres à frente das coxas e os pés firmes no chão.",
            "Mantém o tronco estável, os ombros relaxados e os cotovelos ligeiramente fletidos.",
            "Eleva os halteres junto ao corpo apenas até uma amplitude confortável para os ombros.",
            "Não forces os cotovelos acima da altura dos ombros nem uses balanço.",
            "Baixa os halteres lentamente; interrompe se sentires dor no ombro.",
        ],
    },
    "encolhimento de ombros com halteres": {
        "musculo": "Trapézio superior",
        "equipamento": "Par de halteres",
        "passos": [
            "Fica de pé com um halter em cada mão e os braços relaxados ao lado do corpo.",
            "Mantém o pescoço neutro e os ombros afastados das orelhas na posição inicial.",
            "Eleva os ombros em direção às orelhas sem rodar nem levar os ombros para a frente.",
            "Faz uma pausa curta no topo sem enrijecer o pescoço.",
            "Desce os ombros lentamente até à posição inicial.",
        ],
    },
})

EXERCISE_GUIDE_ALIASES = {
    "puxada com pega neutra": "puxada na frente",
}


def normalize_exercise_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name.casefold())
    without_accents = "".join(
        character for character in normalized
        if not unicodedata.combining(character)
    )
    return " ".join(
        "".join(
            character if character.isalnum() else " "
            for character in without_accents
        ).split()
    )


def get_exercise_guide(
    exercise_name: str, muscle_group: str = "outros"
) -> dict[str, str | list[str]]:
    normalized_name = normalize_exercise_name(exercise_name)
    guide_key = EXERCISE_GUIDE_ALIASES.get(
        normalized_name, normalized_name
    )
    guide = next(
        (
            content
            for name, content in EXERCISE_GUIDES.items()
            if normalize_exercise_name(name) == guide_key
        ),
        None,
    )
    if guide is not None:
        return guide

    normalized_group = normalize_exercise_name(muscle_group)
    target = {
        "empurrar": "Peitoral, ombros e/ou tríceps (conforme o exercício)",
        "puxar": "Costas e/ou bíceps (conforme o exercício)",
        "pernas": "Quadríceps, glúteos e/ou isquiotibiais (conforme o exercício)",
        "abdomen": "Abdómen e estabilizadores do tronco",
    }.get(normalized_group, "Músculos envolvidos no movimento selecionado")
    equipment = "Confirma o equipamento apropriado para este exercício."
    if "halter" in normalized_name:
        equipment = "Halteres"
    elif "barra" in normalized_name:
        equipment = "Barra e discos"
    elif "polia" in normalized_name or "cabo" in normalized_name:
        equipment = "Polia ou máquina de cabos"
    elif normalized_group == "abdomen":
        equipment = "Tapete ou superfície estável"
    return {
        "musculo": target,
        "equipamento": equipment,
        "passos": [
            "Prepara o equipamento e confirma que está estável e ajustado ao teu corpo.",
            "Assume uma posição confortável, mantém o tronco firme e inicia com uma carga leve.",
            "Executa o movimento de forma lenta e controlada, sem balanço nem dor.",
            "Regressa à posição inicial controlando o movimento e mantendo a respiração.",
            "Como este exercício personalizado não tem instruções específicas no guia, "
            "pede a um profissional para confirmar a técnica antes de aumentar a carga.",
        ],
    }


def show_exercise_guide(exercise_name: str, muscle_group: str) -> None:
    guide = get_exercise_guide(exercise_name, muscle_group)
    with st.expander("📖 Como fazer", expanded=False):
        st.markdown(f"**Músculo alvo:** {guide['musculo']}")
        st.markdown(f"**Equipamento:** {guide['equipamento']}")
        st.markdown("**Execução passo a passo:**")
        for step_number, step in enumerate(guide["passos"], start=1):
            st.markdown(f"{step_number}. {step}")
        try:
            video_url = get_exercise_video_url(exercise_name)
        except ValueError as error:
            st.error(str(error))
            video_url = None
        if video_url:
            st.video(video_url)
        else:
            st.caption(
                "Vídeo de demonstração não configurado. Podes adicionar URLs "
                "HTTPS na secção [exercise_videos] do Streamlit Secrets, usando "
                "o nome do exercício sem acentos como chave."
            )


def get_exercise_video_url(exercise_name: str) -> str | None:
    try:
        configured_videos = st.secrets.get("exercise_videos", {})
    except StreamlitSecretNotFoundError:
        return None

    normalized_name = normalize_exercise_name(exercise_name)
    video_url = configured_videos.get(normalized_name)
    if not video_url:
        video_key = EXERCISE_GUIDE_ALIASES.get(
            normalized_name, normalized_name
        )
        guide_name = next(
            (
                name for name in EXERCISE_GUIDES
                if normalize_exercise_name(name) == video_key
            ),
            None,
        )
        if guide_name is not None:
            video_url = configured_videos.get(
                normalize_exercise_name(guide_name)
            )
    if not video_url:
        return None

    video_url = str(video_url).strip()
    parsed_url = urlparse(video_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError("Os vídeos devem usar um URL HTTPS válido.")
    return video_url


def get_admin_password() -> str | None:
    password = os.environ.get("MEU_TREINO_ADMIN_PASSWORD")
    if password:
        return password

    try:
        password = st.secrets.get("admin_password")
    except StreamlitSecretNotFoundError:
        return None
    return str(password) if password else None


@contextmanager
def database_connection() -> Generator[sqlite3.Connection, None, None]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def init_db() -> bool:
    with database_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_usuario TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'comum'
            );
            CREATE TABLE IF NOT EXISTS treinos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL
                    REFERENCES usuarios(id) ON DELETE CASCADE,
                nome TEXT NOT NULL,
                divisao TEXT NOT NULL DEFAULT '',
                data TEXT NOT NULL DEFAULT '',
                notas TEXT NOT NULL DEFAULT '',
                cardio TEXT NOT NULL DEFAULT '',
                cardio_posicao TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS exercicios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                treino_id INTEGER NOT NULL
                    REFERENCES treinos(id) ON DELETE CASCADE,
                nome TEXT NOT NULL,
                series INTEGER NOT NULL CHECK (series > 0),
                repeticoes TEXT NOT NULL,
                descanso TEXT NOT NULL DEFAULT '60s',
                notas TEXT NOT NULL DEFAULT '',
                grupo_muscular TEXT NOT NULL DEFAULT 'outros'
            );
            CREATE TABLE IF NOT EXISTS presencas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL
                    REFERENCES usuarios(id) ON DELETE CASCADE,
                treino_id INTEGER NOT NULL
                    REFERENCES treinos(id) ON DELETE CASCADE,
                data TEXT NOT NULL,
                duracao_minutos INTEGER NOT NULL DEFAULT 0,
                calorias_kcal INTEGER NOT NULL DEFAULT 0,
                series_total INTEGER NOT NULL DEFAULT 0,
                series_push INTEGER NOT NULL DEFAULT 0,
                series_pull INTEGER NOT NULL DEFAULT 0,
                series_legs INTEGER NOT NULL DEFAULT 0,
                UNIQUE (usuario_id, treino_id, data)
            );
            CREATE INDEX IF NOT EXISTS idx_presencas_usuario_data
                ON presencas(usuario_id, data);
            CREATE TABLE IF NOT EXISTS perfis_treino (
                usuario_id INTEGER PRIMARY KEY
                    REFERENCES usuarios(id) ON DELETE CASCADE,
                objetivo TEXT NOT NULL,
                peso_kg REAL NOT NULL,
                gordura_percent REAL NOT NULL,
                experiencia TEXT NOT NULL,
                consistencia TEXT NOT NULL,
                equipamento TEXT NOT NULL DEFAULT '[]',
                acessorios TEXT NOT NULL DEFAULT '[]',
                treinos_semana INTEGER NOT NULL DEFAULT 3,
                meta_push INTEGER NOT NULL DEFAULT 10,
                meta_pull INTEGER NOT NULL DEFAULT 10,
                meta_pernas INTEGER NOT NULL DEFAULT 10,
                atualizado_em TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS app_migrations (
                nome TEXT PRIMARY KEY
            );
            """
        )

        exercise_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(exercicios)")
        }
        if "descanso" not in exercise_columns:
            connection.execute(
                """
                CREATE TABLE exercicios_novo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    treino_id INTEGER NOT NULL
                        REFERENCES treinos(id) ON DELETE CASCADE,
                    nome TEXT NOT NULL,
                    series INTEGER NOT NULL CHECK (series > 0),
                    repeticoes TEXT NOT NULL,
                    descanso TEXT NOT NULL DEFAULT '60s',
                    notas TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                INSERT INTO exercicios_novo
                    (id, treino_id, nome, series, repeticoes, descanso, notas)
                SELECT id, treino_id, nome, series, repeticoes, '60s', notas
                FROM exercicios
                """
            )
            connection.execute("DROP TABLE exercicios")
            connection.execute("ALTER TABLE exercicios_novo RENAME TO exercicios")
            exercise_columns.add("descanso")
        if "grupo_muscular" not in exercise_columns:
            connection.execute(
                """
                ALTER TABLE exercicios
                ADD COLUMN grupo_muscular TEXT NOT NULL DEFAULT 'outros'
                """
            )

        workout_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(treinos)")
        }
        for column in ("cardio", "cardio_posicao"):
            if column not in workout_columns:
                connection.execute(
                    f"ALTER TABLE treinos ADD COLUMN {column} "
                    "TEXT NOT NULL DEFAULT ''"
                )

        attendance_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(presencas)")
        }
        for column in (
            "duracao_minutos",
            "calorias_kcal",
            "series_total",
            "series_push",
            "series_pull",
            "series_legs",
        ):
            if column not in attendance_columns:
                connection.execute(
                    f"ALTER TABLE presencas ADD COLUMN {column} "
                    "INTEGER NOT NULL DEFAULT 0"
                )

        user_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(usuarios)")
        }
        if "tipo" not in user_columns:
            connection.execute(
                "ALTER TABLE usuarios ADD COLUMN tipo TEXT NOT NULL DEFAULT 'comum'"
            )

        legacy_migration = connection.execute(
            "SELECT 1 FROM app_migrations WHERE nome = 'legacy_english_schema_v1'"
        ).fetchone()
        if legacy_migration is None:
            if table_exists(connection, "users"):
                connection.execute(
                    """
                    INSERT OR IGNORE INTO usuarios
                        (id, nome_usuario, password_salt, password_hash, tipo)
                    SELECT id, username, password_salt, password_hash, 'comum'
                    FROM users
                    """
                )

            if table_exists(connection, "workouts"):
                connection.execute(
                    """
                    INSERT OR IGNORE INTO treinos
                        (id, usuario_id, nome, divisao, data, notas)
                    SELECT id, user_id, name, '', workout_date, notes FROM workouts
                    """
                )

            if table_exists(connection, "exercises"):
                connection.execute(
                    """
                    INSERT OR IGNORE INTO exercicios
                        (id, treino_id, nome, series, repeticoes, descanso, notas)
                    SELECT id, workout_id, name, sets, CAST(reps AS TEXT), '60s', notes
                    FROM exercises
                    """
                )
            connection.execute(
                "INSERT INTO app_migrations (nome) VALUES ('legacy_english_schema_v1')"
            )

        admin = connection.execute(
            "SELECT id, tipo FROM usuarios WHERE nome_usuario = ?",
            (ADMIN_USERNAME,),
        ).fetchone()
        admin_password = get_admin_password()

        if admin is None and admin_password is None:
            return False
        if admin_password is not None and len(admin_password) < 8:
            raise ValueError(
                "A palavra-passe de administrador deve ter pelo menos 8 caracteres."
            )

        if admin is None:
            salt = secrets.token_bytes(16)
            connection.execute(
                """
                INSERT INTO usuarios
                    (nome_usuario, password_salt, password_hash, tipo)
                VALUES (?, ?, ?, 'admin')
                """,
                (
                    ADMIN_USERNAME,
                    salt.hex(),
                    hash_password(admin_password, salt),
                ),
            )
            return True

        if admin["tipo"] != "admin":
            if admin_password is None:
                return False
            salt = secrets.token_bytes(16)
            connection.execute(
                """
                UPDATE usuarios
                SET tipo = 'admin', password_salt = ?, password_hash = ?
                WHERE id = ?
                """,
                (salt.hex(), hash_password(admin_password, salt), admin["id"]),
            )
        return True

def hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    ).hex()


def register_user(username: str, password: str) -> None:
    username = username.strip()
    if not 3 <= len(username) <= 30:
        raise ValueError("O nome de utilizador deve ter entre 3 e 30 caracteres.")
    if username.casefold() == ADMIN_USERNAME.casefold():
        raise ValueError("Esse nome de utilizador está reservado.")
    if len(password) < 8:
        raise ValueError("A palavra-passe deve ter pelo menos 8 caracteres.")

    salt = secrets.token_bytes(16)
    with database_connection() as connection:
        connection.execute(
            """
            INSERT INTO usuarios (nome_usuario, password_salt, password_hash, tipo)
            VALUES (?, ?, ?, 'comum')
            """,
            (username, salt.hex(), hash_password(password, salt)),
        )


def authenticate_user(username: str, password: str) -> sqlite3.Row | None:
    with database_connection() as connection:
        user = connection.execute(
            """
            SELECT id, nome_usuario, password_salt, password_hash, tipo
            FROM usuarios
            WHERE nome_usuario = ?
            """,
            (username.strip(),),
        ).fetchone()

    if user is None:
        return None
    salt = bytes.fromhex(user["password_salt"])
    candidate_hash = hash_password(password, salt)
    if not hmac.compare_digest(candidate_hash, user["password_hash"]):
        return None
    return user


def get_session_user(user_id: int) -> sqlite3.Row | None:
    with database_connection() as connection:
        return connection.execute(
            "SELECT id, nome_usuario, tipo FROM usuarios WHERE id = ?",
            (user_id,),
        ).fetchone()


def get_training_profile(user_id: int) -> dict[str, object] | None:
    with database_connection() as connection:
        profile = connection.execute(
            "SELECT * FROM perfis_treino WHERE usuario_id = ?",
            (user_id,),
        ).fetchone()
    if profile is None:
        return None
    return {
        "objetivo": profile["objetivo"],
        "peso_kg": profile["peso_kg"],
        "gordura_percent": profile["gordura_percent"],
        "experiencia": profile["experiencia"],
        "consistencia": profile["consistencia"],
        "equipamento": json.loads(profile["equipamento"]),
        "acessorios": json.loads(profile["acessorios"]),
        "treinos_semana": profile["treinos_semana"],
        "meta_push": profile["meta_push"],
        "meta_pull": profile["meta_pull"],
        "meta_pernas": profile["meta_pernas"],
    }


def save_training_profile(
    user_id: int,
    objective: str,
    weight_kg: float,
    body_fat_percent: float,
    experience: str,
    consistency: str,
    equipment: list[str],
    accessories: list[str],
    workouts_per_week: int,
    push_goal: int,
    pull_goal: int,
    legs_goal: int,
) -> None:
    if objective not in TRAINING_PROFILES:
        raise ValueError("Seleciona um objetivo válido.")
    if experience not in EXPERIENCE_OPTIONS or consistency not in CONSISTENCY_OPTIONS:
        raise ValueError("Seleciona uma experiência e consistência válidas.")
    if not 30 <= weight_kg <= 300 or not 1 <= body_fat_percent <= 70:
        raise ValueError("Confirma o peso e a percentagem de gordura.")
    if not 1 <= workouts_per_week <= 7:
        raise ValueError("A meta semanal deve ser entre 1 e 7 treinos.")
    if not all(1 <= goal <= 40 for goal in (push_goal, pull_goal, legs_goal)):
        raise ValueError("As metas de séries devem estar entre 1 e 40.")
    if not set(equipment).issubset(EQUIPMENT_OPTIONS):
        raise ValueError("A seleção de equipamento contém opções inválidas.")
    if not equipment:
        raise ValueError("Seleciona pelo menos um tipo de equipamento.")

    with database_connection() as connection:
        connection.execute(
            """
            INSERT INTO perfis_treino (
                usuario_id, objetivo, peso_kg, gordura_percent, experiencia,
                consistencia, equipamento, acessorios, treinos_semana,
                meta_push, meta_pull, meta_pernas, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(usuario_id) DO UPDATE SET
                objetivo = excluded.objetivo,
                peso_kg = excluded.peso_kg,
                gordura_percent = excluded.gordura_percent,
                experiencia = excluded.experiencia,
                consistencia = excluded.consistencia,
                equipamento = excluded.equipamento,
                acessorios = excluded.acessorios,
                treinos_semana = excluded.treinos_semana,
                meta_push = excluded.meta_push,
                meta_pull = excluded.meta_pull,
                meta_pernas = excluded.meta_pernas,
                atualizado_em = excluded.atualizado_em
            """,
            (
                user_id,
                objective,
                weight_kg,
                body_fat_percent,
                experience,
                consistency,
                json.dumps(equipment),
                json.dumps(accessories),
                workouts_per_week,
                push_goal,
                pull_goal,
                legs_goal,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def require_admin(connection: sqlite3.Connection, admin_id: int) -> None:
    admin = connection.execute(
        """
        SELECT 1 FROM usuarios
        WHERE id = ? AND tipo = 'admin'
          AND nome_usuario = ? COLLATE NOCASE
        """,
        (admin_id, ADMIN_USERNAME),
    ).fetchone()
    if admin is None:
        raise PermissionError("Esta operação requer a conta administradora.")


def get_admin_users(admin_id: int) -> list[sqlite3.Row]:
    with database_connection() as connection:
        require_admin(connection, admin_id)
        return connection.execute(
            """
            SELECT usuarios.id, usuarios.nome_usuario, usuarios.tipo,
                   COUNT(DISTINCT treinos.id) AS total_treinos
            FROM usuarios
            LEFT JOIN treinos ON treinos.usuario_id = usuarios.id
            GROUP BY usuarios.id
            ORDER BY usuarios.nome_usuario COLLATE NOCASE
            """
        ).fetchall()


def get_admin_workouts(admin_id: int) -> list[sqlite3.Row]:
    with database_connection() as connection:
        require_admin(connection, admin_id)
        return connection.execute(
            """
            SELECT treinos.id, treinos.nome, treinos.divisao, treinos.data,
                   usuarios.nome_usuario,
                   COUNT(exercicios.id) AS total_exercicios
            FROM treinos
            JOIN usuarios ON usuarios.id = treinos.usuario_id
            LEFT JOIN exercicios ON exercicios.treino_id = treinos.id
            GROUP BY treinos.id
            ORDER BY treinos.id DESC
            """
        ).fetchall()


def delete_user_account(admin_id: int, user_id: int) -> None:
    if user_id == admin_id:
        raise ValueError("A conta administradora não pode ser apagada.")

    with database_connection() as connection:
        require_admin(connection, admin_id)
        result = connection.execute(
            """
            DELETE FROM usuarios
            WHERE id = ? AND nome_usuario != ? COLLATE NOCASE
            """,
            (user_id, ADMIN_USERNAME),
        )
        if result.rowcount == 0:
            raise ValueError("O utilizador não existe ou não pode ser apagado.")


def get_workouts(user_id: int) -> list[sqlite3.Row]:
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT id, nome, divisao, data, notas, cardio, cardio_posicao
            FROM treinos
            WHERE usuario_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()


def get_attendance(user_id: int) -> list[sqlite3.Row]:
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT presencas.id, presencas.data, treinos.nome AS treino,
                   treinos.divisao, presencas.duracao_minutos,
                   presencas.calorias_kcal, presencas.series_total,
                   presencas.series_push, presencas.series_pull,
                   presencas.series_legs
            FROM presencas
            JOIN treinos ON treinos.id = presencas.treino_id
            WHERE presencas.usuario_id = ?
            ORDER BY presencas.data DESC, presencas.id DESC
            """,
            (user_id,),
        ).fetchall()


def has_attendance(user_id: int, workout_id: int, completed_on: date) -> bool:
    with database_connection() as connection:
        return (
            connection.execute(
                """
                SELECT 1 FROM presencas
                WHERE usuario_id = ? AND treino_id = ? AND data = ?
                """,
                (user_id, workout_id, completed_on.isoformat()),
            ).fetchone()
            is not None
        )


def show_quick_attendance(user_id: int) -> None:
    workouts = get_workouts(user_id)
    with st.sidebar:
        st.divider()
        st.subheader("Registo rápido")
        if not workouts:
            st.caption("Cria uma ficha para poderes registar um treino.")
            return

        today = date.today()
        workout_id = st.selectbox(
            "Treino concluído hoje",
            options=[workout["id"] for workout in workouts],
            format_func=lambda selected_id: next(
                workout["nome"]
                for workout in workouts
                if workout["id"] == selected_id
            ),
            key=f"attendance_workout_{user_id}",
        )
        already_recorded = has_attendance(user_id, workout_id, today)
        duration_minutes = st.number_input(
            "Duração (minutos)",
            min_value=0,
            max_value=600,
            value=45,
            step=5,
            key=f"attendance_duration_{user_id}",
        )
        calories_kcal = st.number_input(
            "Calorias (opcional)",
            min_value=0,
            max_value=10000,
            value=0,
            step=25,
            help="Podes introduzir a estimativa do teu relógio ou equipamento.",
            key=f"attendance_calories_{user_id}",
        )
        if already_recorded:
            st.success("Este treino já está registado para hoje.")
        if st.button(
            "✅ Marcar treino como concluído",
            disabled=already_recorded,
            key=f"record_attendance_{user_id}_{today.isoformat()}",
            width="stretch",
        ):
            try:
                record_attendance(
                    user_id,
                    workout_id,
                    today,
                    int(duration_minutes),
                    int(calories_kcal),
                )
            except ValueError as error:
                st.error(str(error))
            else:
                st.success("Treino registado no histórico.")
                st.rerun()


def record_attendance(
    user_id: int,
    workout_id: int,
    completed_on: date | None = None,
    duration_minutes: int = 0,
    calories_kcal: int = 0,
) -> None:
    if not 0 <= duration_minutes <= 600:
        raise ValueError("A duração deve estar entre 0 e 600 minutos.")
    if not 0 <= calories_kcal <= 10000:
        raise ValueError("As calorias devem estar entre 0 e 10 000 kcal.")
    completed_on = completed_on or date.today()
    with database_connection() as connection:
        result = connection.execute(
            """
            INSERT INTO presencas (
                usuario_id, treino_id, data, duracao_minutos,
                calorias_kcal, series_total, series_push, series_pull,
                series_legs
            )
            SELECT ?, ?, ?, ?, ?,
                   COALESCE((
                       SELECT SUM(exercicios.series)
                       FROM exercicios
                       WHERE exercicios.treino_id = ?
                   ), 0),
                   COALESCE((
                       SELECT SUM(exercicios.series)
                       FROM exercicios
                       WHERE exercicios.treino_id = ?
                         AND lower(exercicios.grupo_muscular) = 'empurrar'
                   ), 0),
                   COALESCE((
                       SELECT SUM(exercicios.series)
                       FROM exercicios
                       WHERE exercicios.treino_id = ?
                         AND lower(exercicios.grupo_muscular) = 'puxar'
                   ), 0),
                   COALESCE((
                       SELECT SUM(exercicios.series)
                       FROM exercicios
                       WHERE exercicios.treino_id = ?
                         AND lower(exercicios.grupo_muscular) = 'pernas'
                   ), 0)
            WHERE EXISTS (
                SELECT 1 FROM treinos
                WHERE id = ? AND usuario_id = ?
            )
              AND NOT EXISTS (
                SELECT 1 FROM presencas
                WHERE usuario_id = ? AND treino_id = ? AND data = ?
            )
            """,
            (
                user_id,
                workout_id,
                completed_on.isoformat(),
                duration_minutes,
                calories_kcal,
                workout_id,
                workout_id,
                workout_id,
                workout_id,
                workout_id,
                user_id,
                user_id,
                workout_id,
                completed_on.isoformat(),
            ),
        )
        if result.rowcount == 0:
            raise ValueError(
                "O treino não pertence à tua conta ou já foi registado nessa data."
            )


def create_workout(
    user_id: int,
    name: str,
    division: str,
    notes: str,
    cardio: str = "",
    cardio_position: str = "",
) -> None:
    with database_connection() as connection:
        connection.execute(
            """
            INSERT INTO treinos
                (usuario_id, nome, divisao, notas, cardio, cardio_posicao)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                name.strip(),
                division.strip(),
                notes.strip(),
                cardio,
                cardio_position,
            ),
        )


def delete_workout(workout_id: int, user_id: int) -> None:
    with database_connection() as connection:
        connection.execute(
            "DELETE FROM treinos WHERE id = ? AND usuario_id = ?",
            (workout_id, user_id),
        )


def get_exercises(workout_id: int, user_id: int) -> list[sqlite3.Row]:
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT exercicios.id, exercicios.nome, exercicios.series,
                   exercicios.repeticoes, exercicios.descanso, exercicios.notas,
                   exercicios.grupo_muscular
            FROM exercicios
            JOIN treinos ON treinos.id = exercicios.treino_id
            WHERE exercicios.treino_id = ? AND treinos.usuario_id = ?
            ORDER BY exercicios.id
            """,
            (workout_id, user_id),
        ).fetchall()


def create_exercise(
    workout_id: int,
    user_id: int,
    name: str,
    sets: int,
    reps: str,
    rest_time: str,
    muscle_group: str = "outros",
) -> None:
    with database_connection() as connection:
        connection.execute(
            """
            INSERT INTO exercicios
                (treino_id, nome, series, repeticoes, descanso, grupo_muscular)
            SELECT ?, ?, ?, ?, ?, ?
            WHERE EXISTS (
                SELECT 1 FROM treinos
                WHERE id = ? AND usuario_id = ?
            )
            """,
            (
                workout_id,
                name.strip(),
                sets,
                reps.strip(),
                rest_time.strip(),
                muscle_group,
                workout_id,
                user_id,
            ),
        )


def generate_smart_workout(
    focus: str, profile_name: str, recovery: str
) -> list[dict[str, str | int]]:
    if focus not in SMART_WORKOUTS:
        raise ValueError("Divisão de treino inválida.")
    if profile_name not in TRAINING_PROFILES:
        raise ValueError("Perfil de treino inválido.")

    profile = TRAINING_PROFILES[profile_name]
    low_recovery = recovery == "Baixa (menos volume)"
    exercises = []
    for name, exercise_type in SMART_WORKOUTS[focus]:
        if exercise_type == "hiit":
            sets = profile["series_multiarticulares"]
            reps = "30 s de esforço / 30 s de recuperação ativa"
            rest_seconds = 30
        elif exercise_type == "abdomen":
            sets = profile["series_isolados"]
            reps = (
                "30-45 s" if name == "Prancha"
                else profile["repeticoes_isolados"]
            )
            rest_seconds = profile["descanso_isolados"]
        elif exercise_type == "multiarticular":
            sets = profile["series_multiarticulares"]
            reps = profile["repeticoes_multiarticulares"]
            rest_seconds = profile["descanso_multiarticulares"]
        else:
            sets = profile["series_isolados"]
            reps = profile["repeticoes_isolados"]
            rest_seconds = profile["descanso_isolados"]

        if low_recovery:
            sets = max(1, sets - 1)
            rest_seconds += 30
        muscle_group = infer_muscle_group(name, focus)
        exercises.append(
            {
                "nome": name,
                "tipo": exercise_type,
                "grupo_muscular": muscle_group,
                "series": sets,
                "repeticoes": reps,
                "descanso": f"{rest_seconds}s",
            }
        )
    return exercises


def recommend_weekly_split(workouts_per_week: int) -> list[str]:
    if workouts_per_week <= 3:
        return ["Full Body"] * workouts_per_week
    if workouts_per_week == 4:
        return ["Upper", "Lower", "Upper", "Lower"]
    if workouts_per_week == 5:
        return ["Push A", "Pull A", "Legs A", "Upper", "Lower"]
    if workouts_per_week == 6:
        return ["Push A", "Pull A", "Legs A", "Push B", "Pull B", "Legs B"]
    return [
        "Push A",
        "Pull A",
        "Legs A",
        "Upper",
        "Lower",
        "Full Body",
        "Recuperação",
    ]


def infer_muscle_group(exercise_name: str, focus: str) -> str:
    if focus.startswith("Legs") or focus == "Lower":
        return "pernas"
    if focus.startswith("Push"):
        return "empurrar"
    if focus.startswith("Pull"):
        return "puxar"
    name = exercise_name.casefold()
    if any(
        word in name
        for word in ("agachamento", "leg press", "peso morto", "hip thrust",
                     "step-up", "gémeos", "pernas")
    ):
        return "pernas"
    if any(
        word in name
        for word in ("supino", "press", "flexões", "tríceps", "elevação lateral",
                     "elevação frontal", "thruster")
    ):
        return "empurrar"
    if any(
        word in name
        for word in ("remada", "puxada", "curl", "bíceps", "face pull",
                     "crucifixo inverso", "encolhimento")
    ):
        return "puxar"
    return "outros"


def save_smart_workout(
    user_id: int,
    name: str,
    focus: str,
    profile_name: str,
    weight_kg: float,
    body_fat_percent: float,
    recovery: str,
    exercises: list[dict[str, str | int]],
    cardio: str = "",
    cardio_position: str = "",
    workout_date: str = "",
) -> None:
    notes = (
        f"Perfil: {profile_name} ({weight_kg:g} kg, "
        f"{body_fat_percent:g}% de gordura corporal). "
        f"Objetivo: {TRAINING_PROFILES[profile_name]['objetivo']}. "
        f"Recuperação: {recovery}."
    )
    with database_connection() as connection:
        workout = connection.execute(
            """
            INSERT INTO treinos
                (usuario_id, nome, divisao, data, notas, cardio, cardio_posicao)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                name.strip(),
                focus,
                workout_date,
                notes,
                cardio,
                cardio_position,
            ),
        )
        for exercise in exercises:
            connection.execute(
                """
                INSERT INTO exercicios
                    (treino_id, nome, series, repeticoes, descanso, grupo_muscular)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    workout.lastrowid,
                    exercise["nome"],
                    exercise["series"],
                    exercise["repeticoes"],
                    exercise["descanso"],
                    exercise["grupo_muscular"],
                ),
            )


def has_saved_smart_workout(user_id: int, workout_date: str, name: str) -> bool:
    with database_connection() as connection:
        return (
            connection.execute(
                """
                SELECT 1 FROM treinos
                WHERE usuario_id = ? AND data = ? AND nome = ?
                """,
                (user_id, workout_date, name),
            ).fetchone()
            is not None
        )


def delete_exercise(exercise_id: int, workout_id: int, user_id: int) -> None:
    with database_connection() as connection:
        connection.execute(
            """
            DELETE FROM exercicios
            WHERE id = ? AND treino_id = ?
              AND EXISTS (
                  SELECT 1 FROM treinos
                  WHERE treinos.id = exercicios.treino_id
                    AND usuario_id = ?
              )
            """,
            (exercise_id, workout_id, user_id),
        )


def show_authentication_page() -> None:
    st.markdown(
        """
        <div class="brand-mark">🏋️‍♂️</div>
        <h1 class="auth-title">Meu Treino</h1>
        <p class="auth-subtitle">As tuas fichas de treino, sempre contigo.</p>
        """,
        unsafe_allow_html=True,
    )
    login_tab, register_tab = st.tabs(["Entrar", "Criar Conta"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Nome de utilizador")
            password = st.text_input("Palavra-passe", type="password")
            submitted = st.form_submit_button(
                "Entrar", type="primary", width="stretch"
            )
        if submitted:
            user = authenticate_user(username, password)
            if user is None:
                st.error("Nome de utilizador ou palavra-passe incorretos.")
            else:
                st.session_state.user = {
                    "id": user["id"],
                    "username": user["nome_usuario"],
                    "tipo": user["tipo"],
                }
                st.rerun()

    with register_tab:
        with st.form("register_form"):
            new_username = st.text_input("Nome de utilizador", key="new_username")
            new_password = st.text_input(
                "Palavra-passe (mínimo 8 caracteres)",
                type="password",
                key="new_password",
            )
            confirm_password = st.text_input(
                "Confirmar palavra-passe",
                type="password",
                key="confirm_password",
            )
            submitted = st.form_submit_button(
                "Criar conta", type="primary", width="stretch"
            )
        if submitted:
            if new_password != confirm_password:
                st.error("As palavras-passe não coincidem.")
            else:
                try:
                    register_user(new_username, new_password)
                except ValueError as error:
                    st.error(str(error))
                except sqlite3.IntegrityError:
                    st.error("Esse nome de utilizador já está em uso.")
                else:
                    user = authenticate_user(new_username, new_password)
                    if user is None:
                        st.error(
                            "A conta foi criada, mas não foi possível iniciar sessão."
                        )
                    else:
                        st.session_state.user = {
                            "id": user["id"],
                            "username": user["nome_usuario"],
                            "tipo": user["tipo"],
                        }
                        st.rerun()


def show_profile_form(user_id: int, initial_setup: bool = False) -> None:
    profile = get_training_profile(user_id)
    st.subheader("Configuração do perfil e metas")
    if initial_setup:
        st.write(
            "Vamos preparar um plano inicial. Podes ajustar estas preferências "
            "mais tarde no separador Perfil."
        )
    objective_options = list(TRAINING_PROFILES)
    current_objective = profile["objetivo"] if profile else objective_options[3]
    objective_index = (
        objective_options.index(current_objective)
        if current_objective in objective_options
        else 0
    )
    experience_options = EXPERIENCE_OPTIONS
    consistency_options = CONSISTENCY_OPTIONS
    equipment_defaults = profile["equipamento"] if profile else ["Academia completa"]
    accessory_options = [
        "Barra de treino",
        "Discos pequenos / microcargas",
        "Banco ajustável",
        "Suporte de agachamento",
    ]
    current_accessories = profile["acessorios"] if profile else []
    with st.form(f"training_profile_{user_id}"):
        objective = st.selectbox(
            "Meta principal",
            objective_options,
            index=objective_index,
        )
        physical = st.columns(2)
        with physical[0]:
            weight_kg = st.number_input(
                "Peso (kg)",
                min_value=30.0,
                max_value=300.0,
                value=float(profile["peso_kg"]) if profile else 85.0,
                step=0.5,
            )
        with physical[1]:
            body_fat = st.number_input(
                "Gordura corporal (%)",
                min_value=1.0,
                max_value=70.0,
                value=float(profile["gordura_percent"]) if profile else 30.0,
                step=0.5,
            )
        experience = st.selectbox(
            "Experiência de treino",
            experience_options,
            index=(
                experience_options.index(profile["experiencia"])
                if profile and profile["experiencia"] in experience_options
                else 0
            ),
        )
        consistency = st.selectbox(
            "Consistência recente",
            consistency_options,
            index=(
                consistency_options.index(profile["consistencia"])
                if profile and profile["consistencia"] in consistency_options
                else 0
            ),
        )
        equipment = st.multiselect(
            "Equipamento disponível",
            EQUIPMENT_OPTIONS,
            default=equipment_defaults,
            help="Seleciona todo o equipamento a que tens acesso.",
        )
        accessories = st.multiselect(
            "Barras, pesos pequenos e acessórios",
            accessory_options,
            default=[
                item for item in current_accessories if item in accessory_options
            ],
        )
        workouts_per_week = st.slider(
            "Meta de treinos por semana",
            min_value=1,
            max_value=7,
            value=int(profile["treinos_semana"]) if profile else 3,
        )
        st.markdown("#### Metas semanais de séries")
        goal_columns = st.columns(3)
        with goal_columns[0]:
            push_goal = st.number_input(
                "Empurrar",
                min_value=1,
                max_value=40,
                value=int(profile["meta_push"]) if profile else 10,
            )
        with goal_columns[1]:
            pull_goal = st.number_input(
                "Puxar",
                min_value=1,
                max_value=40,
                value=int(profile["meta_pull"]) if profile else 10,
            )
        with goal_columns[2]:
            legs_goal = st.number_input(
                "Pernas",
                min_value=1,
                max_value=40,
                value=int(profile["meta_pernas"]) if profile else 10,
            )
        submitted = st.form_submit_button(
            "Guardar perfil e metas",
            type="primary",
            width="stretch",
        )
    if submitted:
        try:
            save_training_profile(
                user_id,
                objective,
                weight_kg,
                body_fat,
                experience,
                consistency,
                equipment,
                accessories,
                int(workouts_per_week),
                int(push_goal),
                int(pull_goal),
                int(legs_goal),
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.success("Perfil e metas guardados.")
            st.rerun()


def show_workout_cards(user_id: int) -> None:
    workouts = get_workouts(user_id)
    if not workouts:
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-icon">📋</div>
                <strong>Ainda não tens fichas</strong>
                <p>Cria a tua primeira ficha no separador “Criar Novo Treino”.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    workout = st.selectbox(
        "Ficha ativa",
        options=[item["id"] for item in workouts],
        format_func=lambda workout_id: next(
            (
                f"{item['nome']} · {item['divisao']}"
                if item["divisao"]
                else item["nome"]
            )
            for item in workouts
            if item["id"] == workout_id
        ),
        key=f"active_workout_{user_id}",
        label_visibility="collapsed",
    )
    workout_id = workout
    workout = next(item for item in workouts if item["id"] == workout_id)
    workout_name = html.escape(workout["nome"])
    workout_division = html.escape(workout["divisao"] or "Treino personalizado")
    st.markdown(
        f'<div class="workout-heading"><h2>{workout_name}</h2>'
        f'<span>{workout_division}</span></div>',
        unsafe_allow_html=True,
    )
    if workout["notas"]:
        st.caption(workout["notas"])
    if workout["cardio"]:
        st.info(
            f"Cardio {workout['cardio_posicao'].casefold()}: {workout['cardio']}"
        )

    exercises = get_exercises(workout_id, user_id)
    if not exercises:
        st.info("Esta ficha ainda não tem exercícios. Adiciona o primeiro abaixo.")
    else:
        for exercise in exercises:
            with st.container(border=True):
                card, delete = st.columns([6, 1], vertical_alignment="top")
                with card:
                    st.markdown(f"**{exercise['nome']}**")
                    metrics = st.columns(3)
                    metrics[0].metric("Séries", exercise["series"])
                    metrics[1].metric("Repetições", exercise["repeticoes"])
                    metrics[2].metric(
                        "Tempo de descanso", exercise["descanso"]
                    )
                    if exercise["notas"]:
                        st.caption(exercise["notas"])
                    show_exercise_guide(
                        exercise["nome"], exercise["grupo_muscular"]
                    )
                with delete:
                    if st.button(
                        "🗑️",
                        key=f"delete_exercise_{exercise['id']}",
                        help="Apagar exercício",
                        width="stretch",
                    ):
                        delete_exercise(exercise["id"], workout_id, user_id)
                        st.rerun()

    with st.expander("➕ Adicionar exercício", expanded=not exercises):
        with st.form(f"add_exercise_{workout_id}"):
            name = st.text_input("Nome do exercício", placeholder="Ex.: Supino reto")
            sets = st.number_input("Séries", min_value=1, value=3, step=1)
            reps = st.text_input(
                "Repetições",
                value="8-12",
                help="Podes indicar um intervalo, por exemplo 8-12.",
            )
            muscle_group = st.selectbox(
                "Grupo muscular",
                ["Empurrar", "Puxar", "Pernas", "Outros"],
                key=f"exercise_group_{workout_id}",
            )
            rest_time = st.number_input(
                "Tempo de descanso (segundos)",
                min_value=15,
                max_value=300,
                value=60,
                step=15,
                help="Escolhe um tempo entre 15 e 300 segundos.",
            )
            submitted = st.form_submit_button(
                "Adicionar exercício", type="primary", width="stretch"
            )
        if submitted:
            if not name.strip() or not reps.strip():
                st.error("Preenche o nome e as repetições.")
            else:
                create_exercise(
                    workout_id,
                    user_id,
                    name,
                    int(sets),
                    reps,
                    f"{int(rest_time)}s",
                    muscle_group.casefold(),
                )
                st.rerun()

    st.markdown("")
    if st.button(
        "🗑️ Apagar esta ficha de treino",
        key=f"delete_workout_{workout_id}",
        width="stretch",
    ):
        delete_workout(workout_id, user_id)
        st.session_state.pop(f"active_workout_{user_id}", None)
        st.rerun()


def show_create_workout_form(user_id: int) -> None:
    st.subheader("Criar uma ficha")
    st.caption("Organiza os exercícios por objetivo ou grupo muscular.")
    with st.form("create_workout_form"):
        name = st.text_input("Nome do treino", placeholder="Ex.: Treino A")
        division = st.selectbox(
            "Divisão / foco muscular",
            [
                "Peito / Tríceps",
                "Costas / Bíceps",
                "Pernas",
                "Ombros",
                "Full body",
                *SMART_WORKOUTS,
                "Outro",
            ],
        )
        if division == "Outro":
            division = st.text_input(
                "Indica a divisão muscular", placeholder="Ex.: Peito e ombros"
            )
        notes = st.text_area("Notas (opcional)")
        cardio = st.selectbox("Recomendação de cardio", CARDIO_OPTIONS)
        cardio_position = ""
        if cardio != "Sem cardio":
            cardio_position = st.radio(
                "Quando fazer o cardio?",
                ["Antes do treino", "Depois do treino"],
                horizontal=True,
            )
        submitted = st.form_submit_button(
            "Criar ficha de treino", type="primary", width="stretch"
        )
    if submitted:
        if not name.strip() or not division.strip():
            st.error("Preenche o nome e a divisão muscular do treino.")
        else:
            create_workout(
                user_id,
                name,
                division,
                notes,
                "" if cardio == "Sem cardio" else cardio,
                cardio_position,
            )
            st.success("Ficha de treino criada.")
            st.rerun()


def get_weekly_workout_schedule(workouts_per_week: int) -> tuple[str, ...]:
    schedules = {
        1: ("Recuperação", "Recuperação", "Full Body", "Recuperação",
            "Recuperação", "Recuperação", "Recuperação"),
        2: ("Upper", "Recuperação", "Recuperação", "Lower",
            "Recuperação", "Recuperação", "Recuperação"),
        3: ("Pull A", "Recuperação", "Push A", "Recuperação",
            "Legs A", "Recuperação", "Recuperação"),
        4: ("Upper", "Lower", "Recuperação", "Upper",
            "Lower", "Recuperação", "Recuperação"),
        5: ("Pull A", "Push A", "Legs A", "Recuperação",
            "Upper", "Lower", "Recuperação"),
        6: WEEKLY_WORKOUT_SCHEDULE,
        7: ("Pull A", "Push A", "Legs A", "Upper",
            "Pull B", "Legs B", "Recuperação"),
    }
    try:
        return schedules[workouts_per_week]
    except KeyError as error:
        raise ValueError("A meta semanal deve ser entre 1 e 7 treinos.") from error


def get_daily_workout_suggestion(
    now: datetime | None = None, workouts_per_week: int = 6
) -> dict[str, str]:
    current_time = now or datetime.now()
    weekday = current_time.weekday()
    return {
        "weekday": WEEKDAY_NAMES[weekday],
        "focus": get_weekly_workout_schedule(workouts_per_week)[weekday],
        "date": current_time.date().isoformat(),
    }


def render_exercise_recommendations(
    exercises: list[dict[str, str | int]],
) -> None:
    for exercise in exercises:
        with st.container(border=True):
            st.markdown(f"**{exercise['nome']}**")
            metrics = st.columns(3)
            metrics[0].metric("Séries", exercise["series"])
            metrics[1].metric("Repetições", exercise["repeticoes"])
            metrics[2].metric("Tempo de descanso", exercise["descanso"])
            show_exercise_guide(
                exercise["nome"],
                str(exercise.get("grupo_muscular", "outros")),
            )


def show_daily_workout(user_id: int) -> None:
    profile = get_training_profile(user_id)
    workouts_per_week = int(profile["treinos_semana"]) if profile else 6
    suggestion = get_daily_workout_suggestion(
        workouts_per_week=workouts_per_week
    )
    st.subheader(f"Treino de hoje · {suggestion['weekday']}")
    st.caption(
        f"Plano semanal automático para {suggestion['date']}. "
        "A data e o dia da semana são determinados pelo relógio local do servidor."
    )
    schedule_frame = pd.DataFrame(
        [
            {
                "Dia": weekday,
                "Sugestão": focus,
                "Estado": "Recuperação" if focus == "Recuperação" else "Treino",
            }
            for weekday, focus in zip(
                WEEKDAY_NAMES,
                get_weekly_workout_schedule(workouts_per_week),
            )
        ]
    )
    st.dataframe(schedule_frame, width="stretch", hide_index=True)

    focus = suggestion["focus"]
    if focus == "Recuperação":
        st.info(
            "Hoje está reservado para recuperação. Podes fazer mobilidade leve "
            "ou uma caminhada confortável, se isso fizer parte da tua rotina."
        )
        return
    objective = str(profile["objetivo"]) if profile else "Perder peso"
    weight_kg = float(profile["peso_kg"]) if profile else 85.0
    body_fat = float(profile["gordura_percent"]) if profile else 30.0
    exercises = generate_smart_workout(focus, objective, "Normal")
    st.markdown(f"#### Plano sugerido: {focus}")
    render_exercise_recommendations(exercises)

    workout_name = f"{suggestion['date']} · {focus}"
    already_saved = has_saved_smart_workout(
        user_id, suggestion["date"], workout_name
    )
    if already_saved:
        st.success("O treino de hoje já está guardado em Minhas Fichas.")
    if st.button(
        "📥 Carregar treino de hoje para Minhas Fichas",
        type="primary",
        disabled=already_saved,
        key=f"load_daily_workout_{user_id}_{suggestion['date']}",
        width="stretch",
    ):
        save_smart_workout(
            user_id=user_id,
            name=workout_name,
            focus=focus,
            profile_name=objective,
            weight_kg=weight_kg,
            body_fat_percent=body_fat,
            recovery="Normal",
            exercises=exercises,
            workout_date=suggestion["date"],
        )
        st.rerun()


def show_body_focus_generator(user_id: int) -> None:
    profile = get_training_profile(user_id)
    st.subheader("Gerar treino por grupo muscular")
    if st.session_state.pop(f"body_focus_saved_{user_id}", False):
        st.success("Treino focado guardado em Minhas Fichas.")
    focus_options = [
        "Pernas Completo",
        "Ombros",
        "Braços",
        "Abdómen",
        "Peito",
        "Costas",
        "Full Body",
    ]
    focus = st.selectbox(
        "Escolhe a parte do corpo",
        focus_options,
        key=f"body_focus_{user_id}",
    )
    objective_options = list(TRAINING_PROFILES)
    stored_objective = str(profile["objetivo"]) if profile else "Perder peso"
    objective = st.selectbox(
        "Objetivo",
        objective_options,
        index=(
            objective_options.index(stored_objective)
            if stored_objective in objective_options
            else 0
        ),
        key=f"body_focus_objective_{user_id}",
    )
    recovery = st.selectbox(
        "Recuperação",
        ["Normal", "Baixa (menos volume)"],
        key=f"body_focus_recovery_{user_id}",
    )
    state_key = f"body_focus_suggestion_{user_id}"
    if st.button(
        "Gerar treino focado",
        type="primary",
        key=f"generate_body_focus_{user_id}",
        width="stretch",
    ):
        st.session_state[state_key] = {
            "focus": focus,
            "objective": objective,
            "recovery": recovery,
            "exercises": generate_smart_workout(
                focus, objective, recovery
            ),
        }

    suggestion = st.session_state.get(state_key)
    if not suggestion:
        return
    st.markdown(f"#### {suggestion['focus']} · {suggestion['objective']}")
    render_exercise_recommendations(suggestion["exercises"])
    name = st.text_input(
        "Nome da ficha",
        value=f"Treino {suggestion['focus']}",
        key=f"body_focus_name_{user_id}",
    )
    if st.button(
        "Guardar treino focado",
        key=f"save_body_focus_{user_id}",
        width="stretch",
    ):
        if not name.strip():
            st.error("Indica um nome para a ficha.")
        else:
            weight = float(profile["peso_kg"]) if profile else 85.0
            body_fat = (
                float(profile["gordura_percent"]) if profile else 30.0
            )
            save_smart_workout(
                user_id,
                name,
                suggestion["focus"],
                suggestion["objective"],
                weight,
                body_fat,
                suggestion["recovery"],
                suggestion["exercises"],
            )
            st.session_state[f"body_focus_saved_{user_id}"] = True
            st.rerun()


def show_smart_workout_generator(user_id: int) -> None:
    user_profile = get_training_profile(user_id)
    st.subheader("Gerar Treino Inteligente")
    if st.session_state.pop(f"smart_saved_{user_id}", False):
        st.success("Treino inteligente guardado nas tuas fichas.")
    st.caption(
        "Escolhe um objetivo, ajusta os teus dados físicos e seleciona a divisão "
        "adequada para o treino de hoje."
    )
    st.info(
        "O perfil ajusta o volume, as repetições e o descanso recomendados. "
        "As cargas são sempre escolhidas por ti, de acordo com a técnica e o esforço."
    )
    if user_profile:
        split = recommend_weekly_split(int(user_profile["treinos_semana"]))
        st.markdown("#### Plano semanal sugerido")
        st.write(" · ".join(f"{day}: {focus}" for day, focus in enumerate(split, 1)))
        st.caption(
            f"Experiência: {user_profile['experiencia']} · "
            f"Consistência: {user_profile['consistencia']}"
        )
    with st.expander("🎯 Calibração e escolha da carga"):
        rir_target = st.select_slider(
            "Repetições que deves conseguir fazer ainda no fim da série (RIR)",
            options=[1, 2, 3, 4],
            value=2,
            key=f"smart_rir_{user_id}",
        )
        st.write(
            f"Começa com uma carga leve de aquecimento; escolhe uma carga que "
            f"permita completar o intervalo recomendado mantendo cerca de "
            f"{rir_target} repetições em reserva e técnica estável. Aumenta a carga "
            "gradualmente apenas quando completares todas as séries com controlo."
        )
    objective_options = list(TRAINING_PROFILES)
    selected_objective = (
        str(user_profile["objetivo"]) if user_profile else objective_options[3]
    )
    profile_widget_key = f"smart_profile_{user_id}"
    if st.session_state.get(profile_widget_key) not in objective_options:
        st.session_state.pop(profile_widget_key, None)
    focus_widget_key = f"smart_focus_{user_id}"
    if st.session_state.get(focus_widget_key) not in SMART_WORKOUTS:
        st.session_state.pop(focus_widget_key, None)
    suggestion_key = f"smart_workout_v2_{user_id}"
    profile_name = st.selectbox(
        "Objetivo de treino",
        objective_options,
        index=(
            objective_options.index(selected_objective)
            if selected_objective in objective_options
            else 0
        ),
        key=profile_widget_key,
    )
    physical_data = st.columns(2)
    with physical_data[0]:
        weight_kg = st.number_input(
            "Peso (kg)",
            min_value=30.0,
            max_value=300.0,
            value=float(user_profile["peso_kg"]) if user_profile else 85.0,
            step=0.5,
            key=f"smart_weight_{user_id}",
        )
    with physical_data[1]:
        body_fat_percent = st.number_input(
            "Gordura corporal (%)",
            min_value=1.0,
            max_value=70.0,
            value=(
                float(user_profile["gordura_percent"]) if user_profile else 30.0
            ),
            step=0.5,
            key=f"smart_body_fat_{user_id}",
        )
    focus = st.selectbox(
        "Divisão de treino",
        list(SMART_WORKOUTS),
        key=focus_widget_key,
    )
    recovery = st.selectbox(
        "Como está a tua recuperação?",
        ["Normal", "Baixa (menos volume)"],
        help=(
            "Se ainda sentes fadiga do treino anterior, escolhe recuperação baixa "
            "para reduzir séries e aumentar o descanso."
        ),
        key=f"smart_recovery_{user_id}",
    )
    cardio = st.selectbox(
        "Cardio recomendado",
        CARDIO_OPTIONS,
        key=f"smart_cardio_{user_id}",
    )
    cardio_position = ""
    if cardio != "Sem cardio":
        cardio_position = st.radio(
            "Quando fazer o cardio?",
            ["Antes do treino", "Depois do treino"],
            horizontal=True,
            key=f"smart_cardio_position_{user_id}",
        )
    if st.button(
        "🤖 Gerar Treino Inteligente",
        type="primary",
        key=f"generate_smart_workout_{user_id}",
        width="stretch",
    ):
        st.session_state[suggestion_key] = {
            "focus": focus,
            "profile_name": profile_name,
            "weight_kg": weight_kg,
            "body_fat_percent": body_fat_percent,
            "recovery": recovery,
            "cardio": cardio,
            "cardio_position": cardio_position,
            "exercises": generate_smart_workout(
                focus, profile_name, recovery
            ),
        }

    suggestion = st.session_state.get(suggestion_key)
    if not suggestion:
        return
    st.markdown(
        f"#### Sugestão: {suggestion['focus']} · {suggestion['profile_name']}"
    )
    st.caption(
        f"Perfil: {suggestion['weight_kg']:g} kg · "
        f"{suggestion['body_fat_percent']:g}% de gordura corporal. "
        "Mantém a técnica e ajusta ou interrompe qualquer movimento que cause dor."
    )
    if user_profile:
        st.caption(
            "Equipamento selecionado: "
            + ", ".join(user_profile["equipamento"])
            + ". Confirma que cada exercício é compatível com o equipamento disponível."
        )
    exercise_type_labels = {
        "multiarticular": "Multiarticular",
        "isolado": "Isolado",
        "hiit": "HIIT",
        "abdomen": "Abdómen",
    }
    for exercise in suggestion["exercises"]:
        with st.container(border=True):
            st.markdown(f"**{exercise['nome']}**")
            st.caption(exercise_type_labels[exercise["tipo"]])
            st.caption(
                f"{exercise['series']} séries · {exercise['repeticoes']} "
                f"· {exercise['descanso']} de descanso"
            )
            show_exercise_guide(
                exercise["nome"], exercise["grupo_muscular"]
            )
    if suggestion["cardio"]:
        st.info(
            f"Cardio {suggestion['cardio_position'].casefold()}: "
            f"{suggestion['cardio']}"
        )

    workout_name = st.text_input(
        "Nome da ficha",
        value=f"Treino Inteligente - {suggestion['focus']}",
        key=f"smart_workout_name_{user_id}",
    )
    if st.button(
        "Guardar nas minhas fichas",
        key=f"save_smart_workout_{user_id}",
        width="stretch",
    ):
        if not workout_name.strip():
            st.error("Indica um nome para a ficha.")
        else:
            save_smart_workout(
                user_id,
                workout_name,
                suggestion["focus"],
                suggestion["profile_name"],
                suggestion["weight_kg"],
                suggestion["body_fat_percent"],
                suggestion["recovery"],
                suggestion["exercises"],
                "" if suggestion["cardio"] == "Sem cardio" else suggestion["cardio"],
                suggestion["cardio_position"],
            )
            st.session_state[f"smart_saved_{user_id}"] = True
            st.rerun()


def show_attendance_history(user_id: int) -> None:
    st.subheader("Evolução semanal")
    attendance = get_attendance(user_id)
    profile = get_training_profile(user_id)
    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())
    first_week_start = current_week_start - timedelta(weeks=11)
    week_starts = pd.date_range(
        start=first_week_start,
        periods=12,
        freq="W-MON",
    )

    if attendance:
        attendance_frame = pd.DataFrame(
            [{"data": entry["data"]} for entry in attendance]
        )
        attendance_frame["data"] = pd.to_datetime(
            attendance_frame["data"], errors="raise"
        )
        attendance_frame["semana"] = (
            attendance_frame["data"]
            .dt.to_period("W-SUN")
            .dt.start_time
        )
        weekly_counts = (
            attendance_frame.groupby("semana")
            .size()
            .reindex(week_starts, fill_value=0)
        )
    else:
        weekly_counts = pd.Series(0, index=week_starts, dtype="int64")

    chart_data = pd.DataFrame(
        {"Semana": week_starts, "Treinos": weekly_counts.to_numpy()}
    )
    st.bar_chart(chart_data, x="Semana", y="Treinos")
    st.caption("Número de treinos registados por semana (últimas 12 semanas).")

    this_week_count = int(
        weekly_counts.get(pd.Timestamp(current_week_start), 0)
    )
    metric_total, metric_week = st.columns(2)
    metric_total.metric("Treinos registados", len(attendance))
    metric_week.metric("Esta semana", this_week_count)

    if profile:
        st.subheader("Metas semanais de séries por grupo")
        goals = {
            "Empurrar": int(profile["meta_push"]),
            "Puxar": int(profile["meta_pull"]),
            "Pernas": int(profile["meta_pernas"]),
        }
        if attendance:
            current_week = pd.DataFrame(
                [
                    {
                        "Grupo": label,
                        "Séries": int(entry[column]),
                    }
                    for entry in attendance
                    if pd.Timestamp(entry["data"]).date() >= current_week_start
                    and pd.Timestamp(entry["data"]).date() <= today
                    for label, column in (
                        ("Empurrar", "series_push"),
                        ("Puxar", "series_pull"),
                        ("Pernas", "series_legs"),
                    )
                ]
            )
            done = (
                current_week.groupby("Grupo")["Séries"].sum().to_dict()
                if not current_week.empty
                else {}
            )
        else:
            done = {}
        goals_frame = pd.DataFrame(
            {
                "Grupo": list(goals),
                "Séries concluídas": [done.get(group, 0) for group in goals],
                "Meta semanal": list(goals.values()),
            }
        )
        st.bar_chart(
            goals_frame,
            x="Grupo",
            y=["Séries concluídas", "Meta semanal"],
        )
        progress_columns = st.columns(3)
        for column, (group, goal) in zip(progress_columns, goals.items()):
            completed = int(done.get(group, 0))
            column.metric(
                f"{group}: {completed}/{goal}",
                f"{min(100, round(completed / goal * 100))}%",
            )

    st.subheader("Histórico de presenças")
    if not attendance:
        st.info("Ainda não há treinos concluídos registados.")
        return

    history_frame = pd.DataFrame(
        [
            {
                "Data": entry["data"],
                "Treino": entry["treino"],
                "Divisão": entry["divisao"],
                "Duração (min)": entry["duracao_minutos"],
                "Séries": entry["series_total"],
                "Calorias (kcal)": entry["calorias_kcal"],
            }
            for entry in attendance
        ]
    )
    history_frame["Data"] = pd.to_datetime(
        history_frame["Data"], errors="raise"
    ).dt.strftime("%d/%m/%Y")
    st.dataframe(history_frame, width="stretch", hide_index=True)
    summary = st.columns(3)
    summary[0].metric(
        "Séries registadas",
        sum(int(entry["series_total"]) for entry in attendance),
    )
    summary[1].metric(
        "Calorias indicadas",
        sum(int(entry["calorias_kcal"]) for entry in attendance),
    )
    summary[2].metric(
        "Dias frequentados",
        len({entry["data"] for entry in attendance}),
    )


def show_admin_panel(admin_id: int) -> None:
    st.title("🛡️ Painel do Administrador")
    st.caption("Gestão das contas e visão geral dos treinos.")
    users_tab, overview_tab = st.tabs(
        ["👥 Utilizadores", "📊 Visão geral dos treinos"]
    )

    with users_tab:
        users = get_admin_users(admin_id)
        st.subheader("Contas registadas")
        st.dataframe(
            [
                {
                    "Utilizador": user["nome_usuario"],
                    "Tipo de conta": user["tipo"],
                    "Treinos": user["total_treinos"],
                }
                for user in users
            ],
            width="stretch",
            hide_index=True,
        )

        deletable_users = [user for user in users if user["id"] != admin_id]
        if not deletable_users:
            st.info("Não existem outras contas para gerir.")
        else:
            st.markdown("#### Apagar utilizador")
            selected_user = st.selectbox(
                "Seleciona a conta",
                options=[user["id"] for user in deletable_users],
                format_func=lambda user_id: next(
                    user["nome_usuario"]
                    for user in deletable_users
                    if user["id"] == user_id
                ),
                key="admin_selected_user",
            )
            selected_user = next(
                user for user in deletable_users if user["id"] == selected_user
            )
            confirmed = st.checkbox(
                f"Confirmo que quero apagar a conta "
                f"“{selected_user['nome_usuario']}” e os respetivos treinos.",
                key=f"confirm_delete_user_{selected_user['id']}",
            )
            if st.button(
                "🗑️ Apagar utilizador",
                type="primary",
                disabled=not confirmed,
                key=f"admin_delete_user_{selected_user['id']}",
                width="stretch",
            ):
                delete_user_account(admin_id, selected_user["id"])
                st.success("Utilizador e respetivos treinos apagados.")
                st.rerun()

    with overview_tab:
        workouts = get_admin_workouts(admin_id)
        total_users = len(users)
        total_exercises = sum(
            workout["total_exercicios"] for workout in workouts
        )
        metric_users, metric_workouts, metric_exercises = st.columns(3)
        metric_users.metric("Utilizadores", total_users)
        metric_workouts.metric("Treinos", len(workouts))
        metric_exercises.metric("Exercícios", total_exercises)

        if workouts:
            st.dataframe(
                [
                    {
                        "Utilizador": workout["nome_usuario"],
                        "Treino": workout["nome"],
                        "Divisão / foco": workout["divisao"],
                        "Data": workout["data"],
                        "Exercícios": workout["total_exercicios"],
                    }
                    for workout in workouts
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("Ainda não existem treinos registados.")


st.set_page_config(page_title="Meu Treino", page_icon="🏋️‍♂️", layout="centered")
st.markdown(
    """
    <style>
    .block-container {
        max-width: 760px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }
    [data-testid="stSidebar"] { min-width: 250px; }
    .brand-mark { text-align: center; font-size: 3rem; margin-top: 1rem; }
    .auth-title { text-align: center; margin: 0; }
    .auth-subtitle { text-align: center; color: #8b95a1; margin: 0 0 1.5rem; }
    .workout-heading { margin: 1.25rem 0 1rem; }
    .workout-heading h2 { margin: 0; }
    .workout-heading span { color: #8b95a1; font-size: 0.95rem; }
    .empty-state {
        border: 1px dashed rgba(128, 128, 128, 0.45);
        border-radius: 16px;
        padding: 2rem 1rem;
        text-align: center;
        margin: 1.5rem 0;
    }
    .empty-icon { font-size: 2.5rem; margin-bottom: 0.5rem; }
    .empty-state p { color: #8b95a1; margin-bottom: 0; }
    div.stButton > button, div.stFormSubmitButton > button {
        min-height: 2.8rem;
        border-radius: 10px;
    }
    @media (max-width: 640px) {
        .block-container { padding: 1rem 1rem 2rem; }
        [data-testid="stSidebar"] { min-width: 0; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

admin_ready = init_db()
if not admin_ready:
    st.warning(
        "A conta administradora JJadm ainda não foi criada. "
        "Define MEU_TREINO_ADMIN_PASSWORD ou o segredo `admin_password` "
        "no Streamlit para a inicializar."
    )

if "user" in st.session_state:
    session_user = get_session_user(st.session_state.user["id"])
    if session_user is None:
        st.session_state.pop("user", None)
        st.rerun()
    st.session_state.user = {
        "id": session_user["id"],
        "username": session_user["nome_usuario"],
        "tipo": session_user["tipo"],
    }

if "user" not in st.session_state:
    show_authentication_page()
else:
    current_user = st.session_state.user
    st.sidebar.markdown("### 🏋️‍♂️ Meu Treino")
    st.sidebar.write(f"Conta: **{current_user['username']}**")
    if st.sidebar.button("Sair da Conta", width="stretch"):
        st.session_state.pop("user", None)
        st.rerun()

    if (
        current_user["tipo"] == "admin"
        and current_user["username"].casefold() == ADMIN_USERNAME.casefold()
    ):
        show_admin_panel(current_user["id"])
    else:
        show_quick_attendance(current_user["id"])
        st.title("🏋️‍♂️ Meu Treino")
        training_profile = get_training_profile(current_user["id"])
        if training_profile is None:
            st.subheader("Bem-vindo ao Meu Treino")
            show_profile_form(current_user["id"], initial_setup=True)
            st.stop()

        (
            daily_tab,
            ficha_tab,
            body_tab,
            create_tab,
            smart_tab,
            history_tab,
            profile_tab,
        ) = st.tabs(
            [
                "📅 Treino de Hoje",
                "📋 Minhas Fichas",
                "🎯 Por Grupo Muscular",
                "➕ Criar Novo Treino",
                "🤖 Treino Inteligente",
                "📈 Frequência e evolução",
                "⚙️ Perfil e metas",
            ]
        )
        with daily_tab:
            show_daily_workout(current_user["id"])
        with ficha_tab:
            show_workout_cards(current_user["id"])
        with body_tab:
            show_body_focus_generator(current_user["id"])
        with create_tab:
            show_create_workout_form(current_user["id"])
        with smart_tab:
            show_smart_workout_generator(current_user["id"])
        with history_tab:
            show_attendance_history(current_user["id"])
        with profile_tab:
            show_profile_form(current_user["id"])
