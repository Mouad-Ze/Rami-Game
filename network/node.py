# net/node.py

import socket
import threading
import time
import random
import logging
import os
from typing import Dict, List, Tuple

from game.rami import RamiGame
from .protocol import (
    encode_msg, decode_msg,
    card_to_str, str_to_card,
    HELLO, STATE_SNAPSHOT, HEARTBEAT,
    TOKEN_ANNOUNCE, PLAYER_QUIT,
    ACTION_PROPOSE, ACTION_VOTE, ACTION_COMMIT, ACTION_ABORT,
    DEALER_SELECTED, NEW_GAME,
    WIN_DECISION,
)


class RamiNode:
    def __init__(
        self,
        player_id: str,
        host: str,
        port: int,
        peers: List[Tuple[str, int]],
        all_player_ids=("P1", "P2", "P3"),
        seed=42,
    ):
        self.player_id = player_id
        self.host = host
        self.port = port
        self.peers_info = peers

        # Player list (static)
        self.all_player_ids = list(all_player_ids)
        self.n_players = len(self.all_player_ids)

        # Distributed state
        self.dealer = None
        self.turn_order = list(self.all_player_ids)
        self.token_holder = None

        # Local replicated game engine
        self.game = None
        self.seed = seed

        # Networking
        self.server_socket = None
        self.connections = []
        self.connections_lock = threading.Lock()

        # Consensus tracking
        self.current_action_id = 0
        self.pending_votes: Dict[int, Dict[str, bool]] = {}
        self.actions_by_id: Dict[int, dict] = {}
        self.applied_action_ids = set()

        # Heartbeat tracking
        now = time.time()
        self.last_heartbeat = {pid: now for pid in self.all_player_ids}
        self.alive_players = set(self.all_player_ids)
        self.heartbeat_interval = 2
        self.heartbeat_timeout = 6

        self.running = True

        # Setup logging
        self._setup_logging()


    def _setup_logging(self):
        """Setup file-based logging for this node."""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        logger = logging.getLogger(f'Node_{self.player_id}')
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        logger.handlers = []
        
        # File handler
        file_handler = logging.FileHandler(
            f'{log_dir}/node_{self.player_id}.log',
            mode='a'
        )
        file_handler.setLevel(logging.INFO)
        
        # Console handler (also print to stdout)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        self.logger = logger
        self.logger.info(f"Node {self.player_id} logging initialized")


    def start(self):
        threading.Thread(target=self._run_server, daemon=True).start()
        time.sleep(0.5)
        self._connect_to_peers()

        # Announce presence
        self._broadcast({"type": HELLO, "sender": self.player_id, "payload": {}})

        # P1 initiates the FIRST game
        if self.player_id == "P1":
            self._start_new_game()

        threading.Thread(target=self._send_heartbeats_loop, daemon=True).start()
        threading.Thread(target=self._check_liveness_loop, daemon=True).start()

        self.logger.info(f"Node started at {self.host}:{self.port}")
        print(f"[{self.player_id}] Node started at {self.host}:{self.port}")


    def _start_new_game(self):
        self.logger.info("Starting NEW GAME")
        print(f"[{self.player_id}] Starting NEW GAME.")

        dealer = random.choice(self.all_player_ids)
        self.logger.info(f"Randomly selected dealer = {dealer}")
        print(f"[{self.player_id}] Randomly selected dealer = {dealer}")

        self._broadcast({
            "type": DEALER_SELECTED,
            "sender": self.player_id,
            "payload": {"dealer": dealer}
        })

        # Apply locally too
        self._apply_dealer(dealer)

        # Create the game using new turn order
        self._reset_game_state()

    def _apply_dealer(self, dealer):
        """Apply the dealer to THIS node and derive turn order."""
        self.dealer = dealer
        idx = self.all_player_ids.index(dealer)

        # Turn order: dealer → next → next …
        self.turn_order = [
            self.all_player_ids[(idx + i) % self.n_players]
            for i in range(self.n_players)
        ]

        # Dealer holds the initial token
        self.token_holder = self.turn_order[0]

        self.logger.info(f"New dealer = {dealer}, turn order = {self.turn_order}")
        print(f"[{self.player_id}] New dealer = {dealer}")
        print(f"[{self.player_id}] New turn order = {self.turn_order}")

        # Broadcast token holder if needed
        if self.player_id == dealer:
            self._broadcast_token_holder()

    def _reset_game_state(self):
        """Start a fresh RamiGame replica using the new turn order."""
        self.logger.info("Resetting local game state")
        print(f"[{self.player_id}] Resetting local game state.")
        self.game = RamiGame(self.turn_order, seed=self.seed)


    def try_draw(self, source="deck"):
        if not self._i_have_token():
            self.logger.warning("Cannot draw: no token")
            print(f"[{self.player_id}] Cannot draw: no token.")
            return
        aid = self._next_action_id()
        action = {
            "action_id": aid,
            "kind": "DRAW",
            "player": self.player_id,
            "source": source,
        }
        self.logger.info(f"Proposing DRAW action {aid} from {source}")
        self._propose_action(action)

    def try_discard(self, card_str: str):
        if not self._i_have_token():
            self.logger.warning("Cannot discard: no token")
            print(f"[{self.player_id}] Cannot discard: no token.")
            return
        aid = self._next_action_id()
        action = {
            "action_id": aid,
            "kind": "DISCARD",
            "player": self.player_id,
            "card": card_str,
        }
        self.logger.info(f"Proposing DISCARD action {aid}: {card_str}")
        self._propose_action(action)

    def try_declare_win(self, groups: List[List[str]]):
        """
        Declare win with the given groups.
        groups: List of groups, where each group is a list of card strings.
        """
        if not self._i_have_token():
            self.logger.warning("Cannot declare win: no token")
            print(f"[{self.player_id}] Cannot declare win: no token.")
            return
        aid = self._next_action_id()
        action = {
            "action_id": aid,
            "kind": "DECLARE_WIN",
            "player": self.player_id,
            "groups": groups,
        }
        self.logger.info(f"Proposing DECLARE_WIN action {aid} with {len(groups)} groups")
        self._propose_action(action)


    def _run_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.logger.info(f"Listening on {self.host}:{self.port}")
        print(f"[{self.player_id}] Listening on {self.host}:{self.port}")

        while self.running:
            conn, addr = self.server_socket.accept()
            with self.connections_lock:
                self.connections.append(conn)
            threading.Thread(
                target=self._handle_connection,
                args=(conn,),
                daemon=True
            ).start()

    def _connect_to_peers(self):
        for h, p in self.peers_info:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((h, p))
                with self.connections_lock:
                    self.connections.append(sock)
                threading.Thread(
                    target=self._handle_connection,
                    args=(sock,),
                    daemon=True
                ).start()
                self.logger.info(f"Connected to peer {h}:{p}")
                print(f"[{self.player_id}] Connected to peer {h}:{p}")
            except Exception as e:
                self.logger.error(f"Failed to connect to {h}:{p}: {e}")
                print(f"[{self.player_id}] Failed to connect {h}:{p}")

    def _handle_connection(self, conn):
        buffer = b""
        while self.running:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    msg = decode_msg(raw)
                    self._handle_message(msg)
            except:
                break

        with self.connections_lock:
            if conn in self.connections:
                self.connections.remove(conn)
        conn.close()

    def _handle_message(self, msg):
        mtype = msg["type"]
        sender = msg["sender"]
        payload = msg["payload"]

        if mtype == HEARTBEAT:
            self.last_heartbeat[sender] = time.time()
            return

        if mtype == DEALER_SELECTED:
            dealer = payload["dealer"]
            self._apply_dealer(dealer)
            self._reset_game_state()
            return

        if mtype == TOKEN_ANNOUNCE:
            self.token_holder = payload["token_holder"]
            self.logger.info(f"Token holder changed to: {self.token_holder}")
            print(f"[{self.player_id}] Token holder now: {self.token_holder}")
            return

        if mtype == ACTION_PROPOSE:
            self._on_action_propose(payload)
            return

        if mtype == ACTION_VOTE:
            self._on_action_vote(sender, payload)
            return

        if mtype == ACTION_COMMIT:
            self._on_action_commit(payload)
            return

        if mtype == ACTION_ABORT:
            self.logger.warning("Action aborted")
            print(f"[{self.player_id}] Action aborted")
            self._rotate_token()
            return

        if mtype == PLAYER_QUIT:
            quitter = payload["player"]
            self.logger.info(f"Player {quitter} announced quit.")
            print(f"[{self.player_id}] Player {quitter} quit the game.")
            self._mark_player_dead(quitter, reason="player quit")
            return

        if mtype == WIN_DECISION:
            winner = payload["winner"]
            self.logger.info(f"GAME OVER - Winner: {winner}")
            print(f"[{self.player_id}] Game Over. Winner = {winner}")

            # Start a NEW GAME after win
            if self.player_id == self.token_holder:
                self._start_new_game()

            return


    def _send_heartbeats_loop(self):
        while self.running:
            self._broadcast({
                "type": HEARTBEAT,
                "sender": self.player_id,
                "payload": {}
            })
            time.sleep(self.heartbeat_interval)

    def _check_liveness_loop(self):
        while self.running:
            now = time.time()
            for pid in self.all_player_ids:
                if pid == self.player_id:
                    continue
                if now - self.last_heartbeat[pid] > self.heartbeat_timeout:
                    self._mark_player_dead(pid, reason="heartbeat timeout")
            time.sleep(self.heartbeat_interval)


    def _i_have_token(self):
        return self.token_holder == self.player_id

    def _rotate_token(self):
        if not self.turn_order:
            return

        current = self.token_holder
        if current in self.turn_order:
            idx = self.turn_order.index(current)
        else:
            idx = -1

        new_holder = None
        for _ in range(self.n_players):
            idx = (idx + 1) % self.n_players
            candidate = self.turn_order[idx]
            if candidate in self.alive_players:
                new_holder = candidate
                break

        self.token_holder = new_holder
        self._broadcast_token_holder()

    def _broadcast_token_holder(self):
        self._broadcast({
            "type": TOKEN_ANNOUNCE,
            "sender": self.player_id,
            "payload": {"token_holder": self.token_holder}
        })
        self.logger.info(f"Token rotated to: {self.token_holder}")
        print(f"[{self.player_id}] Broadcast token holder = {self.token_holder}")

    def _mark_player_dead(self, pid, reason=""):
        if pid not in self.alive_players:
            return
        self.alive_players.remove(pid)
        self.logger.warning(f"Node {pid} removed from alive set ({reason}).")
        print(f"[{self.player_id}] Node {pid} removed ({reason}).")
        self.last_heartbeat[pid] = 0
        if self.token_holder == pid:
            self._rotate_token()


    def _next_action_id(self):
        self.current_action_id += 1
        return self.current_action_id

    def _propose_action(self, action):
        aid = action["action_id"]
        self.actions_by_id[aid] = action
        self.pending_votes[aid] = {self.player_id: True}

        self._broadcast({
            "type": ACTION_PROPOSE,
            "sender": self.player_id,
            "payload": action
        })

    def _on_action_propose(self, action):
        aid = action["action_id"]
        self.actions_by_id[aid] = action
        vote = self._validate_action(action)

        if aid not in self.pending_votes:
            self.pending_votes[aid] = {}
        self.pending_votes[aid][self.player_id] = vote

        self._broadcast({
            "type": ACTION_VOTE,
            "sender": self.player_id,
            "payload": {"action_id": aid, "vote": vote}
        })

    def _on_action_vote(self, sender, payload):
        aid = payload["action_id"]
        vote = payload["vote"]

        if aid not in self.pending_votes:
            self.pending_votes[aid] = {}
        self.pending_votes[aid][sender] = vote

        if not self._i_have_token():
            return

        # All votes received
        if set(self.pending_votes[aid].keys()) != self.alive_players:
            return

        yes = sum(1 for v in self.pending_votes[aid].values() if v)
        action = self.actions_by_id[aid]
        if yes >= 2:
            self.logger.info(f"COMMITTED action {aid}: {action['kind']} by {action['player']}")
            print(f"[{self.player_id}] COMMITTED action {aid}")
            self._broadcast({
                "type": ACTION_COMMIT,
                "sender": self.player_id,
                "payload": {"action": action}
            })
            self._apply_action(action)
            # Only rotate token after DISCARD actions
            # DRAW actions keep the token so player can discard
            # DECLARE_WIN ends the game, so no token rotation needed
            if self.game and self.game.phase != "GAME_OVER":
                if action['kind'] == 'DISCARD':
                    # After discard, rotate token to next player
                    self._rotate_token()
                # For DRAW actions, don't rotate - player keeps token to discard
        else:
            self.logger.warning(f"ABORTED action {aid}: insufficient votes ({yes}/{len(self.alive_players)})")
            print(f"[{self.player_id}] ABORTED action {aid}")
            self._broadcast({
                "type": ACTION_ABORT,
                "sender": self.player_id,
                "payload": {"action_id": aid}
            })
            self._rotate_token()

    def _on_action_commit(self, payload):
        action = payload["action"]
        self._apply_action(action)


    def _validate_action(self, action):
        if self.game is None:
            return False

        g = self.game
        kind = action["kind"]
        player = action["player"]

        if g.current_player_id != player:
            return False

        if kind == "DRAW":
            if g.phase != "AWAIT_DRAW":
                return False
            src = action["source"]
            state = g.game_state_summary()
            if src == "deck" and state["deck_size"] == 0:
                return False
            if src == "discard" and state["discard_top"] is None:
                return False
            return True

        if kind == "DISCARD":
            if g.phase not in ("AWAIT_DISCARD_OR_WIN", "WIN_DECLARED"):
                return False
            card = str_to_card(action["card"])
            return card in g.players[player].hand

        if kind == "DECLARE_WIN":
            if g.phase != "AWAIT_DISCARD_OR_WIN":
                return False
            # Parse groups from action
            groups_str = action.get("groups", [])
            try:
                groups = [[str_to_card(cs) for cs in group] for group in groups_str]
                ok, _ = g.can_declare_win(player, groups)
                return ok
            except Exception as e:
                self.logger.error(f"Win validation error: {e}")
                print(f"[{self.player_id}] Win validation error: {e}")
                return False

        return False

    def _apply_action(self, action):
        if self.game is None:
            return

        g = self.game
        kind = action["kind"]
        action_id = action.get("action_id")

        if action_id is not None:
            if action_id in self.applied_action_ids:
                return
            self.applied_action_ids.add(action_id)

        player = action["player"]

        if kind == "DRAW":
            src = action["source"]
            try:
                card = g.draw_card(player, src)
                self.logger.info(f"Applied DRAW: {player} drew from {src} -> {card}")
            except Exception as e:
                self.logger.error(f"DRAW apply error: {e}")
                print(f"[{self.player_id}] DRAW apply error:", e)

        elif kind == "DISCARD":
            card = str_to_card(action["card"])
            try:
                g.discard_card(player, card)
                self.logger.info(f"Applied DISCARD: {player} discarded {card}")
            except Exception as e:
                self.logger.error(f"DISCARD apply error: {e}")
                print(f"[{self.player_id}] DISCARD apply error:", e)

        elif kind == "DECLARE_WIN":
            groups_str = action.get("groups", [])
            try:
                groups = [[str_to_card(cs) for cs in group] for group in groups_str]
                success, msg, card_to_discard = g.declare_win(player, groups)
                if success:
                    self.logger.info(f"WIN DECLARED by {player}: {msg}")
                    print(f"[{self.player_id}] {player} declared WIN! {msg}")
                    # Automatically discard the final card
                    if card_to_discard:
                        g.discard_card(player, card_to_discard)
                        self.logger.info(f"{player} discarded final card: {card_to_discard}")
                        print(f"[{self.player_id}] {player} discarded final card: {card_to_discard}")
                    # Broadcast win decision
                    if self._i_have_token():
                        self._broadcast({
                            "type": WIN_DECISION,
                            "sender": self.player_id,
                            "payload": {"winner": player}
                        })
                else:
                    self.logger.warning(f"Win declaration failed: {msg}")
                    print(f"[{self.player_id}] Win declaration failed: {msg}")
            except Exception as e:
                self.logger.error(f"DECLARE_WIN apply error: {e}")
                print(f"[{self.player_id}] DECLARE_WIN apply error: {e}")


    def _broadcast(self, msg):
        enc = encode_msg(msg)
        with self.connections_lock:
            for c in list(self.connections):
                try:
                    c.sendall(enc)
                except:
                    self.connections.remove(c)

    def announce_quit(self):
        self.logger.info("Announcing quit.")
        print(f"[{self.player_id}] Announcing quit.")
        self._broadcast({
            "type": PLAYER_QUIT,
            "sender": self.player_id,
            "payload": {"player": self.player_id}
        })
        self._mark_player_dead(self.player_id, reason="self quit")
        self.shutdown()

    def shutdown(self):
        if not self.running:
            return
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        with self.connections_lock:
            for c in list(self.connections):
                try:
                    c.close()
                except:
                    pass
            self.connections.clear()
