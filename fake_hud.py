"""Fake HUD control client for testing game_engine.py - NOT the real HUD.

Connects to the engine's lobby/control port (TCP 8000, PROTOCOL.md section 4),
sends the `hello` handshake, prints every line the engine sends back, and lets
you type commands.

Usage:
    python fake_hud.py A              connect as player A
    python fake_hud.py B              connect as player B
    python fake_hud.py A --no-hello   connect without sending hello
                                      (to test handshake rejection by hand)

Commands (type and press Enter):
    ready | pause | resume | rematch  send {"t": "<command>"}
    {"t": "hello", "p": "C", "v": 1}  any line starting with { is sent as-is
    quit                              disconnect and exit
"""
import json
import socket
import sys
import threading
import time

ENGINE = ("127.0.0.1", 8000)
COMMANDS = ("ready", "pause", "resume", "rematch")

if len(sys.argv) < 2 or sys.argv[1].upper() not in ("A", "B"):
    print("Usage: python fake_hud.py A|B [--no-hello]")
    sys.exit(1)
player = sys.argv[1].upper()
send_hello = "--no-hello" not in sys.argv

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.connect(ENGINE)
except OSError as e:
    print(f"Could not connect to {ENGINE[0]}:{ENGINE[1]} - is the engine running? ({e})")
    sys.exit(1)
print(f"Connected to {ENGINE[0]}:{ENGINE[1]} as player {player}")
quitting = False    # set when we disconnect on purpose


def send(msg):
    line = json.dumps(msg)
    sock.sendall((line + "\n").encode())
    print(f"  -> {line}")


def receive():
    """Background thread: print every newline-delimited message from the engine."""
    buf = b""
    while True:
        try:
            data = sock.recv(4096)
        except OSError:
            data = b""
        if not data:
            if not quitting:
                print("\n[engine closed the connection]")
            return
        buf += data
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            print(f"  <- {line.decode(errors='replace')}")


threading.Thread(target=receive, daemon=True).start()

if send_hello:
    send({"t": "hello", "p": player, "v": 1})

print("Type: ready | pause | resume | rematch | {raw json} | quit")
try:
    while True:
        try:
            text = input().strip()
        except EOFError:
            time.sleep(0.5)     # input was piped in; give replies time to print
            break
        if not text:
            continue
        if text == "quit":
            break
        if text.startswith("{"):
            try:
                send(json.loads(text))
            except ValueError:
                print("  (not valid JSON)")
        elif text in COMMANDS:
            send({"t": text})
        else:
            print("  (unknown - use ready, pause, resume, rematch, {json} or quit)")
except (KeyboardInterrupt, OSError):
    pass
finally:
    quitting = True
    sock.close()
    print("disconnected")
