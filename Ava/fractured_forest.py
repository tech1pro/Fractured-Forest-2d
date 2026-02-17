import math
import random
import sys
from dataclasses import dataclass

import pygame


WIDTH, HEIGHT = 960, 540
FPS = 60
ROOM_COUNT = 5
GROUND_Y = HEIGHT - 42

SEASON_ORDER = ["Spring", "Summer", "Autumn", "Winter"]
SEASON_COLORS = {
    "Spring": (114, 201, 120),
    "Summer": (245, 191, 78),
    "Autumn": (225, 122, 57),
    "Winter": (149, 190, 255),
}


@dataclass
class EchoSeed:
    name: str
    description: str


class SeasonManager:
    def __init__(self, cooldown_ms: int = 500):
        self.current_index = 0
        self.cooldown_ms = cooldown_ms
        self.last_cycle_ms = -cooldown_ms
        self.flash_alpha = 0

    @property
    def current(self) -> str:
        return SEASON_ORDER[self.current_index]

    def can_cycle(self, now_ms: int) -> bool:
        return now_ms - self.last_cycle_ms >= self.cooldown_ms

    def cycle(self, now_ms: int) -> bool:
        if not self.can_cycle(now_ms):
            return False
        self.current_index = (self.current_index + 1) % len(SEASON_ORDER)
        self.last_cycle_ms = now_ms
        self.flash_alpha = 170
        return True

    def update(self):
        if self.flash_alpha > 0:
            self.flash_alpha = max(0, self.flash_alpha - 8)


class RoomChunk:
    def __init__(self, template: dict):
        self.template = template
        self.base_platforms = [pygame.Rect(*p) for p in template.get("platforms", [])]
        self.seasonal_platforms = [
            {"rect": pygame.Rect(*item["rect"]), "seasons": set(item["seasons"]), "kind": item["kind"]}
            for item in template.get("seasonal_platforms", [])
        ]
        self.hazards = [pygame.Rect(*h) for h in template.get("hazards", [])]
        self.water = [pygame.Rect(*w) for w in template.get("water", [])]
        self.wind = [pygame.Rect(*w) for w in template.get("wind", [])]
        self.exit_zone = pygame.Rect(*template["exit"])

    def active_platforms(self, season: str):
        active = list(self.base_platforms)
        for entry in self.seasonal_platforms:
            if season in entry["seasons"]:
                active.append(entry["rect"])
        if season == "Winter":
            active.extend(self.water)
        return active

    def hazard_active(self, season: str, brittle_thorns: bool):
        if season in {"Summer", "Autumn"}:
            return True
        if season == "Spring" and brittle_thorns:
            return True
        return False


class Player:
    def __init__(self, x: int, y: int):
        self.rect = pygame.Rect(x, y, 34, 52)
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.on_ground = False

        self.base_speed = 4.8
        self.base_jump = 12.5
        self.base_gravity = 0.58
        self.max_fall = 15.0

    def reset(self, x: int, y: int):
        self.rect.x = x
        self.rect.y = y
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.on_ground = False

    def update(self, keys, room: RoomChunk, season: str, modifiers: dict):
        speed = self.base_speed * modifiers.get("speed_mult", 1.0)
        gravity = self.base_gravity * modifiers.get("gravity_mult", 1.0)
        jump_power = self.base_jump * modifiers.get("jump_mult", 1.0)

        direction = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            direction -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            direction += 1

        self.vel_x = direction * speed

        in_water = any(self.rect.colliderect(w) for w in room.water)
        if in_water and season in {"Spring", "Summer"}:
            slow_mult = modifiers.get("water_drag_mult", 1.0)
            self.vel_x *= 0.45 * slow_mult

        if season == "Autumn":
            for zone in room.wind:
                if self.rect.colliderect(zone):
                    self.vel_x += modifiers.get("wind_push", 0.25)

        self.vel_y = min(self.vel_y + gravity, self.max_fall)

        self.rect.x += round(self.vel_x)
        for platform in room.active_platforms(season):
            if self.rect.colliderect(platform):
                if self.vel_x > 0:
                    self.rect.right = platform.left
                elif self.vel_x < 0:
                    self.rect.left = platform.right

        self.rect.y += round(self.vel_y)
        self.on_ground = False
        for platform in room.active_platforms(season):
            if self.rect.colliderect(platform):
                if self.vel_y > 0:
                    self.rect.bottom = platform.top
                    self.vel_y = 0
                    self.on_ground = True
                elif self.vel_y < 0:
                    self.rect.top = platform.bottom
                    self.vel_y = 0

        if in_water and season == "Winter":
            slip = modifiers.get("ice_slip", 1.0)
            self.vel_x *= 0.985 * slip

        self.rect.clamp_ip(pygame.Rect(0, -200, WIDTH, HEIGHT + 300))
        return jump_power


class GameManager:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Fractured Forest: Echo of Seasons")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.big_font = pygame.font.Font(None, 66)

        self.room_templates = self._build_templates()
        self.echo_pool = [
            EchoSeed("Swiftstride", "+20% movement speed."),
            EchoSeed("Moonlight Bones", "Lower gravity, slightly higher jump."),
            EchoSeed("Brittle Thorns", "Spring thorns are now dangerous."),
            EchoSeed("Glacial Rhythm", "Season cycle cooldown increased."),
            EchoSeed("Heavy Bloom", "Spring/Summer water slows you more."),
            EchoSeed("Tailwind", "Autumn wind pushes harder."),
        ]

        self.state = "playing"
        self.start_time_ms = 0
        self.end_time_ms = 0
        self.room_index = 0
        self.rooms = []
        self.current_room = None
        self.season_manager = SeasonManager()
        self.player = Player(50, 400)
        self.particles = []
        self.selected_seeds = []
        self.modifiers = {}
        self.restart_run()

    def _build_templates(self):
        return [
            {
                "platforms": [(0, GROUND_Y, WIDTH, 50), (190, 430, 170, 20), (450, 360, 180, 20)],
                "seasonal_platforms": [
                    {"rect": (330, 300, 130, 16), "seasons": ["Spring", "Autumn"], "kind": "vine"},
                    {"rect": (690, 270, 170, 16), "seasons": ["Winter"], "kind": "ice"},
                ],
                "hazards": [(560, GROUND_Y - 18, 130, 18)],
                "water": [(95, GROUND_Y - 18, 180, 18)],
                "wind": [(640, 210, 200, 220)],
                "exit": (900, GROUND_Y - 70, 44, 70),
            },
            {
                "platforms": [(0, GROUND_Y, WIDTH, 50), (160, 390, 120, 20), (350, 330, 140, 20), (560, 285, 120, 20)],
                "seasonal_platforms": [
                    {"rect": (285, 445, 110, 16), "seasons": ["Winter"], "kind": "ice"},
                    {"rect": (725, 250, 145, 16), "seasons": ["Spring", "Autumn"], "kind": "vine"},
                ],
                "hazards": [(380, GROUND_Y - 18, 120, 18)],
                "water": [(640, GROUND_Y - 20, 210, 20)],
                "wind": [(95, 220, 180, 230)],
                "exit": (902, 180, 40, 68),
            },
            {
                "platforms": [(0, GROUND_Y, WIDTH, 50), (105, 455, 160, 20), (360, 415, 160, 20), (620, 360, 150, 20)],
                "seasonal_platforms": [
                    {"rect": (500, 300, 130, 16), "seasons": ["Spring", "Autumn"], "kind": "vine"},
                    {"rect": (260, 310, 130, 16), "seasons": ["Winter"], "kind": "ice"},
                ],
                "hazards": [(140, GROUND_Y - 16, 135, 16), (810, GROUND_Y - 16, 90, 16)],
                "water": [(430, GROUND_Y - 18, 200, 18)],
                "wind": [(700, 210, 160, 210)],
                "exit": (34, 380, 38, 70),
            },
        ]

    def restart_run(self):
        self.state = "playing"
        self.start_time_ms = pygame.time.get_ticks()
        self.end_time_ms = 0
        self.room_index = 0
        self.rooms = [RoomChunk(random.choice(self.room_templates)) for _ in range(ROOM_COUNT)]
        self.current_room = self.rooms[0]
        self.selected_seeds = random.sample(self.echo_pool, 2)
        self.modifiers = self._seeds_to_modifiers(self.selected_seeds)
        cooldown = 800 if self.modifiers.get("slow_cycle") else 500
        self.season_manager = SeasonManager(cooldown_ms=cooldown)
        self.player.reset(70, 420)
        self.particles.clear()

    def _seeds_to_modifiers(self, seeds):
        mods = {
            "speed_mult": 1.0,
            "gravity_mult": 1.0,
            "jump_mult": 1.0,
            "water_drag_mult": 1.0,
            "wind_push": 0.24,
            "ice_slip": 1.0,
            "brittle_thorns": False,
            "slow_cycle": False,
        }
        for seed in seeds:
            if seed.name == "Swiftstride":
                mods["speed_mult"] *= 1.2
            elif seed.name == "Moonlight Bones":
                mods["gravity_mult"] *= 0.82
                mods["jump_mult"] *= 1.08
            elif seed.name == "Brittle Thorns":
                mods["brittle_thorns"] = True
            elif seed.name == "Glacial Rhythm":
                mods["slow_cycle"] = True
            elif seed.name == "Heavy Bloom":
                mods["water_drag_mult"] *= 0.75
            elif seed.name == "Tailwind":
                mods["wind_push"] = 0.45
        return mods

    def spawn_particle(self):
        season = self.season_manager.current
        if len(self.particles) > 140:
            return
        if random.random() > 0.45:
            return

        if season == "Spring":
            color = (229, 238, 152)
            size = random.randint(2, 4)
        elif season == "Autumn":
            color = (233, 143, 66)
            size = random.randint(3, 5)
        elif season == "Winter":
            color = (230, 240, 255)
            size = random.randint(2, 3)
        else:
            color = (255, 233, 190)
            size = random.randint(2, 3)

        self.particles.append(
            {
                "x": random.uniform(0, WIDTH),
                "y": random.uniform(-20, HEIGHT),
                "vx": random.uniform(-0.35, 0.35),
                "vy": random.uniform(0.25, 1.05),
                "life": random.randint(100, 250),
                "size": size,
                "color": color,
            }
        )

    def update_particles(self):
        for particle in self.particles:
            particle["x"] += particle["vx"]
            particle["y"] += particle["vy"]
            particle["life"] -= 1
            if self.season_manager.current == "Autumn":
                particle["x"] += math.sin(particle["y"] * 0.05) * 0.3
        self.particles = [
            p for p in self.particles if p["life"] > 0 and -30 <= p["x"] <= WIDTH + 30 and p["y"] <= HEIGHT + 30
        ]

    def advance_room(self):
        self.room_index += 1
        if self.room_index >= len(self.rooms):
            self.state = "won"
            self.end_time_ms = pygame.time.get_ticks()
            return
        self.current_room = self.rooms[self.room_index]
        self.player.reset(70, 420)

    def fail_run(self):
        if self.state == "playing":
            self.state = "failed"
            self.end_time_ms = pygame.time.get_ticks()

    def _handle_gameplay_input(self, event, now_ms):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q:
                self.season_manager.cycle(now_ms)
            elif event.key == pygame.K_SPACE and self.player.on_ground:
                jump_power = self.player.base_jump * self.modifiers.get("jump_mult", 1.0)
                self.player.vel_y = -jump_power

    def _update_gameplay(self):
        keys = pygame.key.get_pressed()
        self.player.update(keys, self.current_room, self.season_manager.current, self.modifiers)

        hazard_on = self.current_room.hazard_active(self.season_manager.current, self.modifiers.get("brittle_thorns", False))
        if hazard_on:
            for hazard in self.current_room.hazards:
                if self.player.rect.colliderect(hazard):
                    self.fail_run()
                    return

        if self.player.rect.top > HEIGHT + 80:
            self.fail_run()
            return

        if self.player.rect.colliderect(self.current_room.exit_zone):
            self.advance_room()

        self.spawn_particle()
        self.update_particles()
        self.season_manager.update()

    def draw_room(self):
        season = self.season_manager.current
        base = {
            "Spring": (24, 45, 34),
            "Summer": (52, 55, 22),
            "Autumn": (55, 34, 24),
            "Winter": (25, 34, 56),
        }[season]
        self.screen.fill(base)

        for particle in self.particles:
            pygame.draw.circle(self.screen, particle["color"], (int(particle["x"]), int(particle["y"])), particle["size"])

        for water in self.current_room.water:
            if season == "Winter":
                pygame.draw.rect(self.screen, (194, 240, 255), water)
                pygame.draw.rect(self.screen, (230, 248, 255), water, 2)
            elif season in {"Spring", "Summer"}:
                pygame.draw.rect(self.screen, (72, 138, 202), water)
            else:
                pygame.draw.rect(self.screen, (85, 120, 155), water)

        hazard_active = self.current_room.hazard_active(season, self.modifiers.get("brittle_thorns", False))
        for hazard in self.current_room.hazards:
            color = (192, 58, 46) if hazard_active else (116, 112, 118)
            pygame.draw.rect(self.screen, color, hazard)
            if hazard_active:
                for x in range(hazard.left, hazard.right, 14):
                    tip = [(x, hazard.bottom), (x + 7, hazard.top), (x + 14, hazard.bottom)]
                    pygame.draw.polygon(self.screen, (240, 196, 177), tip)

        for zone in self.current_room.wind:
            if season == "Autumn":
                s = pygame.Surface((zone.width, zone.height), pygame.SRCALPHA)
                s.fill((230, 134, 64, 50))
                self.screen.blit(s, zone.topleft)

        for platform in self.current_room.base_platforms:
            pygame.draw.rect(self.screen, (80, 68, 50), platform)

        for seasonal in self.current_room.seasonal_platforms:
            if season in seasonal["seasons"]:
                color = (99, 179, 88) if seasonal["kind"] == "vine" else (189, 223, 255)
                pygame.draw.rect(self.screen, color, seasonal["rect"])
                pygame.draw.rect(self.screen, (32, 40, 50), seasonal["rect"], 2)

        pygame.draw.rect(self.screen, (240, 246, 154), self.current_room.exit_zone)
        pygame.draw.rect(self.screen, (50, 60, 64), self.current_room.exit_zone, 2)

        pygame.draw.rect(self.screen, (220, 220, 235), self.player.rect, border_radius=6)
        pygame.draw.rect(self.screen, (40, 40, 55), self.player.rect, 2, border_radius=6)

        if self.season_manager.flash_alpha > 0:
            flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            flash.fill((*SEASON_COLORS[season], self.season_manager.flash_alpha))
            self.screen.blit(flash, (0, 0))

    def draw_ui(self):
        season = self.season_manager.current
        pygame.draw.rect(self.screen, (20, 20, 26), (16, 12, 440, 94), border_radius=8)
        pygame.draw.circle(self.screen, SEASON_COLORS[season], (36, 36), 10)

        season_txt = self.font.render(f"Season: {season}", True, (240, 240, 246))
        room_txt = self.font.render(f"Room: {self.room_index + 1}/{len(self.rooms)}", True, (240, 240, 246))
        cooldown_left = max(0, (self.season_manager.cooldown_ms - (pygame.time.get_ticks() - self.season_manager.last_cycle_ms)) / 1000)
        cd_txt = self.font.render(f"Q Cooldown: {cooldown_left:.2f}s", True, (210, 210, 220))
        self.screen.blit(season_txt, (56, 24))
        self.screen.blit(room_txt, (56, 50))
        self.screen.blit(cd_txt, (230, 24))

        seed_names = ", ".join(seed.name for seed in self.selected_seeds)
        seed_txt = self.font.render(f"Echo Seeds: {seed_names}", True, (242, 235, 214))
        self.screen.blit(seed_txt, (20, 114))

    def draw_end_screen(self):
        elapsed_ms = self.end_time_ms - self.start_time_ms
        elapsed_s = elapsed_ms / 1000.0
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        title = "Run Complete" if self.state == "won" else "Run Failed"
        title_color = (160, 245, 176) if self.state == "won" else (245, 126, 126)
        t_surface = self.big_font.render(title, True, title_color)
        s_surface = self.font.render(f"Rooms cleared: {self.room_index}/{len(self.rooms)}", True, (242, 242, 242))
        time_surface = self.font.render(f"Time: {elapsed_s:.2f}s", True, (242, 242, 242))
        r_surface = self.font.render("Press R to restart run", True, (245, 245, 199))

        self.screen.blit(t_surface, (WIDTH // 2 - t_surface.get_width() // 2, 190))
        self.screen.blit(s_surface, (WIDTH // 2 - s_surface.get_width() // 2, 268))
        self.screen.blit(time_surface, (WIDTH // 2 - time_surface.get_width() // 2, 302))
        self.screen.blit(r_surface, (WIDTH // 2 - r_surface.get_width() // 2, 350))

    def run(self):
        while True:
            now_ms = pygame.time.get_ticks()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)

                if event.type == pygame.KEYDOWN and event.key == pygame.K_r and self.state in {"won", "failed"}:
                    self.restart_run()

                if self.state == "playing":
                    self._handle_gameplay_input(event, now_ms)

            if self.state == "playing":
                self._update_gameplay()

            self.draw_room()
            self.draw_ui()
            if self.state in {"won", "failed"}:
                self.draw_end_screen()

            pygame.display.flip()
            self.clock.tick(FPS)


def main():
    GameManager().run()


if __name__ == "__main__":
    main()
