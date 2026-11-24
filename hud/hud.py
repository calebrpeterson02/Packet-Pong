import json
import os
import socket
import sys
import time

import pygame
from dotenv import load_dotenv

load_dotenv()  # read the repo's .env; values already set (e.g. by docker env_file) win

pygame.init()
window = pygame.display.set_mode((800, 480), pygame.FULLSCREEN)
pygame.display.set_caption("Packet Pong")

clock = pygame.time.Clock()
FIELD_W = 1600

### Put code you want to run once before the game starts below this!
player = os.environ.get("PLAYER", "A").upper()
if player == "A":
    bind_ip = "0.0.0.0"  # engine runs on this same Pi
    bind_port = 9101
    view_offset = 0
elif player == "B":
    bind_ip = "0.0.0.0"
    bind_port = 9102
    view_offset = FIELD_W / 2
else:
    print("Invalid PLAYER. Use 'A' or 'B'.")
    sys.exit(1)

udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # IPv4 + UDP
udp_sock.bind((bind_ip, bind_port))  # note: one tuple argument
udp_sock.setblocking(False)

latest_state = None
last_seq = -1
last_state_time = None

font = pygame.font.Font(None, 36)

# TCP control connection to the engine (lobby / pause / rematch)
ENGINE_IP = os.environ.get("ENGINE_IP", "192.168.5.52")
RECONNECT_S = 2
tcp_sock = None
tcp_buf = b""
last_connect_try = 0
ready = {"A": False, "B": False}
board = []

# The one on-screen button sends the command that fits the current phase
COMMANDS = {
    "lobby": "ready",
    "serve": "pause",
    "playing": "pause",
    "paused": "resume",
    "over": "rematch",
}
button = pygame.Rect(340, 10, 120, 40)


def connect():
    """Opens the TCP connection to the engine and sends hello."""
    global tcp_sock, tcp_buf
    try:
        s = socket.create_connection((ENGINE_IP, 8000), timeout=0.5)
        s.sendall((json.dumps({"t": "hello", "p": player, "v": 1}) + "\n").encode())
        s.setblocking(False)
        tcp_sock, tcp_buf = s, b""
        print("[+] Connected to engine")
    except OSError:
        tcp_sock = None


def send(msg):
    """Sends one command line to the engine."""
    global tcp_sock
    if tcp_sock is None:
        return
    try:
        tcp_sock.sendall((json.dumps(msg) + "\n").encode())
    except OSError:
        tcp_sock.close()
        tcp_sock = None


### Put code you want to run once before the game starts above this!

should_run = True
while should_run:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            should_run = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                should_run = False

        # Tap the button (or press Space) to send this phase's command
        pressed = (
            event.type == pygame.MOUSEBUTTONDOWN and button.collidepoint(event.pos)
        ) or (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE)
        if pressed and latest_state is not None:
            command = COMMANDS.get(latest_state["phase"])
            if command:
                send({"t": command})

    ### Put code you want to run every frame below this!
    if tcp_sock is None and time.monotonic() - last_connect_try >= RECONNECT_S:
        last_connect_try = time.monotonic()
        connect()

    if tcp_sock is not None:
        try:
            data = tcp_sock.recv(4096)
        except BlockingIOError:
            data = None  # nothing new this frame
        except OSError:
            data = b""

        if data == b"":
            print("[ERROR] Engine closed the connection")
            tcp_sock.close()
            tcp_sock = None  # retry in RECONNECT_S
        elif data:
            tcp_buf += data
            while b"\n" in tcp_buf:
                line, tcp_buf = tcp_buf.split(b"\n", 1)
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(msg, dict):
                    continue
                if msg.get("t") == "lobby":
                    ready = msg["ready"]
                elif msg.get("t") == "board":
                    board = msg["rows"]
                elif msg.get("t") == "error":
                    print("[ERROR]", msg.get("msg"))

    while True:
        try:
            data, addr = udp_sock.recvfrom(2048)  # buffer size is 2048 bytes
        except BlockingIOError:
            break  # no more data to read

        try:
            msg = json.loads(data)
        except ValueError:
            continue  # garbled packet, skip it

        if not isinstance(msg, dict) or msg.get("t") != "state":
            continue  # not a state message

        seq = msg.get("seq", -1)
        if seq <= last_seq and last_seq - seq <= 1000:
            continue  # old or duplicate packet (a drop > 1000 means the engine restarted)

        latest_state = msg
        last_seq = seq
        last_state_time = time.monotonic()

    # Logic goes above, draw goes below
    window.fill("black")

    if latest_state is None:
        text = font.render("Waiting for engine...", True, "white")
        textpos = text.get_rect(centerx=window.get_width() / 2, y=10)
        window.blit(text, textpos)
    else:
        # Paddles
        paddle_a = pygame.Rect(0, 0, 10, 80)
        paddle_a.center = (20 - view_offset, latest_state["pa"])
        paddle_b = pygame.Rect(0, 0, 10, 80)
        paddle_b.center = (FIELD_W - 20 - view_offset, latest_state["pb"])

        pygame.draw.rect(window, "white", paddle_a)
        pygame.draw.rect(window, "white", paddle_b)

        # Ball
        ball_x, ball_y = latest_state["ball"]
        pygame.draw.circle(
            window, "white", center=(ball_x - view_offset, ball_y), radius=5
        )

        # Scores
        player_a_score = font.render(str(latest_state["sa"]), True, "white")
        player_b_score = font.render(str(latest_state["sb"]), True, "white")
        window.blit(player_a_score, (200, 20))
        window.blit(player_b_score, (600, 20))

        # Phase message
        phase = latest_state["phase"]
        if phase == "lobby":
            status = f"A: {'ready' if ready['A'] else 'not ready'}    B: {'ready' if ready['B'] else 'not ready'}"
        elif phase == "paused":
            status = "PAUSED"
        elif phase == "over":
            status = ("A" if latest_state["sa"] > latest_state["sb"] else "B") + " wins!"
        else:
            status = ""
        text = font.render(status, True, "white")
        window.blit(text, text.get_rect(centerx=window.get_width() / 2, y=140))

        # Leaderboard between matches
        if phase in ("lobby", "over"):
            title = font.render("Longest rallies", True, "white")
            window.blit(title, title.get_rect(centerx=window.get_width() / 2, y=200))
            for i, row in enumerate(board[:5]):
                line = font.render(
                    f"{row['rally']} hits  (match {row['match_id']})", True, "white"
                )
                window.blit(
                    line, line.get_rect(centerx=window.get_width() / 2, y=240 + i * 32)
                )

        # Command button, or a notice while the TCP link is down
        if tcp_sock is None:
            label = font.render("Connecting...", True, "gray")
        else:
            pygame.draw.rect(window, "white", button, 2)
            label = font.render(COMMANDS.get(phase, "").capitalize(), True, "white")
        window.blit(label, label.get_rect(center=button.center))

    ### Put code you want to run every frame above this!

    pygame.display.flip()

    clock.tick(30)


pygame.quit()
