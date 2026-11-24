import json
import os
import socket
import time
import signal

from dotenv import load_dotenv
from sense_hat import SenseHat

load_dotenv()  # read the repo's .env; values already set (e.g. by docker env_file) win

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

# TCP connection the engine uses to send LED events
LED_PORT = 9300
RECONNECT_S = 2
FLASH_S = 0.5
led_sock = None
led_buf = b""
last_connect_try = 0
flash_until = None


def connect_led():
    """Opens the LED event connection to the engine and sends hello."""
    global led_sock, led_buf
    try:
        s = socket.create_connection((ENGINE_IP, LED_PORT), timeout=0.5)
        s.sendall((json.dumps({"t": "hello", "p": PLAYER, "v": 1}) + "\n").encode())
        s.setblocking(False)
        led_sock, led_buf = s, b""
        print("[+] Connected to engine LED events")
    except OSError:
        led_sock = None


def show(ev):
    """Shows one LED event on the Sense HAT matrix."""
    global flash_until
    flash_until = None
    if ev == "goal_for":
        sense.clear((0, 255, 0))
        flash_until = time.monotonic() + FLASH_S
    elif ev == "goal_against":
        sense.clear((255, 0, 0))
        flash_until = time.monotonic() + FLASH_S
    elif ev == "win":
        sense.show_letter("W", text_colour=(0, 255, 0))
    elif ev == "lose":
        sense.show_letter("L", text_colour=(255, 0, 0))
    elif ev == "paused":
        sense.show_letter("P", text_colour=(255, 255, 0))
    elif ev == "clear":
        sense.clear()


def on_sigterm(signum, frame):
    """Turns Docker's stop signal into a normal exit so the finally block runs."""
    raise SystemExit


signal.signal(signal.SIGTERM, on_sigterm)

try:
    while True:
        # 1. Turn joystick events into the current direction
        for event in sense.stick.get_events():
            if event.direction not in ("up", "down"):
                continue  # left/right/middle unused in pong
            if event.action in ("pressed", "held"):
                if event.direction == "up":
                    direction = -1
                else:
                    direction = 1
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

        # 3. Read LED events from the engine (reconnect every 2 s if the link is down)
        if led_sock is None and time.monotonic() - last_connect_try >= RECONNECT_S:
            last_connect_try = time.monotonic()
            connect_led()

        if led_sock is not None:
            try:
                data = led_sock.recv(1024)
            except BlockingIOError:
                data = None  # nothing new this tick
            except OSError:
                data = b""

            if data == b"":
                print("[ERROR] Engine closed the LED connection")
                sense.clear()
                flash_until = None
                led_sock.close()
                led_sock = None
            elif data:
                led_buf += data
                while b"\n" in led_buf:
                    line, led_buf = led_buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(msg, dict) and msg.get("t") == "led":
                        show(msg.get("ev"))

        if flash_until is not None and time.monotonic() >= flash_until:
            sense.clear()  # end of a goal flash
            flash_until = None

        # 4. Sleep until the next 33 ms tick
        next_tick += TICK
        delay = next_tick - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_tick = time.monotonic()  # fell behind; resync instead of bursting
finally:
    sense.clear()
    if led_sock is not None:
        led_sock.close()