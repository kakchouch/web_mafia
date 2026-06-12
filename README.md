# 🐺 Loup-Garou — Web App en Python

Un jeu de Loup-Garou (Mafia) en français, entièrement jouable dans le navigateur. L'IA (Perplexity) joue tous les personnages non-joueurs, narre la partie en temps réel, et chaque personnage parle à voix haute avec une voix distincte grâce à l'API Web Speech intégrée au navigateur.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Lancement](#lancement)
- [Les rôles](#les-rôles)
- [Déroulement d'une partie](#déroulement-dune-partie)
- [Modes de jeu](#modes-de-jeu)
- [Architecture technique](#architecture-technique)
- [Structure des fichiers](#structure-des-fichiers)
- [Configuration avancée](#configuration-avancée)

---

## Fonctionnalités

- **Jeu complet en français** — narration dramatique, dialogues des PNJ, votes, et fin de partie
- **IA narrative** — Perplexity génère la narration atmosphérique et les répliques de chaque personnage
- **TTS multi-voix** — chaque personnage a une voix distincte (Web Speech API, gratuit, aucune installation)
- **Deux modes** :
  - **Joueur** : vous incarnez un rôle avec information limitée (secret de votre rôle respecté)
  - **Spectateur** : vous observez toute la partie, tous les secrets visibles
- **6 rôles jouables** : Villageois, Loup-Garou, Voyante, Sorcière, Chasseur, Cupidon
- **Compositions équilibrées** pour 4 à 8 joueurs
- **Mémoire des PNJ** : les personnages IA accumulent des suspicions au fil des tours
- **Interface réactive** via Server-Sent Events (SSE) — pas de rechargement de page
- **100% gratuit** — TTS natif, modèles Perplexity à faible coût

---

## Prérequis

- **Python 3.10+**
- **Une clé API Perplexity** — obtenir sur [perplexity.ai](https://www.perplexity.ai/settings/api)
- Un navigateur moderne (Chrome, Edge, Firefox, Safari) pour le TTS

---

## Installation

```bash
# Cloner ou télécharger le projet
cd mafia

# Installer les dépendances Python
pip install -r requirements.txt
```

Puis ouvrir le fichier `api.secret` et y coller votre clé Perplexity :

```
PERPLEXITY_API_KEY=pplx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## Lancement

```bash
python app.py
```

Ouvrir ensuite **[http://localhost:5000](http://localhost:5000)** dans le navigateur.

> La première fois que le navigateur parle, il peut demander l'autorisation d'utiliser la synthèse vocale. Acceptez pour profiter du TTS.

---

## Les rôles

### 🐺 Loup-Garou — Équipe des Loups
Chaque nuit, les loups se réveillent et votent secrètement pour dévorer un villageois. Leur objectif : être en nombre égal ou supérieur aux villageois.

### 👨‍🌾 Villageois — Équipe du Village
Aucun pouvoir spécial. Participe aux discussions et aux votes du jour. Doit identifier et éliminer les loups.

### 🔮 Voyante — Équipe du Village
Chaque nuit, peut découvrir la véritable identité d'un joueur. Information précieuse, mais attention à ne pas se dévoiler trop tôt.

### 🧙 Sorcière — Équipe du Village
Possède deux potions, chacune utilisable **une seule fois** dans la partie :
- **Potion de vie** : sauve la victime des loups cette nuit
- **Potion de mort** : élimine n'importe quel joueur la nuit

### 🏹 Chasseur — Équipe du Village
Lorsqu'il est éliminé (de nuit par les loups ou de jour par un vote), peut immédiatement abattre un autre joueur de son choix.

### 💘 Cupidon — Équipe du Village
Agit **uniquement la première nuit** : désigne deux joueurs comme amoureux. Si l'un des deux meurt, l'autre mourra de chagrin immédiatement. Si les deux amoureux sont les derniers survivants, ils gagnent ensemble, même si l'un est un loup.

---

## Composition des équipes

| Joueurs | 🐺 Loups | 🔮 Voyante | 🧙 Sorcière | 🏹 Chasseur | 💘 Cupidon | 👨‍🌾 Villageois |
|:-------:|:--------:|:----------:|:-----------:|:-----------:|:----------:|:--------------:|
| 4       | 1        | 1          | —           | —           | —          | 2              |
| 5       | 1        | 1          | 1           | —           | —          | 2              |
| 6       | 2        | 1          | 1           | 1           | —          | 1              |
| 7       | 2        | 1          | 1           | 1           | —          | 2              |
| 8       | 2        | 1          | 1           | 1           | 1          | 2              |

---

## Déroulement d'une partie

### Écran de setup
1. Choisir votre prénom (mode Joueur) ou activer le mode Spectateur
2. Sélectionner votre rôle préféré ou laisser sur "Aléatoire"
3. Régler le nombre de joueurs (4 à 8) avec le curseur
4. Cliquer sur **Commencer la partie**

---

### 🌙 Phase de Nuit

Les joueurs ferment les yeux. Chaque rôle se réveille dans un ordre fixe :

1. **Cupidon** *(première nuit uniquement)* — désigne deux amoureux
2. **Loups-Garous** — délibèrent et choisissent une victime
3. **Voyante** — inspecte un joueur
4. **Sorcière** — décide d'utiliser ou non ses potions

Si c'est **votre** tour d'agir, un panneau d'action apparaît en bas de l'écran avec des boutons à cliquer. Sinon, l'IA résout automatiquement cette étape et vous voyez le résultat dans le journal (si votre rôle vous y donne accès).

---

### ☀️ Phase de Jour — Discussion

Le matin, le village découvre les morts de la nuit. Les PNJ s'expriment tour à tour, s'accusent, se défendent, réagissent aux événements. Leurs suspicions évoluent selon l'historique de la partie.

**Votre tour de parole** : un champ de texte apparaît. Vous pouvez écrire ce que vous pensez (accusation, défense, bluff…) ou passer votre tour. Les PNJ réagissent à ce que vous dites.

---

### 🗳 Phase de Vote

Chaque joueur vivant vote pour éliminer un suspect. Pour vous, un panneau de boutons apparaît avec tous les joueurs vivants (sauf vous-même). Les PNJ votent selon leurs suspicions accumulées. Le joueur ayant le plus de voix est éliminé — en cas d'égalité, le tirage est aléatoire.

Quand un joueur est éliminé, son rôle est révélé à tous.

---

### Conditions de victoire

| Gagnant       | Condition |
|---------------|-----------|
| 🌅 Village    | Tous les loups sont éliminés |
| 🐺 Loups      | Les loups sont en nombre égal ou supérieur aux villageois |
| 💕 Amoureux   | Les deux seuls survivants sont les amoureux |

---

## Modes de jeu

### 🎭 Mode Joueur
Vous participez activement. Votre information est **strictement limitée à votre rôle** :
- Un **Villageois** ne voit pas les actions nocturnes (loups, voyante, sorcière)
- Un **Loup-Garou** voit les délibérations des autres loups la nuit
- La **Voyante** voit les révélations qu'elle demande
- La **Sorcière** voit qui a été tué et choisit ses potions

### 👁 Mode Spectateur
Vous observez sans jouer. **Tout est visible** : les délibérations des loups, les révélations de la voyante, les décisions de la sorcière. Idéal pour apprendre les mécaniques du jeu, ou regarder une partie se dérouler entièrement par l'IA.

---

## Architecture technique

```
Navigateur (JS)  ←──SSE──  Flask (Python)  ──→  Perplexity API
      │                         │
   Web Speech API            threading
   (TTS natif)              (jeu en arrière-plan)
```

### Composants clés

**Backend — Flask**
- Pas de base de données : l'état du jeu vit entièrement en mémoire Python (`GameState`)
- Un thread d'arrière-plan orchestre la partie ; les actions du joueur le débloquent via `threading.Event`
- Le SSE (`/api/events`) streame les événements en temps réel au navigateur

**IA — Perplexity API**
- `sonar-pro` : narration dramatique (peu d'appels, haute qualité)
- `sonar` : dialogues des PNJ et votes (nombreux appels, faible coût)
- Les PNJ ont une **mémoire de suspicion** qui persiste d'un tour à l'autre

**TTS — Web Speech API**
- Intégrée au navigateur, gratuite, aucune clé nécessaire
- Chaque personnage se voit attribuer une voix et des paramètres uniques (pitch, débit)
- File d'attente FIFO pour enchaîner les répliques sans chevauchement
- La narration est prioritaire et interrompt les répliques en cours

---

## Structure des fichiers

```
mafia/
│
├── app.py                   Point d'entrée Flask, routes API, générateur SSE
│
├── game/
│   ├── __init__.py
│   ├── state.py             GameState · Player · NPCMemory
│   ├── roles.py             Définitions des rôles, composition par nb de joueurs
│   ├── ai_director.py       Client Perplexity : narration, dialogues, votes IA
│   └── phases.py            Machine d'état : run_night() et run_jour()
│
├── static/
│   ├── css/style.css        Thème village sombre (parchemin, or, rouge sang)
│   └── js/
│       ├── tts.js           Web Speech API — voix distinctes, file d'attente
│       └── game.js          Consommateur SSE, panneaux d'action, sidebar joueurs
│
├── templates/
│   └── index.html           SPA : setup / jeu / fin de partie / modale règles
│
├── api.secret               Votre clé Perplexity (non commité)
├── .env.example             Exemple de configuration
├── .gitignore
└── requirements.txt
```

---

## Configuration avancée

### Changer le fichier de clé
La clé est lue depuis `api.secret` à la racine du projet. Format :
```
PERPLEXITY_API_KEY=pplx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Changer le port
```bash
# Linux/Mac
PORT=8080 python app.py

# Windows PowerShell
$env:PORT=8080; python app.py
```

Ou modifier directement la dernière ligne de `app.py` :
```python
app.run(debug=True, threaded=True, port=8080)
```

### Désactiver le mode debug (production)
Dans `app.py`, remplacer :
```python
app.run(debug=True, threaded=True, port=5000)
```
par :
```python
app.run(debug=False, threaded=True, port=5000)
```

### Ajouter des noms de personnages
Dans [game/roles.py](game/roles.py), modifier la liste `FRENCH_NAMES` pour personnaliser les prénoms des PNJ.

---

## Dépendances

| Package | Usage |
|---------|-------|
| `flask` | Serveur web, routes, SSE |
| `openai` | Client compatible Perplexity API |
| `python-dotenv` | Chargement des fichiers de configuration |

Toutes les autres fonctionnalités (TTS, interface) utilisent des APIs natives du navigateur, sans dépendance supplémentaire.
