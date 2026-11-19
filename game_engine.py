import json, socket, time
import math, random

FIELD_W = 1600
FIELD_H = 480
PADDLE_H = 80
PADDLE_W = 10
BALL_SIZE = 10

PADDLE_X = 20 # Paddle offset from side of screen

TICK_HZ = 30
SERVE_DELAY_S = 1
TIMEOUT_S = 2

WIN_SCORE = 5

dt = 1/30
BALL_SPEED = 150 * dt
PADDLE_SPEED = 300 * dt

TARGETS = [("127.0.0.1", 9101), ("127.0.0.1", 9102)]
ENGINE_IP = "127.0.0.1"

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

# Game variables
phase = "playing"
ball_x, ball_y = FIELD_W/2, FIELD_H/2
score_a, score_b = 0, 0
rally = 0 # Rally length
seq = 0

# Player variables
direction = {"A": 0, "B": 0}
last_seq = {"A": -1, "B": -1}
last_input_time = {"A": None, "B": None}
paddle_y = {"A": FIELD_H/2, "B": FIELD_H/2}

def new_serve(toward):
    '''Moves ball to the center of the screen and serves in the given direction.
    On start, the direction is random.'''
    global ball_vx, ball_vy, ball_x, ball_y
    ball_x, ball_y = FIELD_H/2, FIELD_W/2
    angle = math.radians(random.randint(-30,30))
    if toward == "A":
        ball_vx, ball_vy = BALL_SPEED * -math.cos(angle), BALL_SPEED * math.sin(angle)
    elif toward == "B":
        ball_vx, ball_vy = BALL_SPEED * math.cos(angle), BALL_SPEED * math.sin(angle)

new_serve(random.choice(["A", "B"]))
next_tick = time.monotonic()

try:
    while True:
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
                if score_b == WIN_SCORE:
                    phase = "over"
                else:
                    phase = "serve"
                    serve_start = time.monotonic()
                    new_serve("A")
            if ball_x >= FIELD_W - BALL_SIZE / 2:
                score_a += 1
                rally = 0
                if score_a == WIN_SCORE:
                    phase = "over"
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

        next_tick += 1/30
        timecheck = time.monotonic()
        if (next_tick - timecheck) > 0:
            time.sleep(next_tick - timecheck)
except KeyboardInterrupt:
    print("stopped")