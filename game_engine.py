import json
import math
import random
import socket
import time

FIELD_W = 1600
FIELD_H = 480
PADDLE_H = 80
PADDLE_W = 10
BALL_SIZE = 10

PADDLE_X = 20  # Paddle offset from side of screen

TICK_HZ = 30
SERVE_DELAY_S = 1
TIMEOUT_S = 2

WIN_SCORE = 5

dt = 1 / 30
BALL_SPEED = 300 * dt
PADDLE_SPEED = 300 * dt

TARGETS = [("127.0.0.1", 9101), ("127.0.0.1", 9102)]
ENGINE_IP = "127.0.0.1"
PROTOCOL_VERSION = 1

# Sending socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setblocking(False)

# Controller A socket
sock_a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_a.bind((ENGINE_IP, 9001))
sock_a.setblocking(False)

# Controller B socket
sock_b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_b.bind((ENGINE_IP, 9002))
sock_b.setblocking(False)

# TCP Socket
tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
tcp_sock.bind((ENGINE_IP, 8000))
tcp_sock.listen()
tcp_sock.setblocking(False)

# LED Socket
led_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
led_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
led_sock.bind((ENGINE_IP, 9300))
led_sock.listen()
led_sock.setblocking(False)

# Socket variables
conns = []
ready = {"A": False, "B": False}
rematch = {"A": False, "B": False}

# Game variables
phase = "lobby"
ball_x, ball_y = FIELD_W/2, FIELD_H/2
score_a, score_b = 0, 0
rally = 0  # Rally length
seq = 0

# Player variables
direction = {"A": 0, "B": 0}
last_seq = {"A": -1, "B": -1}
last_input_time = {"A": None, "B": None}
paddle_y = {"A": FIELD_H/2, "B": FIELD_H/2}

def new_serve(toward):
    """Moves ball to the center of the screen and serves in the given direction.
    On start, the direction is random."""
    global ball_vx, ball_vy, ball_x, ball_y
    ball_x, ball_y = FIELD_W/2, FIELD_H/2
    angle = math.radians(random.randint(-30,30))
    if toward == "A":
        ball_vx, ball_vy = BALL_SPEED * -math.cos(angle), BALL_SPEED * math.sin(angle)
    elif toward == "B":
        ball_vx, ball_vy = BALL_SPEED * math.cos(angle), BALL_SPEED * math.sin(angle)

def drop(c):
    '''Closes a HUD connection and removes it from conns.'''
    global phase
    try:
        c["sock"].close()
    except OSError:
        pass    # already closed or broken
    if c in conns:
        conns.remove(c)
        if c["player"] is not None and phase in ("serve", "playing") and c["kind"] == "hud":
            phase = "paused"
            led_all("paused")
        elif c["player"] is not None and phase == "lobby" and c["kind"] == "hud":
            ready[c["player"]] = False
            broadcast({"t": "lobby", "ready": ready})
    print("dropped", c["player"])

def send_line(c, msg):
    '''Turns msg into bytes and sends it to the HUD connection.'''
    try:
        data = (json.dumps(msg) + "\n").encode()
        c["sock"].sendall(data)
    except OSError:
        pass

def broadcast(msg):
    '''Loops over conns and calls send_line() for every connection'''
    for c in conns:
        if c["player"] is not None and c["kind"] == "hud":
            send_line(c, msg)

def led(p, ev):
    for c in conns:
        if c["kind"] == "led" and c["player"] == p:
            send_line(c, {"t": "led", "ev": ev})

def led_all(ev):
    for p in ("A", "B"):
        led(p, ev)

next_tick = time.monotonic()

try:
    while True:
        for lsock, kind in ((tcp_sock, "hud"), (led_sock, "led")):
            while True:
                try:
                    new_sock, addr = lsock.accept()
                    new_sock.setblocking(False)
                    conns.append({"sock": new_sock, "buf": b"", "player": None, "kind": kind})
                    print(addr)
                except BlockingIOError:
                    break

        for c in conns[:]:
            try:
                data = c["sock"].recv(4096)
            except BlockingIOError:
                continue
            except OSError:
                drop(c)
                continue

            if data == b"":
                drop(c)
                continue

            else:
                c["buf"] += data
                while b"\n" in c["buf"]:
                    line, c["buf"] = c["buf"].split(b"\n", 1)
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue

                    if not isinstance(msg, dict):
                        continue

                    if c["player"] is None:
                        p = msg.get("p")
                        
                        if msg.get("t") != "hello":
                            send_line(c, {"t": "error", "msg": "expected hello"})
                            drop(c)
                            break
                        
                        elif msg.get("v") != PROTOCOL_VERSION:
                            send_line(c, {"t": "error", "msg": "unsupported protocol version"})
                            drop(c)
                            break

                        elif p not in ("A", "B"):
                            send_line(c, {"t": "error", "msg": "invalid player"})
                            drop(c)
                            break

                        elif any(other["player"] == p and other["kind"] == c["kind"] for other in conns):
                            send_line(c, {"t": "error", "msg": f"player {p} already connected."})
                            drop(c)
                            break

                        else:
                            c["player"] = p
                            send_line(c, {"t": "welcome", "p": p})
                            if c["kind"] == "hud":
                                send_line(c, {"t": "lobby", "ready": ready})
                                send_line(c, {"t": "board", "rows":[]})
                            elif c["kind"] == "led":
                                if phase == "paused":
                                    ev = "paused"
                                elif phase == "over":
                                    if (p == "A" and score_a > score_b) or (p == "B" and score_b > score_a):
                                        ev = "win"
                                    else:
                                        ev = "lose"
                                else:
                                    ev = "clear"
                                send_line(c, {"t": "led", "ev": ev})
                            print(f"{c['kind']} {p} joined")
                        
                    elif c["kind"] == "hud":
                        t = msg.get("t")
                        p = c["player"]
                        if t == "ready":
                            if phase == "lobby":
                                ready[p] = True
                                broadcast({"t": "lobby", "ready": ready})
                                if all(ready.values()):
                                    score_a, score_b, rally = 0, 0, 0
                                    paddle_y = {"A": FIELD_H/2, "B": FIELD_H/2}
                                    new_serve(random.choice(["A", "B"]))
                                    serve_start = time.monotonic()
                                    phase = "serve"
                                    led_all("clear")
                            else:
                                send_line(c, {"t": "error", "msg": f"cannot {t} in {phase}"})
                        elif t == "pause":
                            if phase in ("serve", "playing"):
                                phase = "paused"
                                led_all("paused")
                            else:
                                send_line(c, {"t": "error", "msg": f"cannot {t} in {phase}"})
                        elif t == "resume":
                            if phase == "paused":
                                phase = "serve"
                                led_all("clear")
                                serve_start = time.monotonic()
                            else:
                                send_line(c, {"t": "error", "msg": f"cannot {t} in {phase}"})
                        elif t == "rematch":
                            if phase == "over":
                                rematch[p] = True
                                if all(rematch.values()):
                                    score_a, score_b, rally = 0, 0, 0
                                    ready = {"A": False, "B": False}
                                    rematch = {"A": False, "B": False}
                                    ball_x, ball_y = FIELD_W/2, FIELD_H/2
                                    paddle_y = {"A": FIELD_H/2, "B": FIELD_H/2}
                                    phase = "lobby"
                                    led_all("clear")
                                    broadcast({"t": "lobby", "ready": ready})
                            else:
                                send_line(c, {"t": "error", "msg": f"cannot {t} in {phase}"})
                        else:
                            send_line(c, {"t": "error", "msg": f"unknown command {t}"})


        for player, s in (("A", sock_a), ("B", sock_b)):
            while True:
                try:
                    data, addr = s.recvfrom(1024)  # buffer size is 1024 bytes
                except BlockingIOError:
                    break   # no more data to read

                try:
                    msg = json.loads(data)
                except ValueError:
                    continue    # garbled packet, skip it

                if not (isinstance(msg, dict) and msg.get("t") == "input"):
                    continue    # not an input

                if msg.get("p") != player:
                    continue    # not correct player

                in_seq = msg.get("seq", -1)
                if in_seq <= last_seq[player] and last_seq[player] - in_seq <= 1000:
                    continue    # old or duplicate packet (a drop > 1000 means the controller restarted)

                if msg.get("dir") not in (-1, 0, 1):
                    continue    # not a valid direction

                direction[player] = msg["dir"]
                last_seq[player] = in_seq
                last_input_time[player] = time.monotonic()

        for player in ("A", "B"):
            if last_input_time[player] is None or time.monotonic() - last_input_time[player] > TIMEOUT_S:
                direction[player] = 0
                
        if phase == "serve":
            if time.monotonic() - serve_start >= SERVE_DELAY_S:
                phase = "playing"
            for player in ("A", "B"):
                paddle_y[player] += direction[player] * PADDLE_SPEED
                if paddle_y[player] >= FIELD_H - PADDLE_H/2:
                    paddle_y[player] = FIELD_H - PADDLE_H/2
                if paddle_y[player] <= PADDLE_H/2:
                    paddle_y[player] = PADDLE_H/2
        elif phase == "playing":
            # Currently, if the paddle intersects the ball before it hits
            # the wall, the ball will snap to in front of the paddle. Test how this
            # feels to see if this should be intended behavior or not.
            
            for player in ("A", "B"):
                paddle_y[player] += direction[player] * PADDLE_SPEED
                if paddle_y[player] >= FIELD_H - PADDLE_H/2:
                    paddle_y[player] = FIELD_H - PADDLE_H/2
                if paddle_y[player] <= PADDLE_H/2:
                    paddle_y[player] = PADDLE_H/2

            ball_x += ball_vx
            ball_y += ball_vy

            if ball_x - BALL_SIZE / 2 <= (PADDLE_X + PADDLE_W / 2) and abs(ball_y - paddle_y["A"]) <= BALL_SIZE / 2 + PADDLE_H / 2 and ball_vx < 0:
                ball_vx = -ball_vx
                ball_x = BALL_SIZE / 2 + (PADDLE_X + PADDLE_W / 2)
                rally += 1
            if ball_x + BALL_SIZE / 2 >= (FIELD_W - PADDLE_X - PADDLE_W / 2) and abs(ball_y - paddle_y["B"]) <= BALL_SIZE / 2 + PADDLE_H / 2 and ball_vx > 0:
                ball_vx = -ball_vx
                ball_x = FIELD_W - PADDLE_X - PADDLE_W / 2 - BALL_SIZE / 2
                rally += 1
            if ball_y <= BALL_SIZE / 2:
                ball_vy = abs(ball_vy)
                ball_y = BALL_SIZE / 2
            if ball_y >= FIELD_H - BALL_SIZE / 2:
                ball_vy = -abs(ball_vy)
                ball_y = FIELD_H - BALL_SIZE / 2
            if ball_x <= BALL_SIZE / 2:
                score_b += 1
                rally = 0
                led("B", "goal_for")
                led("A", "goal_against")
                if score_b == WIN_SCORE:
                    phase = "over"
                    ball_x, ball_y = FIELD_W/2, FIELD_H/2
                    led("B", "win")
                    led("A", "lose")
                else:
                    phase = "serve"
                    serve_start = time.monotonic()
                    new_serve("A")
            if ball_x >= FIELD_W - BALL_SIZE / 2:
                score_a += 1
                rally = 0
                led("A", "goal_for")
                led("B", "goal_against")
                if score_a == WIN_SCORE:
                    phase = "over"
                    ball_x, ball_y = FIELD_W/2, FIELD_H/2
                    led("A", "win")
                    led("B", "lose")
                else:
                    phase = "serve"
                    serve_start = time.monotonic()
                    new_serve("B")

        state = {
            "t": "state",
            "seq": seq,
            "phase": phase,
            "ball": [round(ball_x, 1), round(ball_y, 1)],
            "pa": round(paddle_y["A"], 1),
            "pb": round(paddle_y["B"], 1),
            "sa": score_a,
            "sb": score_b,
            "rally": rally,
            "ctrl": {"A": (last_input_time["A"] is not None and time.monotonic() - last_input_time["A"] < TIMEOUT_S), "B": (last_input_time["B"] is not None and time.monotonic() - last_input_time["B"] < TIMEOUT_S)},
        }
        data = json.dumps(state).encode()
        for target in TARGETS:
            sock.sendto(data, target)

        seq += 1

        next_tick += 1 / 30
        timecheck = time.monotonic()
        if (next_tick - timecheck) > 0:
            time.sleep(next_tick - timecheck)
except KeyboardInterrupt:
    print("stopped")
