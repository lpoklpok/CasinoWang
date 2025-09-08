from flask import Flask, request, jsonify, send_from_directory
import random, secrets

app = Flask(__name__, static_folder="static", static_url_path="")
GAMES = {}  # Store active games

RANKS = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
SUITS = ["S","H","D","C"]

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
    ranks = [c[:-1] for c in cards]
    total = sum(card_value(r) for r in ranks)
    aces = ranks.count("A")
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

def summarize(game):
    return {
        "gameId": game["id"],
        "hands": game["hands"],
        "activeHand": game["activeHand"],
        "dealer": game["dealer"] if game["status"] != "player_turn" else [game["dealer"][0], "??"],
        "status": game["status"],
        "bets": game["bets"],
        "totals": {
            "dealer": hand_total(game["dealer"]) if game["status"] != "player_turn" else None,
            "hands": [hand_total(h) for h in game["hands"]]
        }
    }

def stand_logic(game):
    # Dealer plays out
    while hand_total(game["dealer"]) < 17:
        game["dealer"].append(game["deck"].pop())

    dealer_total = hand_total(game["dealer"])
    results = []

    for idx, hand in enumerate(game["hands"]):
        player_total = hand_total(hand)
        if game.get("surrendered", {}).get(idx):
            results.append("surrender")
        elif player_total > 21:
            results.append("player_bust")
        elif dealer_total > 21 or player_total > dealer_total:
            results.append("player_win")
        elif dealer_total > player_total:
            results.append("dealer_win")
        else:
            results.append("push")

    game["results"] = results
    game["status"] = "finished"
    return jsonify(summarize(game))

@app.route("/")
def root():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/new-game", methods=["POST"])
def new_game():
    game_id = secrets.token_urlsafe(8)
    deck = new_deck()
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]

    hands = [player]
    bets = [100]  # frontend handles actual bet amounts

    game = {
        "id": game_id,
        "deck": deck,
        "hands": hands,
        "activeHand": 0,
        "dealer": dealer,
        "bets": bets,
        "status": "player_turn",
        "surrendered": {}
    }

    # Check for natural blackjack
    if hand_total(player) == 21:
        game["status"] = "player_blackjack"

    GAMES[game_id] = game
    return jsonify(summarize(game))

@app.route("/api/hit", methods=["POST"])
def hit():
    data = request.get_json(force=True)
    game = GAMES.get(data.get("gameId"))
    if not game or game["status"] != "player_turn":
        return jsonify({"error": "Invalid game"}), 400

    hand = game["hands"][game["activeHand"]]
    hand.append(game["deck"].pop())

    if hand_total(hand) > 21:
        # Bust → move to next hand or dealer
        if game["activeHand"] + 1 < len(game["hands"]):
            game["activeHand"] += 1
        else:
            return stand_logic(game)

    return jsonify(summarize(game))

@app.route("/api/stand", methods=["POST"])
def stand():
    data = request.get_json(force=True)
    game = GAMES.get(data.get("gameId"))
    if not game or game["status"] != "player_turn":
        return jsonify({"error": "Invalid game"}), 400

    if game["activeHand"] + 1 < len(game["hands"]):
        game["activeHand"] += 1
        return jsonify(summarize(game))
    else:
        return stand_logic(game)

@app.route("/api/double", methods=["POST"])
def double_down():
    data = request.get_json(force=True)
    game = GAMES.get(data.get("gameId"))
    if not game or game["status"] != "player_turn":
        return jsonify({"error": "Invalid game"}), 400

    idx = game["activeHand"]
    hand = game["hands"][idx]

    if len(hand) != 2 or game["bets"][idx] > 500:  # crude rule
        return jsonify({"error": "Can only double on first move"}), 400

    game["bets"][idx] *= 2
    hand.append(game["deck"].pop())

    if game["activeHand"] + 1 < len(game["hands"]):
        game["activeHand"] += 1
        return jsonify(summarize(game))
    else:
        return stand_logic(game)

@app.route("/api/surrender", methods=["POST"])
def surrender():
    data = request.get_json(force=True)
    game = GAMES.get(data.get("gameId"))
    if not game or game["status"] != "player_turn":
        return jsonify({"error": "Invalid game"}), 400

    idx = game["activeHand"]
    game["surrendered"][idx] = True

    if game["activeHand"] + 1 < len(game["hands"]):
        game["activeHand"] += 1
        return jsonify(summarize(game))
    else:
        return stand_logic(game)

@app.route("/api/split", methods=["POST"])
def split():
    data = request.get_json(force=True)
    game = GAMES.get(data.get("gameId"))
    if not game or game["status"] != "player_turn":
        return jsonify({"error": "Invalid game"}), 400

    idx = game["activeHand"]
    hand = game["hands"][idx]
    if len(hand) == 2 and hand[0][:-1] == hand[1][:-1]:
        card1, card2 = hand
        new_hand1 = [card1, game["deck"].pop()]
        new_hand2 = [card2, game["deck"].pop()]
        game["hands"][idx] = new_hand1
        game["hands"].insert(idx+1, new_hand2)
        game["bets"].insert(idx+1, game["bets"][idx])
    return jsonify(summarize(game))

if __name__ == "__main__":
    app.run(debug=True)
