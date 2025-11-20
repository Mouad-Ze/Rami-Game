# run_node.py

import sys
import json
from network.node import RamiNode
from network.protocol import str_to_card


def _print_piles(node):
    if node.game is None:
        print("Game not started yet. Waiting for game initialization...")
        return None
    state = node.game.game_state_summary()
    deck_top = state.get("deck_top")
    discard_top = state.get("discard_top")
    deck_size = state.get("deck_size", 0)

    print("\n-- Piles --")
    print(f"Draw pile top: {deck_top or 'Empty'} ({deck_size} cards remaining)")
    print(f"Discard pile top: {discard_top or 'Empty'}")
    return state


def _prompt_draw_source(node):
    """
    Display the top cards of the draw and discard piles and prompt
    the player to choose a source to draw from.
    """
    if node.game is None:
        print("Game not started yet. Waiting for game initialization...")
        return None

    state = _print_piles(node)
    if state is None:
        return None
    deck_top = state.get("deck_top")
    discard_top = state.get("discard_top")
    deck_size = state.get("deck_size", 0)

    while True:
        choice = input("Draw from deck or discard? [deck/discard/cancel]: ").strip().lower()
        if choice in ("cancel", "c", ""):
            print("Canceled draw request.")
            return None
        if choice not in ("deck", "discard"):
            print("Please enter 'deck', 'discard', or 'cancel'.")
            continue
        if choice == "deck" and deck_size == 0:
            print("Draw pile is empty. Choose discard.")
            continue
        if choice == "discard" and discard_top is None:
            print("Discard pile is empty. Choose deck.")
            continue
        return choice


def main():
    if len(sys.argv) < 3:
        print("Usage: python run_node.py <player_id> <port> [host_ip]")
        print("Example (local): python run_node.py P1 8001")
        print("Example (distributed): python run_node.py P1 8001 192.168.1.10")
        print("\nFor distributed setup, also update all_nodes dictionary with actual IPs")
        sys.exit(1)

    player_id = sys.argv[1]   # P1, P2, P3
    port = int(sys.argv[2])
    
    # Host IP: use provided IP, or default to localhost for local testing
    # For distributed setup, use "0.0.0.0" to listen on all interfaces
    if len(sys.argv) >= 4:
        host = sys.argv[3]
    else:
        host = "127.0.0.1"  # Localhost for local testing
    
    # For distributed deployment, bind to all interfaces
    bind_host = "0.0.0.0" if host != "127.0.0.1" else "127.0.0.1"

    # For distributed deployment, update these IPs with actual machine IPs
    # For local testing, keep as 127.0.0.1
    all_nodes = {
        "P1": ("127.0.0.1", 8001),  # Update to actual IP for distributed setup
        "P2": ("127.0.0.1", 8002),  # Update to actual IP for distributed setup
        "P3": ("127.0.0.1", 8003),  # Update to actual IP for distributed setup
    }
    
    # If host is not localhost, update the current node's entry
    if host != "127.0.0.1" and player_id in all_nodes:
        all_nodes[player_id] = (host, port)

    if player_id not in all_nodes:
        print("player_id must be one of: P1, P2, P3")
        sys.exit(1)

    peers = [addr for pid, addr in all_nodes.items() if pid != player_id]

    node = RamiNode(
        player_id=player_id,
        host=bind_host,  # Bind to all interfaces for distributed, localhost for local
        port=port,
        peers=peers,
        all_player_ids=("P1", "P2", "P3"),
        seed=42,
    )
    node.start()

    print(f"[{player_id}] Commands:")
    print("  draw               -> inspect piles, then choose draw source or cancel")
    print("  piles              -> show the current top cards without drawing")
    print("  discard <CARD>     -> discard card (e.g., 7H, AD, JOKER)")
    print("  win <GROUPS>       -> declare win (e.g., win 7H,7D,7S | AH,2H,3H | 10C,10D)")
    print("  hand               -> print your hand")
    print("  state              -> show game state summary")
    print("  token              -> show current token holder")
    print("  quit               -> exit")

    try:
        while True:
            cmd = input(f"[{player_id}] > ").strip()
            if not cmd:
                continue
            if cmd == "quit":
                node.announce_quit()
                break
            elif cmd == "draw":
                source = _prompt_draw_source(node)
                if source is None:
                    continue
                node.try_draw(source)
            elif cmd == "piles":
                _print_piles(node)
            elif cmd.startswith("discard"):
                parts = cmd.split()
                if len(parts) != 2:
                    print("Usage: discard <CARD>")
                    continue
                card_str = parts[1]
                node.try_discard(card_str)
            elif cmd.startswith("win"):
                # Parse: win <group1> | <group2> | <group3> ...
                # Example: win 7H,7D,7S | AH,2H,3H | 10C,10D,JOKER
                parts = cmd.split(" ", 1)
                if len(parts) != 2:
                    print("Usage: win <GROUPS>")
                    print("Example: win 7H,7D,7S | AH,2H,3H | 10C,10D")
                    continue
                groups_str = parts[1]
                try:
                    # Split by | to get groups, then split each group by comma
                    groups = []
                    for group_str in groups_str.split("|"):
                        group = [card.strip() for card in group_str.split(",") if card.strip()]
                        if group:
                            groups.append(group)
                    if not groups:
                        print("Error: No groups provided.")
                        continue
                    node.try_declare_win(groups)
                except Exception as e:
                    print(f"Error parsing win command: {e}")
            elif cmd == "hand":
                if node.game is None:
                    print("Game not started yet. Waiting for game initialization...")
                else:
                    print(node.game.hand_as_strings(player_id))
            elif cmd == "state":
                if node.game is None:
                    print("Game not started yet. Waiting for game initialization...")
                else:
                    state = node.game.game_state_summary()
                    print(json.dumps(state, indent=2))
            elif cmd == "token":
                print("Token holder:", node.token_holder)
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        node.announce_quit()


if __name__ == "__main__":
    main()
