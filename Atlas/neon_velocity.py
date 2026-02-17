import random
import sys
from dataclasses import dataclass

import pygame


WIDTH, HEIGHT = 800, 600
FPS = 60
LANES_Y = [180, 300, 420]
PLAYER_X = 120

NEON_CYAN = (0, 255, 255)
NEON_MAGENTA = (255, 0, 220)
NEON_BLUE = (40, 140, 255)
BG_COLOR = (8, 8, 18)
GRID_COLOR = (25, 35, 60)
WHITE = (240, 245, 255)


@dataclass
class Obstacle:
    x: float
    lane: int
    polarity: int
    speed: float
    size: int = 22

    @property
    def y(self):
        return LANES_Y[self.lane]

    @property
    def color(self):
        return NEON_CYAN if self.polarity == 0 else NEON_MAGENTA

    def update(self, dt):
        self.x -= self.speed * dt

    def draw(self, screen):
        points = [
            (self.x, self.y - self.size),
            (self.x + self.size, self.y),
            (self.x, self.y + self.size),
            (self.x - self.size, self.y),
        ]
        pygame.draw.polygon(screen, self.color, points)
        pygame.draw.polygon(screen, WHITE, points, 2)


class ParticleManager:
    def __init__(self):
        self.particles = []

    def emit_burst(self, pos, color, amount=20):
        for _ in range(amount):
            angle = random.uniform(0, 360)
            speed = random.uniform(80, 260)
            vel = pygame.Vector2(1, 0).rotate(angle) * speed
            self.particles.append(
                {
                    "pos": pygame.Vector2(pos),
                    "vel": vel,
                    "life": random.uniform(0.25, 0.7),
                    "max_life": 0.7,
                    "size": random.randint(2, 5),
                    "color": color,
                }
            )

    def update(self, dt):
        next_particles = []
        for p in self.particles:
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            p["vel"] *= 0.96
            p["pos"] += p["vel"] * dt
            next_particles.append(p)
        self.particles = next_particles

    def draw(self, screen):
        for p in self.particles:
            alpha = max(0.0, min(1.0, p["life"] / p["max_life"]))
            color = tuple(int(c * alpha) for c in p["color"])
            pygame.draw.circle(screen, color, p["pos"], p["size"])


class Player:
    def __init__(self):
        self.lane = 1
        self.polarity = 0
        self.radius = 20
        self.trail = []
        self.trail_max = 18

    @property
    def y(self):
        return LANES_Y[self.lane]

    @property
    def color(self):
        return NEON_CYAN if self.polarity == 0 else NEON_MAGENTA

    def move_up(self):
        self.lane = max(0, self.lane - 1)

    def move_down(self):
        self.lane = min(len(LANES_Y) - 1, self.lane + 1)

    def toggle_polarity(self):
        self.polarity = 1 - self.polarity

    def update(self):
        self.trail.append((PLAYER_X, self.y, self.color))
        if len(self.trail) > self.trail_max:
            self.trail.pop(0)

    def draw(self, screen):
        for i in range(1, len(self.trail)):
            x0, y0, c0 = self.trail[i - 1]
            x1, y1, _ = self.trail[i]
            alpha = i / len(self.trail)
            fade_color = tuple(int(channel * alpha * 0.6) for channel in c0)
            width = max(1, int(alpha * 6))
            pygame.draw.line(screen, fade_color, (x0, y0), (x1, y1), width)

        pygame.draw.circle(screen, self.color, (PLAYER_X, self.y), self.radius)
        pygame.draw.circle(screen, WHITE, (PLAYER_X, self.y), self.radius, 2)


class GameManager:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 24)
        self.big_font = pygame.font.SysFont("consolas", 48, bold=True)
        self.reset(full_reset=True)

    def reset(self, full_reset=False):
        self.player = Player()
        self.particles = ParticleManager()
        self.obstacles = []
        self.score = 0
        if full_reset:
            self.high_score = 0
        else:
            self.high_score = max(self.high_score, self.score)
        self.time_alive = 0.0
        self.base_speed = 260.0
        self.speed_ramp = 14.0
        self.spawn_timer = 0.0
        self.spawn_interval = 0.85
        self.grid_offset = 0.0
        self.game_over = False

    def restart(self):
        self.high_score = max(self.high_score, self.score)
        self.reset(full_reset=False)

    def spawn_obstacle(self):
        speed = self.base_speed + self.time_alive * self.speed_ramp
        self.obstacles.append(
            Obstacle(
                x=WIDTH + 40,
                lane=random.randint(0, 2),
                polarity=random.randint(0, 1),
                speed=speed,
            )
        )

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_w, pygame.K_UP) and not self.game_over:
                    self.player.move_up()
                elif event.key in (pygame.K_s, pygame.K_DOWN) and not self.game_over:
                    self.player.move_down()
                elif event.key == pygame.K_SPACE and not self.game_over:
                    self.player.toggle_polarity()
                elif event.key == pygame.K_r and self.game_over:
                    self.restart()

    def update(self, dt):
        if self.game_over:
            self.particles.update(dt)
            return

        self.time_alive += dt
        self.player.update()
        self.particles.update(dt)

        speed_now = self.base_speed + self.time_alive * self.speed_ramp
        self.grid_offset = (self.grid_offset + speed_now * dt) % 80

        self.spawn_timer -= dt
        current_spawn = max(0.30, self.spawn_interval - self.time_alive * 0.01)
        if self.spawn_timer <= 0:
            self.spawn_obstacle()
            self.spawn_timer = current_spawn

        active_obstacles = []
        player_pos = pygame.Vector2(PLAYER_X, self.player.y)

        for obstacle in self.obstacles:
            obstacle.speed = speed_now
            obstacle.update(dt)

            if obstacle.x < -60:
                continue

            obstacle_pos = pygame.Vector2(obstacle.x, obstacle.y)
            hit_dist = self.player.radius + obstacle.size * 0.75
            if obstacle.lane == self.player.lane and obstacle_pos.distance_to(player_pos) <= hit_dist:
                if obstacle.polarity == self.player.polarity:
                    self.score += 1
                    self.high_score = max(self.high_score, self.score)
                    self.particles.emit_burst(obstacle_pos, self.player.color, amount=24)
                    continue
                self.game_over = True
                self.particles.emit_burst(player_pos, (255, 80, 80), amount=30)
                continue

            active_obstacles.append(obstacle)

        self.obstacles = active_obstacles

    def draw_background(self):
        self.screen.fill(BG_COLOR)

        for lane_y in LANES_Y:
            pygame.draw.line(self.screen, (35, 35, 70), (0, lane_y), (WIDTH, lane_y), 2)

        spacing = 80
        start_x = -int(self.grid_offset)
        for x in range(start_x, WIDTH + spacing, spacing):
            pygame.draw.line(self.screen, GRID_COLOR, (x, 0), (x, HEIGHT), 1)

    def draw_ui(self):
        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        high_text = self.font.render(f"High: {self.high_score}", True, WHITE)
        controls_text = self.font.render("W/S or Up/Down: Lane | Space: Polarity", True, (180, 200, 255))

        self.screen.blit(score_text, (16, 12))
        self.screen.blit(high_text, (16, 40))
        self.screen.blit(controls_text, (16, HEIGHT - 34))

        if self.game_over:
            over_text = self.big_font.render("GAME OVER", True, (255, 90, 110))
            restart_text = self.font.render("Press R to restart", True, WHITE)
            self.screen.blit(over_text, over_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 25)))
            self.screen.blit(restart_text, restart_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30)))

    def draw(self):
        self.draw_background()

        for obstacle in self.obstacles:
            obstacle.draw(self.screen)

        self.player.draw(self.screen)
        self.particles.draw(self.screen)
        self.draw_ui()

        pygame.display.flip()

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()


def main():
    pygame.init()
    pygame.display.set_caption("Neon Velocity")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    manager = GameManager(screen)
    manager.run()


if __name__ == "__main__":
    main()
