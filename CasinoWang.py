from flask import Flask, request, jsonify, send_from_directory
import random, secrets

app = Flask(__name__, static_folder="static", static_url_path="")
GAMES = {}  # in-memory storage: {game_id: {...}}

RANKS = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
SUITS = ["S","H","D","C"]  # spades, hearts, diamonds, clubs

def new_deck():
    deck = [f"{r}{s}" for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck

def card_value(rank):
    if rank in ["J","Q","K"]:
        return 10
    if rank == "A":
        return 11
    return int(rank)

def hand_total(cards):
    # cards like ["AS","10H"]
    ranks = [c[:-1] for c in cards]  # strip suit
    total = sum(card_value(r) for r in ranks)
    # Adjust Aces from 11 to 1 if bust
    aces = ranks.count("A")
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

def deal_card(game):
    game["player_turn"]  # just ensures key exists
    if not game["deck"]:
        game["deck"] = new_deck()
    return game["deck"].pop()

def summarize(game):
    return {
        "gameId": game["id"],
        "status": game["status"],
        "player": game["player"],
        "dealer": game["dealer"] if game["status"] != "player_turn" else [game["dealer"][0], "??"],
        "playerTotal": hand_total(game["player"]),
        "dealerTotal": hand_total(game["dealer"]) if game["status"] != "player_turn" else None
    }

@app.route("/")
def root():
    # Serve the UI
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/new-game", methods=["POST"])
def new_game():
    game_id = secrets.token_urlsafe(8)
    deck = new_deck()
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    status = "player_turn"

    # Natural blackjack checks
    p = hand_total(player)
    d = hand_total(dealer)
    if p == 21 and d == 21:
        status = "push"
    elif p == 21:
        status = "player_blackjack"
    elif d == 21:
        status = "dealer_blackjack"

    game = {
        "id": game_id,
        "deck": deck,
        "player": player,
        "dealer": dealer,
        "status": status,            # player_turn | player_bust | dealer_win | player_win | push | ...
        "player_turn": (status == "player_turn")
    }
    GAMES[game_id] = game
    return jsonify(summarize(game))

@app.route("/api/hit", methods=["POST"])
def hit():
    data = request.get_json(force=True)
    game = GAMES.get(data.get("gameId"))
    if not game or game["status"] != "player_turn":
        return jsonify({"error": "Invalid game or not player's turn"}), 400

    game["player"].append(deal_card(game))
    if hand_total(game["player"]) > 21:
        game["status"] = "player_bust"
    return jsonify(summarize(game))

@app.route("/api/stand", methods=["POST"])
def stand():
    data = request.get_json(force=True)
    game = GAMES.get(data.get("gameId"))
    if not game or game["status"] != "player_turn":
        return jsonify({"error": "Invalid game or not player's turn"}), 400

    # Dealer reveals and draws to 17+
    while hand_total(game["dealer"]) < 17:
        game["dealer"].append(deal_card(game))

    p = hand_total(game["player"])
    d = hand_total(game["dealer"])

    if d > 21:
        game["status"] = "player_win"
    elif p > d:
        game["status"] = "player_win"
    elif d > p:
        game["status"] = "dealer_win"
    else:
        game["status"] = "push"

    return jsonify(summarize(game))

if __name__ == "__main__":
    # Local dev
    app.run(debug=True)