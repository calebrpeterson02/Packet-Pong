import json
import os
import socket
import time

from sense_hat import SenseHat

PLAYER = os.environ.get("PLAYER", "A")
ENGINE_IP = os.environ.get("ENGINE_IP", "192.168.5.52")
if PLAYER == "A":
    ENGINE_PORT = 9001
else:
    ENGINE_PORT = 9002
TICK = 1 / 30  # 30 Hz

sense = SenseHat()
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

direction = 0
seq = 0
next_tick = time.monotonic()

while True:
    # 1. Turn joystick events into the current direction
    for event in sense.stick.get_events():
        if event.direction not in ("up", "down"):
            continue  # left/right/middle unused in pong
        if event.action in ("pressed", "held"):
            if event.direction == "up":
                direction = 1
            else:
                direction = -1
        elif event.action == "released":
            direction = 0

    # 2. Build and send the input message (every tick, even if dir == 0)
    msg = {"t": "input", "p": PLAYER, "seq": seq, "dir": direction}
    data = json.dumps(msg, separators=(",", ":")).encode("utf-8")
    try:
        sock.sendto(data, (ENGINE_IP, ENGINE_PORT))
    except OSError:
        pass  # network not up yet (e.g. at boot) — just try again next tick
    seq += 1

    # 3. Sleep until the next 33 ms tick
    next_tick += TICK
    delay = next_tick - time.monotonic()
    if delay > 0:
        time.sleep(delay)
    else:
        next_tick = time.monotonic()  # fell behind; resync instead of bursting
