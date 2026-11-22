"""Fake controller for testing game_engine.py - NOT the real Sense HAT controller.

Opens a small pygame window and sends `input` packets (PROTOCOL.md section 2)
for BOTH players 30 times a second:

    Player A (left paddle):   W = up,  S = down      -> 127.0.0.1:9001
    Player B (right paddle):  Up arrow = up, Down arrow = down -> 127.0.0.1:9002

    1 / 2 = stop/start sending for player A / B (to test the 2 s timeout)
    Esc or close the window = quit

The window must have keyboard focus for the keys to register.

Usage:  python fake_controller.py
"""
import json
import socket

import pygame

ENGINE_IP = "127.0.0.1"
PORTS = {"A": 9001, "B": 9002}
KEYS = {"A": (pygame.K_w, pygame.K_s), "B": (pygame.K_UP, pygame.K_DOWN)}

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # send-only, no bind needed
seq = {"A": 0, "B": 0}
sending = {"A": True, "B": True}

pygame.init()
window = pygame.display.set_mode((360, 140))
pygame.display.set_caption("Fake Controller")
font = pygame.font.Font(None, 26)
clock = pygame.time.Clock()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_1:
                sending["A"] = not sending["A"]
            elif event.key == pygame.K_2:
                sending["B"] = not sending["B"]

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
        "A: W/S      B: Up/Down      1/2: toggle",
        f"A  dir {dirs['A']:+d}  seq {seq['A']:<6} {'SENDING' if sending['A'] else 'STOPPED'}",
        f"B  dir {dirs['B']:+d}  seq {seq['B']:<6} {'SENDING' if sending['B'] else 'STOPPED'}",
    ]
    for i, text in enumerate(lines):
        window.blit(font.render(text, True, "white"), (12, 15 + i * 40))
    pygame.display.flip()

    clock.tick(30)

pygame.quit()
