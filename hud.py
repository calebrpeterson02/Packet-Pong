import pygame
import socket, json, time, sys

pygame.init()
window = pygame.display.set_mode((800, 480), pygame.FULLSCREEN)
pygame.display.set_caption("Packet Pong")

clock = pygame.time.Clock()

### Put code you want to run once before the game starts below this!
player = sys.argv[1].upper()
if player == "A":
    bind_ip = "127.0.0.1"
    bind_port = 9101
elif player == "B":
    bind_ip = "127.0.0.1"  # "192.168.5.42"
    bind_port = 9102 # 9101
else:
    print("Invalid player argument. Use 'A' or 'B'.")
    sys.exit(1)

udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # IPv4 + UDP
udp_sock.bind((bind_ip, bind_port))                            # note: one tuple argument
udp_sock.setblocking(False)

latest_state = None
last_seq = -1
last_state_time = None

font = pygame.font.Font(None, 36)


### Put code you want to run once before the game starts above this!

should_run = True
while should_run:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            should_run = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                should_run = False

    ### Put code you want to run every frame below this!
    while True:
        try:
            data, addr = udp_sock.recvfrom(2048)  # buffer size is 2048 bytes
        except BlockingIOError:
            break   # no more data to read

        try:
            msg = json.loads(data)
        except ValueError:
            continue    # garbled packet, skip it

        if not isinstance(msg, dict) or msg.get("t") != "state":
            continue    # not a state message

        seq = msg.get("seq", -1)
        if seq <= last_seq and last_seq - seq <= 1000:
            continue    # old or duplicate packet (a drop > 1000 means the engine restarted)

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
        pygame.draw.line(window, "white", (400,0), (400,480))

        # Paddles
        paddle_a = pygame.Rect(0, 0, 10, 80)
        paddle_a.center = (20, latest_state["pa"])
        paddle_b = pygame.Rect(0, 0, 10, 80)
        paddle_b.center = (780, latest_state["pb"])

        pygame.draw.rect(window, "white", paddle_a)
        pygame.draw.rect(window, "white", paddle_b)

        # Ball
        pygame.draw.circle(window, "white", center=latest_state["ball"], radius=5)

        # Scores
        player_a_score = font.render(str(latest_state["sa"]), True, "white")
        player_b_score = font.render(str(latest_state["sb"]), True, "white")
        window.blit(player_a_score, (200, 20))
        window.blit(player_b_score, (600, 20))

    ### Put code you want to run every frame above this!

    pygame.display.flip()

    clock.tick(30)


pygame.quit()