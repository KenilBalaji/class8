import pygame
import random
import os
import sys
from collections import deque

# --------------- Config ---------------
TITLE = "NEON SNAKE - ARCADE"
CELL = 24
GRID_W, GRID_H = 24, 20              # 24x20 cells
BORDER = 32                          # pixels around playfield
W = GRID_W * CELL + BORDER * 2
H = GRID_H * CELL + BORDER * 2 + 80  # extra space for header
FPS = 60
START_LEN = 4
MOVE_DELAY_MS = 140                  # smaller = faster
MIN_DELAY_MS = 70
SPEEDUP_EVERY = 4                     # speed up every N fruit
GLOW_LAYERS = 40                       # how strong the glow looks
HS_FILE = "snake_highscore.txt"

# Colors (arcade neon)
BG = (8, 10, 20)
FG = (235, 247, 255)
NEON_GREEN = (0, 255, 180)
NEON_YELLOW = (255, 230, 80)
NEON_PINK = (255, 70, 150)
NEON_PURPLE = (170, 0, 220)
NEON_BLUE = (0, 200, 255)
GRID_COLOR = (24, 30, 50)
WALL_COLOR = (40, 50, 80)

# --------------- Helpers ---------------
def load_highscore():
    try:
        with open(HS_FILE, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 0

def save_highscore(v):
    try:
        with open(HS_FILE, "w") as f:
            f.write(str(int(v)))
    except Exception:
        pass

def clamp(n, a, b):
    return max(a, min(b, n))

# --------------- Game ---------------
class SnakeGame:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Consolas,JetBrainsMono,Menlo,monospace", 24)
        self.bigfont = pygame.font.SysFont("Consolas,JetBrainsMono,Menlo,monospace", 48, bold=True)

        # Scanline overlay
        self.scanlines = self.make_scanlines()

        # Glow surface for additive blit
        self.glow = pygame.Surface((W, H), pygame.SRCALPHA)

        # Sounds (optional; if mixer fails we keep going)
        self.pop_snd = None
        try:
            pygame.mixer.init()
            # Generate a tiny "pop" by building a short square wave (no numpy dependency)
            self.pop_snd = self.generate_pop_sound()
        except Exception:
            self.pop_snd = None

        self.reset()

    def grid_rect(self, gx, gy):
        return pygame.Rect(BORDER + gx * CELL, BORDER + 60 + gy * CELL, CELL, CELL)

    def reset(self):
        self.dir = (1, 0)
        self.next_dir = (1, 0)
        self.snake = deque()
        cx, cy = GRID_W // 3, GRID_H // 2
        for i in range(START_LEN, 0, -1):
            self.snake.append((cx - i, cy))
        self.spawn_food()
        self.alive = True
        self.score = 0
        self.highscore = load_highscore()
        self.move_delay = MOVE_DELAY_MS
        self.eaten_since_speedup = 0
        self.time_accum = 0
        self.paused = False
        self.flash_timer = 0

    def spawn_food(self):
        free = {(x, y) for x in range(GRID_W) for y in range(GRID_H)} - set(self.snake)
        self.food = random.choice(list(free)) if free else None

    def try_turn(self, dx, dy):
        # Disallow reversing directly
        if (-dx, -dy) != self.dir:
            self.next_dir = (dx, dy)

    def step(self):
        if not self.alive or self.paused or self.food is None:
            return
        self.dir = self.next_dir
        hx, hy = self.snake[-1]
        nx, ny = hx + self.dir[0], hy + self.dir[1]

        # Wall collision
        if nx < 0 or ny < 0 or nx >= GRID_W or ny >= GRID_H:
            self.game_over()
            return
        # Self collision
        if (nx, ny) in self.snake:
            self.game_over()
            return

        self.snake.append((nx, ny))
        if (nx, ny) == self.food:
            self.score += 1
            self.eaten_since_speedup += 1
            if self.pop_snd:
                self.pop_snd.play()
            self.spawn_food()
            # Speed up every few fruit
            if self.eaten_since_speedup >= SPEEDUP_EVERY:
                self.eaten_since_speedup = 0
                self.move_delay = max(MIN_DELAY_MS, self.move_delay - 6)
            self.flash_timer = 120
        else:
            self.snake.popleft()

    def game_over(self):
        self.alive = False
        if self.score > self.highscore:
            self.highscore = self.score
            save_highscore(self.highscore)

    # --------- Audio generation (tiny square "pop") ----------
    def generate_pop_sound(self):
        # Create a 100ms 440Hz square wave in a pygame Sound (16-bit mono)
        freq = 44100
        dur = 0.10
        frames = int(freq * dur)
        period = int(freq / 440)
        buf = bytearray()
        amp = 18000
        for i in range(frames):
            s = amp if (i % period) < period // 2 else -amp
            # little-endian signed 16-bit
            buf += (s & 0xFF).to_bytes(1, 'little', signed=False)
            buf += ((s >> 8) & 0xFF).to_bytes(1, 'little', signed=False)
        return pygame.mixer.Sound(buffer=bytes(buf))

    # --------- Visual helpers ----------
    def make_scanlines(self):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.set_alpha(70)
        for y in range(0, H, 4):
            pygame.draw.line(s, (0, 0, 0, 140), (0, y), (W, y))
        return s

    def draw_bezel(self):
        # Outer border & title plate
        pygame.draw.rect(self.screen, WALL_COLOR, (16, 16, W - 32, H - 32), border_radius=18)
        pygame.draw.rect(self.screen, (18, 22, 36), (BORDER - 8, BORDER + 40, GRID_W * CELL + 16, GRID_H * CELL + 16), border_radius=14)
        # Header bar
        pygame.draw.rect(self.screen, (18, 22, 36), (BORDER - 8, BORDER - 8, GRID_W * CELL + 16, 64), border_radius=14)

    def draw_grid(self):
        play = pygame.Rect(BORDER, BORDER + 60, GRID_W * CELL, GRID_H * CELL)
        pygame.draw.rect(self.screen, (10, 12, 22), play)
        # subtle grid
        for x in range(GRID_W + 1):
            pygame.draw.line(self.screen, GRID_COLOR,
                             (BORDER + x * CELL, BORDER + 60),
                             (BORDER + x * CELL, BORDER + 60 + GRID_H * CELL))
        for y in range(GRID_H + 1):
            pygame.draw.line(self.screen, GRID_COLOR,
                             (BORDER, BORDER + 60 + y * CELL),
                             (BORDER + GRID_W * CELL, BORDER + 60 + y * CELL))
        # frame
        pygame.draw.rect(self.screen, (60, 70, 110), play, width=2)

    def draw_glow_rect(self, rect, color, radius=8):
        # Draw multiple expanded rounded rects to fake a neon glow
        for i in range(GLOW_LAYERS, 0, -1):
            alpha = int(35 * i)
            grow = i * 2
            r = pygame.Rect(rect.x - grow, rect.y - grow, rect.w + grow * 2, rect.h + grow * 2)
            pygame.draw.rect(self.glow, (*color, alpha), r, border_radius=radius + i)

        pygame.draw.rect(self.screen, color, rect, border_radius=radius)

    def draw_snake(self):
        body_color = NEON_GREEN
        head_color = NEON_YELLOW
        # Body
        for i, (x, y) in enumerate(list(self.snake)[:-1]):
            r = self.grid_rect(x, y).inflate(-6, -6)
            self.draw_glow_rect(r, body_color, radius=7)

        # Head (brighter)
        hx, hy = self.snake[-1]
        r = self.grid_rect(hx, hy).inflate(-4, -4)
        self.draw_glow_rect(r, head_color, radius=8)

        # Eyes
        dirx, diry = self.dir
        center = r.center
        ex = center[0] + dirx * 4 - diry * 6
        ey = center[1] + diry * 4 - dirx * 6
        pygame.draw.circle(self.screen, BG, (ex, ey), 3)
        pygame.draw.circle(self.screen, BG, (ex - diry * 6, ey - dirx * 6), 3)

    def draw_food(self):
        if self.food is None:
            return
        fx, fy = self.food
        r = self.grid_rect(fx, fy).inflate(-8, -8)
        self.draw_glow_rect(r, NEON_PINK, radius=10)
        # sparkle
        cx, cy = r.center
        pygame.draw.line(self.screen, NEON_PINK, (cx - 6, cy), (cx + 6, cy), 2)
        pygame.draw.line(self.screen, NEON_PINK, (cx, cy - 6), (cx, cy + 6), 2)

    def draw_header(self):
        # Title
        title = self.bigfont.render("NEON SNAKE", True, NEON_BLUE)
        self.screen.blit(title, (BORDER, BORDER - 4))

        # Scores
        score_txt = self.font.render(f"SCORE: {self.score}", True, FG)
        hs_txt = self.font.render(f"HIGHSCORE: {self.highscore}", True, FG)
        speed = 1000 // self.move_delay
        spd_txt = self.font.render(f"SPEED: {speed}", True, FG)
        self.screen.blit(score_txt, (BORDER, BORDER + 28))
        self.screen.blit(hs_txt, (W - BORDER - hs_txt.get_width(), BORDER + 28))
        self.screen.blit(spd_txt, (W // 2 - spd_txt.get_width() // 2, BORDER + 28))

    def draw_pause_or_gameover(self):
        if self.paused:
            t = self.bigfont.render("PAUSED", True, NEON_PURPLE)
            tip = self.font.render("Press P to resume", True, FG)
            self.screen.blit(t, t.get_rect(center=(W // 2, BORDER + 60 + GRID_H * CELL // 2 - 24)))
            self.screen.blit(tip, tip.get_rect(center=(W // 2, BORDER + 60 + GRID_H * CELL // 2 + 18)))
        elif not self.alive:
            t = self.bigfont.render("GAME OVER", True, NEON_PINK)
            tip = self.font.render("Press SPACE or R to restart", True, FG)
            self.screen.blit(t, t.get_rect(center=(W // 2, BORDER + 60 + GRID_H * CELL // 2 - 24)))
            self.screen.blit(tip, tip.get_rect(center=(W // 2, BORDER + 60 + GRID_H * CELL // 2 + 18)))

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif e.key in (pygame.K_UP, pygame.K_w):
                        self.try_turn(0, -1)
                    elif e.key in (pygame.K_DOWN, pygame.K_s):
                        self.try_turn(0, 1)
                    elif e.key in (pygame.K_LEFT, pygame.K_a):
                        self.try_turn(-1, 0)
                    elif e.key in (pygame.K_RIGHT, pygame.K_d):
                        self.try_turn(1, 0)
                    elif e.key == pygame.K_p:
                        if self.alive:
                            self.paused = not self.paused
                    elif e.key in (pygame.K_r, pygame.K_SPACE):
                        if not self.alive:
                            self.reset()

            if self.alive and not self.paused:
                self.time_accum += dt
                while self.time_accum >= self.move_delay:
                    self.time_accum -= self.move_delay
                    self.step()

            # Draw
            self.screen.fill(BG)
            self.draw_bezel()
            self.draw_grid()

            # Glow layer reset
            self.glow.fill((0, 0, 0, 0))

            if self.flash_timer > 0:
                self.flash_timer -= dt
                # brief white flash on the playfield after eating
                overlay = pygame.Surface((GRID_W * CELL, GRID_H * CELL), pygame.SRCALPHA)
                a = clamp(self.flash_timer, 0, 120) * 1.2
                overlay.fill((255, 255, 255, int(a)))
                self.screen.blit(overlay, (BORDER, BORDER + 60), special_flags=pygame.BLEND_ADD)

            self.draw_food()
            self.draw_snake()

            # Additive glow on top
            self.screen.blit(self.glow, (0, 0), special_flags=pygame.BLEND_ADD)

            self.draw_header()
            self.draw_pause_or_gameover()

            # Scanlines & slight vignette
            self.screen.blit(self.scanlines, (0, 0))
            self.draw_vignette()

            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def draw_vignette(self):
        # subtle dark corners (radial falloff)
        vignette = pygame.Surface((W, H), pygame.SRCALPHA)
        cx, cy = W / 2, H / 2
        maxd = (cx ** 2 + cy ** 2) ** 0.5
        # draw 8 translucent circles to fake a radial gradient
        for i in range(8):
            r = int(max(W, H) * (0.55 + i * 0.07))
            a = 18 + i * 6
            pygame.draw.circle(vignette, (0, 0, 0, a), (int(cx), int(cy)), r)
        self.screen.blit(vignette, (0, 0))

# --------------- Main ---------------

if __name__ == "__main__":
    SnakeGame().run()
