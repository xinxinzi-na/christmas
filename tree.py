# 要sudo apt install python3-pygame


# 安装依赖：pip install pygame
# 运行：python christmas_tree.py

import pygame
import math
import random
import sys

pygame.init()

WIDTH, HEIGHT = 1000, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Merry Christmas")
clock = pygame.time.Clock()

GOLD = (255, 200, 70)
WHITE = (240, 245, 255)
GREEN = (35, 200, 105)
RED = (255, 45, 65)

particles = []
snow = []
stars = []

# ==================== 圣诞树粒子 ====================

for _ in range(4500):
    h = random.uniform(0, 1)
    theta = random.uniform(0, math.tau)

    radius = (1 - h) * 1.65
    radius *= random.uniform(0.65, 1.05)
    radius *= 0.85 + 0.15 * math.cos(h * 35)

    x = radius * math.cos(theta)
    y = h * 4 - 2
    z = radius * math.sin(theta)

    color = random.choices(
        [GREEN, GOLD, WHITE, RED],
        weights=[45, 40, 10, 5]
    )[0]

    particles.append({
        "x": x,
        "y": y,
        "z": z,
        "color": color,
        "size": random.uniform(0.7, 2.0),
        "phase": random.uniform(0, math.tau),
        "start": (
            random.uniform(-7, 7),
            random.uniform(-5, 5),
            random.uniform(-7, 7)
        )
    })

# ==================== 金色螺旋灯带 ====================

for i in range(1500):
    h = i / 1499
    theta = h * math.tau * 7
    radius = (1 - h) * 1.72

    particles.append({
        "x": radius * math.cos(theta),
        "y": h * 4 - 2,
        "z": radius * math.sin(theta),
        "color": GOLD,
        "size": random.uniform(1.2, 2.5),
        "phase": random.uniform(0, math.tau),
        "start": (
            random.uniform(-6, 6),
            random.uniform(-5, 5),
            random.uniform(-6, 6)
        )
    })

# ==================== 星空与雪花 ====================

for _ in range(180):
    snow.append([
        random.random(),
        random.random(),
        random.uniform(0.015, 0.07),
        random.uniform(1, 3)
    ])

for _ in range(220):
    stars.append((
        random.random(),
        random.random(),
        random.uniform(0, math.tau)
    ))

# ==================== 发光粒子 ====================

glow_cache = {}


def glow(surface, x, y, radius, color, brightness=1):
    radius = max(1, int(radius))
    brightness = max(0.0, min(1.0, brightness))

    rgb = tuple(int(c * brightness) for c in color)
    rgb = tuple((c // 24) * 24 for c in rgb)

    key = (radius, rgb)

    if key not in glow_cache:
        r = radius * 4
        sprite = pygame.Surface((r * 2 + 1, r * 2 + 1))

        for i in range(r, 0, -1):
            strength = math.exp(-4 * (i / r) ** 2) * 0.4

            c = tuple(
                min(255, int(v * strength))
                for v in rgb
            )

            pygame.draw.circle(sprite, c, (r, r), i)

        pygame.draw.circle(sprite, rgb, (r, r), radius)
        glow_cache[key] = sprite

    sprite = glow_cache[key]

    surface.blit(
        sprite,
        (
            int(x - sprite.get_width() / 2),
            int(y - sprite.get_height() / 2)
        ),
        special_flags=pygame.BLEND_RGB_ADD
    )


# ==================== 三维投影 ====================

def project(x, y, z, angle, width, height):
    rx = x * math.cos(angle) - z * math.sin(angle)
    rz = x * math.sin(angle) + z * math.cos(angle)

    tilt = 0.12

    ry = y * math.cos(tilt) - rz * math.sin(tilt)
    depth = rz * math.cos(tilt) + y * math.sin(tilt)

    distance = max(1, 8.5 - depth)
    scale = min(width, height) * 1.32 / distance

    sx = width / 2 + rx * scale
    sy = height * 0.53 - ry * scale

    return sx, sy, scale, depth


# ==================== 五角星 ====================

def draw_star(surface, x, y, radius, t):
    points = []

    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2
        r = radius if i % 2 == 0 else radius * 0.42

        points.append((
            x + r * math.cos(angle),
            y + r * math.sin(angle)
        ))

    glow(surface, x, y, radius // 2, GOLD, 0.8)

    pygame.draw.polygon(surface, GOLD, points)
    pygame.draw.polygon(surface, WHITE, points, 1)

    length = radius * (1.6 + 0.25 * math.sin(t * 3))

    for i in range(4):
        angle = i * math.pi / 2

        pygame.draw.aaline(
            surface,
            (255, 225, 150),
            (x, y),
            (
                x + length * math.cos(angle),
                y + length * math.sin(angle)
            )
        )


# ==================== 主程序 ====================

start_time = pygame.time.get_ticks() / 1000
fullscreen = False
running = True

while running:
    dt = min(clock.tick(60) / 1000, 0.05)
    t = pygame.time.get_ticks() / 1000 - start_time

    WIDTH, HEIGHT = screen.get_size()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

            elif event.key == pygame.K_SPACE:
                start_time = pygame.time.get_ticks() / 1000

            elif event.key == pygame.K_F11:
                fullscreen = not fullscreen

                if fullscreen:
                    screen = pygame.display.set_mode(
                        (0, 0), pygame.FULLSCREEN
                    )
                else:
                    screen = pygame.display.set_mode(
                        (1000, 800), pygame.RESIZABLE
                    )

    screen.fill((2, 3, 9))

    angle = t * 0.22

    # 星空闪烁
    for x, y, phase in stars:
        brightness = 0.2 + 0.3 * (
            1 + math.sin(t * 1.5 + phase)
        )

        glow(
            screen,
            x * WIDTH,
            y * HEIGHT,
            1,
            WHITE,
            brightness
        )

    # 粒子聚合动画
    progress = min(t / 4, 1)
    progress = 1 - (1 - progress) ** 3

    projected = []

    for p in particles:
        sx, sy, sz = p["start"]

        x = sx + (p["x"] - sx) * progress
        y = sy + (p["y"] - sy) * progress
        z = sz + (p["z"] - sz) * progress

        px, py, scale, depth = project(
            x, y, z, angle, WIDTH, HEIGHT
        )

        brightness = 0.72 + 0.28 * math.sin(
            t * 2.5 + p["phase"]
        )

        size = max(1, p["size"] * scale / 125)

        projected.append((
            depth,
            px,
            py,
            size,
            p["color"],
            brightness
        ))

    projected.sort(key=lambda p: p[0])

    for depth, x, y, size, color, brightness in projected:
        glow(screen, x, y, size, color, brightness)

    # 底部旋转光环
    if progress > 0.8:
        for ring in range(3):
            radius = 1.8 + ring * 0.22

            for i in range(160):
                a = i / 160 * math.tau + t * 0.4

                x = radius * math.cos(a)
                z = radius * math.sin(a)

                px, py, _, _ = project(
                    x,
                    -2.1 + ring * 0.025,
                    z,
                    angle,
                    WIDTH,
                    HEIGHT
                )

                brightness = (
                    0.4 + 0.35 * math.sin(a * 5 + t)
                )

                glow(screen, px, py, 1, GOLD, brightness)

    # 顶部金色五角星
    if t > 2:
        x, y, _, _ = project(
            0, 2.23, 0, angle, WIDTH, HEIGHT
        )

        radius = int(
            min(WIDTH, HEIGHT) * 0.027
        )

        draw_star(screen, x, y, radius, t)

    # 飘雪
    for flake in snow:
        flake[1] += flake[2] * dt
        flake[0] += math.sin(
            t + flake[1] * 10
        ) * dt * 0.015

        if flake[1] > 1:
            flake[1] = 0
            flake[0] = random.random()

        glow(
            screen,
            flake[0] * WIDTH,
            flake[1] * HEIGHT,
            flake[3],
            WHITE,
            0.65
        )

    # 圣诞祝福文字
    if t > 2.5:
        alpha = int(min((t - 2.5) / 2, 1) * 255)

        font = pygame.font.SysFont(
            "serif",
            max(24, int(HEIGHT * 0.067)),
            italic=True
        )

        title = font.render(
            "Merry Christmas",
            True,
            GOLD
        )

        title.set_alpha(alpha)

        screen.blit(
            title,
            title.get_rect(
                center=(WIDTH / 2, HEIGHT * 0.085)
            )
        )

        small_font = pygame.font.SysFont(
            "serif",
            max(12, int(HEIGHT * 0.022))
        )

        subtitle = small_font.render(
            "May all your wishes come true.",
            True,
            (220, 190, 130)
        )

        subtitle.set_alpha(alpha)

        screen.blit(
            subtitle,
            subtitle.get_rect(
                center=(WIDTH / 2, HEIGHT * 0.92)
            )
        )

    pygame.display.flip()

pygame.quit()
sys.exit()