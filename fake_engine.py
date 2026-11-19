"""Fake engine for testing HUD.py - NOT the real game engine.

Sends made-up `state` packets (PROTOCOL.md section 3) 30 times a second to
both local HUD ports: HUD A on 127.0.0.1:9101 and HUD B on 127.0.0.1:9102.
The ball bounces off every edge, the paddles follow it, and a point is
added each time it hits the left or right wall.

Usage:  python fake_engine.py      (Ctrl+C to stop)
"""
import json
import socket
import time

TARGETS = [("127.0.0.1", 9101), ("127.0.0.1", 9102)]

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # send-only, no bind needed

seq = 0
x, y = 400.0, 240.0      # ball center
vx, vy = 6.0, 4.0        # ball velocity, units per frame
sa, sb = 0, 0            # scores

print("Sending fake state to", TARGETS, "- Ctrl+C to stop")
try:
    while True:
        # Move the ball and bounce it off the edges
        x += vx
        y += vy
        if y < 5 or y > 475:
            vy = -vy
        if x < 5:
            vx = -vx
            sb += 1          # ball reached A's side: point for B
        elif x > 795:
            vx = -vx
            sa += 1          # ball reached B's side: point for A

        # Paddles follow the ball, kept fully on screen (paddle is 80 tall)
        paddle_y = min(max(y, 40), 440)

        state = {
            "t": "state",
            "seq": seq,
            "phase": "playing",
            "ball": [round(x, 1), round(y, 1)],
            "pa": round(paddle_y, 1),
            "pb": round(paddle_y, 1),
            "sa": sa,
            "sb": sb,
            "rally": 0,
            "ctrl": {"A": True, "B": True},
        }
        data = json.dumps(state).encode()
        for target in TARGETS:
            sock.sendto(data, target)

        seq += 1
        time.sleep(1 / 30)
except KeyboardInterrupt:
    print("stopped")
