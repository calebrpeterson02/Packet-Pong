import json, socket, time
import math, random

FIELD_W = 800
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

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setblocking(False)

phase = "playing"
ball_x, ball_y = 400.0, 240.0
angle = math.radians(random.randint(-30,30)) # Serve angle
ball_vx, ball_vy = BALL_SPEED * math.cos(angle), BALL_SPEED * math.sin(angle)
paddle_a, paddle_b = 240, 240 # Paddle y values
score_a, score_b = 0, 0
rally = 0 # Rally length
seq = 0

next_tick = time.monotonic()
try:
    while True:
        if phase == "serve":
            start = time.monotonic()
            time.sleep(SERVE_DELAY_S)
            phase = "playing"
        elif phase == "playing":
            ball_x += ball_vx
            ball_y += ball_vy

            if ball_y <= BALL_SIZE / 2:
                ball_vy = abs(ball_vy)
                ball_y = BALL_SIZE / 2
            if ball_y >= FIELD_H - BALL_SIZE / 2:
                ball_vy = -abs(ball_vy)
                ball_y = FIELD_H - BALL_SIZE / 2
            if ball_x <= BALL_SIZE / 2:
                ball_x, ball_y = 400.0, 240.0 
                ball_vx, ball_vy = -BALL_SPEED * math.cos(angle), BALL_SPEED * math.sin(angle)
                score_b += 1
                rally = 0
                if score_b == WIN_SCORE:
                    phase = "over"
            if ball_x >= FIELD_W - BALL_SIZE / 2:
                ball_x, ball_y = 400.0, 240.0
                ball_vx, ball_vy = BALL_SPEED * math.cos(angle), BALL_SPEED * math.sin(angle)
                score_a += 1
                rally = 0
                if score_a == WIN_SCORE:
                    phase = "over"

        state = {
            "t": "state",
            "seq": seq,
            "phase": phase,
            "ball": [round(ball_x, 1), round(ball_y, 1)],
            "pa": round(paddle_a, 1),
            "pb": round(paddle_b, 1),
            "sa": score_a,
            "sb": score_b,
            "rally": rally,
            "ctrl": {"A": True, "B": True},
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