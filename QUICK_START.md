# Quick Start Guide

## Fastest Way to Test (Local)

1. **Open 3 terminal windows**

2. **Terminal 1:**
   ```bash
   python run_node.py P1 8001
   ```

3. **Terminal 2:**
   ```bash
   python run_node.py P2 8002
   ```

4. **Terminal 3:**
   ```bash
   python run_node.py P3 8003
   ```

5. **Wait for connections** (you'll see "Connected to peer" messages)

6. **Play the game:**
   - Check whose turn it is: `token`
   - Peek at piles without drawing: `piles`
   - When it's your turn: `draw` (shows pile tops, then choose `deck`/`discard` or cancel)
   - Draw directly: `draw deck` or `draw discard`
   - See your hand: `hand`
   - Discard a card: `discard 7H` (replace with a card you have)
   - Declare win: `win 7H,7D,7S | AH,2H,3H | 10C,10D`

## For Project Demo (Separate Machines)

1. **Update IPs in `run_node.py` (on ALL machines):**
   ```python
   all_nodes = {
       "P1": ("MACHINE1_IP", 8001),  # e.g., "192.168.1.10"
       "P2": ("MACHINE2_IP", 8002),  # e.g., "192.168.1.11"
       "P3": ("MACHINE3_IP", 8003),  # e.g., "192.168.1.12"
   }
   ```

2. **Run on each machine (use machine's own IP as 3rd argument):**
   - Machine 1: `python run_node.py P1 8001 MACHINE1_IP`
   - Machine 2: `python run_node.py P2 8002 MACHINE2_IP`
   - Machine 3: `python run_node.py P3 8003 MACHINE3_IP`

3. **Check logs:** `logs/node_P1.log`, etc.

## Common Commands

| Command | Description |
|---------|-------------|
| `piles` | Show draw/discard pile tops without drawing |
| `draw` | Inspect piles, then choose `deck`/`discard` or cancel |
| `discard 7H` | Discard a card |
| `hand` | Show your cards |
| `state` | Show game state |
| `token` | Show whose turn it is |
| `win 7H,7D,7S \| AH,2H,3H` | Declare win |

## Troubleshooting

- **Can't connect?** Start P1 first, wait 2 seconds, then P2, wait 2 seconds, then P3
- **"No token"?** Wait for your turn (check with `token`)
- **Check logs:** Look in `logs/` directory for detailed information

