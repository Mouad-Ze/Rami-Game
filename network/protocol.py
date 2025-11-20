# net/protocol.py

import json
from game.rami import Card

# Message types
HELLO          = "HELLO"
STATE_SNAPSHOT = "STATE_SNAPSHOT"
HEARTBEAT      = "HEARTBEAT"

TOKEN_ANNOUNCE = "TOKEN_ANNOUNCE"
PLAYER_QUIT    = "PLAYER_QUIT"

ACTION_PROPOSE = "ACTION_PROPOSE"
ACTION_VOTE    = "ACTION_VOTE"
ACTION_COMMIT  = "ACTION_COMMIT"
ACTION_ABORT   = "ACTION_ABORT"

DEALER_SELECTED = "DEALER_SELECTED"
NEW_GAME        = "NEW_GAME"

WIN_DECISION   = "WIN_DECISION"


def encode_msg(msg: dict) -> bytes:
    return (json.dumps(msg) + "\n").encode("utf-8")


def decode_msg(raw: bytes) -> dict:
    return json.loads(raw.decode("utf-8"))


def card_to_str(card: Card) -> str:
    if card.is_joker:
        return "JOKER"
    rank_map = {1: "A", 11: "J", 12: "Q", 13: "K"}
    r = rank_map.get(card.rank, str(card.rank))
    return f"{r}{card.suit}"


def str_to_card(s: str) -> Card:
    if s == "JOKER":
        return Card(None, None)
    rank_str = s[:-1]
    suit = s[-1]
    back_map = {"A": 1, "J": 11, "Q": 12, "K": 13}
    rank = back_map.get(rank_str, int(rank_str))
    return Card(rank, suit)
