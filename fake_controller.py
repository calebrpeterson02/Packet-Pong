"""Fake controller for testing game_engine.py - NOT the real Sense HAT controller.

Opens a small pygame window and sends `input` packets (PROTOCOL.md section 2)
for BOTH players 30 times a second:

    Player A (left paddle):   W = up,  S = down      -> 127.0.0.1:9001
    Player B (right paddle):  Up arrow = up, Down arrow = down -> 127.0.0.1:9002

    Enter  = send `ready` for BOTH players (see note below)
    1 / 2  = stop/start sending input for player A / B (to test the 2 s timeout)
    Esc or close the window = quit

Note on Enter: in the real system `ready` comes from the HUD over TCP port
8000, not from the controller. To save you running two fake_hud.py windows,
this tool also acts as both HUDs on the control channel: the first Enter opens
a TCP connection per player, sends `hello`, then `ready`. The connections stay
open (closing them would count as the HUDs disconnecting). If a real HUD or
fake_hud.py is already connected as A or B, the engine rejects this tool's
`hello` for that player - the error is shown in the window.

The window must have keyboard focus for the keys to register.

Usage:  python fake_controller.py
"""
import json
import socket

import pygame

ENGINE_IP = "127.0.0.1"
PORTS = {"A": 9001, "B": 9002}
CONTROL_PORT = 8000
KEYS = {"A": (pygame.K_w, pygame.K_s), "B": (pygame.K_UP, pygame.K_DOWN)}

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # send-only, no bind needed
seq = {"A": 0, "B": 0}
sending = {"A": True, "B": True}

# TCP control connections (acting as the HUDs), one per player
tcp = {"A": None, "B": None}
tcp_buf = {"A": b"", "B": b""}
tcp_status = {"A": "not connected", "B": "not connected"}


def send_line(player, msg):
    tcp[player].sendall((json.dumps(msg) + "\n").encode())


def close_tcp(player, status):
    if tcp[player] is not None:
        try:
            tcp[player].close()
        except OSError:
            pass
    tcp[player] = None
    tcp_buf[player] = b""
    tcp_status[player] = status


def send_ready():
    """Connect + hello (first time only), then send ready, for both players."""
    for player in ("A", "B"):
        try:
            if tcp[player] is None:
                s = socket.create_connection((ENGINE_IP, CONTROL_PORT), timeout=1)
                s.setblocking(False)
                tcp[player] = s
                send_line(player, {"t": "hello", "p": player, "v": 1})
            send_line(player, {"t": "ready"})
            tcp_status[player] = "sent ready"
        except OSError as e:
            close_tcp(player, f"connect failed: {e.__class__.__name__}")


def read_tcp():
    """Drain replies from the engine so we can show the latest one."""
    for player in ("A", "B"):
        s = tcp[player]
        if s is None:
            continue
        try:
            data = s.recv(4096)
        except BlockingIOError:
            continue
        except OSError:
            data = b""
        if not data:
            close_tcp(player, "engine closed connection")
            continue
        tcp_buf[player] += data
        while b"\n" in tcp_buf[player]:
            line, tcp_buf[player] = tcp_buf[player].split(b"\n", 1)
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            t = msg.get("t") if isinstance(msg, dict) else None
            if t == "error":
                tcp_status[player] = f"error: {msg.get('msg')}"
            elif t == "lobby":
                who = [q for q, r in msg.get("ready", {}).items() if r]
                tcp_status[player] = "lobby, ready: " + (", ".join(who) or "nobody")
            elif t in ("welcome", "board"):
                pass   # keep the more useful status
            else:
                tcp_status[player] = str(t)


pygame.init()
window = pygame.display.set_mode((420, 230))
pygame.display.set_caption("Fake Controller")
font = pygame.font.Font(None, 24)
clock = pygame.time.Clock()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                send_ready()
            elif event.key == pygame.K_1:
                sending["A"] = not sending["A"]
            elif event.key == pygame.K_2:
                sending["B"] = not sending["B"]

    read_tcp()

    keys = pygame.key.get_pressed()
    dirs = {}
    for player in ("A", "B"):
        up_key, down_key = KEYS[player]
        # -1 = up, 1 = down, 0 = none (both held also cancels out to 0)
        dirs[player] = keys[down_key] - keys[up_key]

        if sending[player]:
            msg = {"t": "input", "p": player, "seq": seq[player], "dir": dirs[player]}
            sock.sendto(json.dumps(msg).encode(), (ENGINE_IP, PORTS[player]))
            seq[player] += 1

    # Status display
    window.fill("black")
    lines = [
        "A: W/S   B: Up/Down   1/2: toggle   Enter: ready",
        f"A  dir {dirs['A']:+d}  seq {seq['A']:<6} {'SENDING' if sending['A'] else 'STOPPED'}",
        f"B  dir {dirs['B']:+d}  seq {seq['B']:<6} {'SENDING' if sending['B'] else 'STOPPED'}",
        f"A control: {tcp_status['A']}",
        f"B control: {tcp_status['B']}",
    ]
    for i, text in enumerate(lines):
        window.blit(font.render(text, True, "white"), (12, 15 + i * 42))
    pygame.display.flip()

    clock.tick(30)

for player in ("A", "B"):
    close_tcp(player, "")
pygame.quit()
