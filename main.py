"""
DRONE FLIGHT TRAINING SIMULATOR  -  Robodrone Challenge
=======================================================
Python + Ursina (Panda3D).  Whole simulator lives in this one file:

    1. settings & helpers
    2. world  (ground, walls, buildings, pads, rings)
    3. drone  (model + flight state)
    4. physics (fixed 120 Hz step: motors, battery, drag, wind, collisions)
    5. HUD, minimap, cameras
    6. input + main loop

Ursina conventions used everywhere below (verified against the engine):
    rotation_x  +  = nose DOWN  (drone accelerates forward)
    rotation_z  +  = roll RIGHT (drone accelerates to the right)
    rotation_y  +  = yaw RIGHT  (clockwise seen from above)
"""

import math
import random

from ursina import *

# ============================================================
# APP / WINDOW
# ============================================================


def rgb(r, g, b, a=255):
    """0-255 colour helper that works on old and new Ursina versions."""
    try:
        return color.rgba32(r, g, b, a)
    except AttributeError:
        return color.rgba(r, g, b, a)


SKY_COLOR = rgb(120, 170, 190)

app = Ursina()

window.title = "Drone Flight Training Simulator"
window.borderless = False
window.fullscreen = False
window.color = SKY_COLOR

for _name in ("exit_button", "cog_button", "entity_counter", "collider_counter"):
    try:
        getattr(window, _name).enabled = False
    except Exception:
        pass

# ============================================================
# SETTINGS
# ============================================================

GRAVITY = 9.81
MASS = 1.5
MAX_THRUST = MASS * GRAVITY * 2.0     # 100 % throttle = 2 x weight
HOVER_THROTTLE = 0.50                 # 50 % throttle = hover

DRAG = 0.35                           # linear air drag
DRAG2 = 0.06                          # quadratic air drag
MAX_SPEED = 30.0

MAX_TILT = 35.0                       # ANGLE mode limit (deg)
ATT_TAU = 0.10                        # attitude response time (s)
ATT_RATE_LIMIT = 260.0                # deg/s
YAW_SPEED = 80.0                      # deg/s
ACRO_RATE = 140.0                     # deg/s (ACRO pitch / roll)
ACRO_YAW = 120.0

MOTOR_TAU = 0.07                      # motor spool-up time constant (s)
THROTTLE_RATE = 0.35                  # throttle change per second
ALT_CLIMB = 3.0                       # m/s in altitude-hold mode

GROUND_Y = 0.0
GEAR = 0.30                           # landing-gear height under drone centre
BODY_R = 0.95                         # collision radius
CRASH_VERTICAL_SPEED = 4.5            # m/s
CRASH_TILT_ANGLE = 15.0               # deg
CRASH_SIDE_SPEED = 7.0                # m/s sliding on touchdown
WALL_CRASH_SPEED = 2.5                # m/s into a wall

WORLD_SIZE = 100
MAX_ALT = 60.0
STEP = 1.0 / 120.0                    # fixed physics step

BATTERY_IDLE_DRAIN = 0.10             # % per second
BATTERY_LOAD_DRAIN = 0.35             # extra % per second at full load

WIND_BASE = 3.5
WIND_DIR = 35.0                       # degrees, direction wind blows TOWARD

RING_SIZE = 5.0
RING_HOLE = 1.9                       # allowed offset from ring centre
RING_POINTS = 25
MISSION_BONUS = 100

PAD_HEIGHT = 0.16

MODE_NAMES = ("ANGLE", "ACRO")
CAMERA_NAMES = ("CHASE", "FPV", "TOP")
FPV_UPTILT = 10.0                     # camera tilt-up on the FPV view (deg)


def dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z


def distance_xz(a, b):
    return math.sqrt((a.x - b.x) ** 2 + (a.z - b.z) ** 2)


def approach(value, target, max_delta):
    if value < target:
        return min(target, value + max_delta)
    return max(target, value - max_delta)


def up_vector(pitch, yaw, roll):
    """Drone's body-up direction in world space (matches Ursina's HPR order)."""
    p, y, r = math.radians(pitch), math.radians(yaw), math.radians(roll)
    x0, y0 = math.sin(r), math.cos(r)
    y1, z1 = y0 * math.cos(p), y0 * math.sin(p)
    return Vec3(
        x0 * math.cos(y) + z1 * math.sin(y),
        y1,
        -x0 * math.sin(y) + z1 * math.cos(y),
    )


def sign(v):
    return -1.0 if v < 0 else 1.0


# ============================================================
# WORLD
# ============================================================

try:
    scene.fog_color = SKY_COLOR
    scene.fog_density = (70, 190)
except Exception:
    pass

Sky()

ground = Entity(
    model="cube",
    scale=(WORLD_SIZE, 0.2, WORLD_SIZE),
    position=(0, -0.1, 0),
    color=rgb(70, 110, 70),
    texture="white_cube",
    texture_scale=(WORLD_SIZE / 4, WORLD_SIZE / 4),
    collider="box",
)

# Boundary walls (also enforced in physics)
for _pos, _scale in (
    ((0, 2.5, WORLD_SIZE / 2), (WORLD_SIZE, 5, 0.5)),
    ((0, 2.5, -WORLD_SIZE / 2), (WORLD_SIZE, 5, 0.5)),
    ((WORLD_SIZE / 2, 2.5, 0), (0.5, 5, WORLD_SIZE)),
    ((-WORLD_SIZE / 2, 2.5, 0), (0.5, 5, WORLD_SIZE)),
):
    Entity(model="cube", scale=_scale, position=_pos, color=rgb(90, 90, 90))

# ---------------- landing pads ----------------


class Pad:
    def __init__(self, name, x, z, points, col):
        self.name = name
        self.x, self.z = x, z
        self.half = 3.0
        self.top = PAD_HEIGHT
        self.points = points
        self.position = Vec3(x, PAD_HEIGHT / 2, z)
        self.color = col


PADS = [
    Pad("HOME", 0, 0, 100, color.green),
    Pad("PAD B", 20, 20, 150, color.yellow),
]


def build_pad(pad):
    root = Entity(position=(pad.x, 0, pad.z))
    Entity(parent=root, model="cube", scale=(6, PAD_HEIGHT, 6),
           position=(0, PAD_HEIGHT / 2, 0), color=pad.color)
    top = PAD_HEIGHT + 0.01
    white = color.white
    # "H" style marking + border
    Entity(parent=root, model="cube", scale=(0.3, 0.02, 2.4), position=(-0.9, top, 0), color=white)
    Entity(parent=root, model="cube", scale=(0.3, 0.02, 2.4), position=(0.9, top, 0), color=white)
    Entity(parent=root, model="cube", scale=(1.5, 0.02, 0.3), position=(0, top, 0), color=white)
    for sx, sz, w, d in ((0, 2.75, 5.6, 0.2), (0, -2.75, 5.6, 0.2),
                         (2.75, 0, 0.2, 5.6), (-2.75, 0, 0.2, 5.6)):
        Entity(parent=root, model="cube", scale=(w, 0.02, d), position=(sx, top, sz), color=white)
    Text(text=pad.name, parent=scene, position=(pad.x, 3.2, pad.z), billboard=True,
         scale=30, origin=(0, 0), color=color.white)


for _pad in PADS:
    build_pad(_pad)

# ---------------- practice rings ----------------

RING_POSITIONS = [
    (-12, 5, 0),
    (-20, 7, 5),
    (-28, 9, 10),
    (-20, 11, 20),
    (-5, 13, 25),
    (10, 10, 28),
    (22, 8, 25),
    (30, 6, 20),
]

RING_IDLE = rgb(230, 120, 20)
RING_NEXT = rgb(255, 220, 40)
RING_DONE = rgb(70, 210, 100)


class Ring:
    def __init__(self, index, pos, yaw):
        self.index = index
        self.pos = Vec3(*pos)
        self.yaw = yaw
        yr = math.radians(yaw)
        self.normal = Vec3(math.sin(yr), 0, math.cos(yr))
        self.right = Vec3(math.cos(yr), 0, -math.sin(yr))
        self.passed = False
        self.parts = []
        self.root = Entity(position=self.pos, rotation=(0, yaw, 0))
        t, s = 0.22, RING_SIZE
        for scale, position in (
            ((s, t, t), (0, s / 2, 0)), ((s, t, t), (0, -s / 2, 0)),
            ((t, s, t), (-s / 2, 0, 0)), ((t, s, t), (s / 2, 0, 0)),
        ):
            self.parts.append(Entity(parent=self.root, model="cube",
                                     scale=scale, position=position, color=RING_IDLE))
        Text(text=str(index + 1), parent=scene, position=self.pos + Vec3(0, s / 2 + 1.2, 0),
             billboard=True, scale=30, origin=(0, 0), color=color.orange)

    def set_color(self, col):
        for part in self.parts:
            part.color = col


rings = []
for _i, _p in enumerate(RING_POSITIONS):
    _a = Vec3(*_p)
    if _i < len(RING_POSITIONS) - 1:
        _b = Vec3(*RING_POSITIONS[_i + 1])
        _d = _b - _a
    else:
        _b = Vec3(*RING_POSITIONS[_i - 1])
        _d = _a - _b
    rings.append(Ring(_i, _p, math.degrees(math.atan2(_d.x, _d.z))))

# ---------------- buildings ----------------


class Box:
    """Axis-aligned building footprint used by the physics."""

    def __init__(self, cx, cz, hx, hz, top):
        self.cx, self.cz, self.hx, self.hz, self.top = cx, cz, hx, hz, top


def near_box(x, z, hw, hd, px, pz, margin):
    return abs(x - px) < hw + margin and abs(z - pz) < hd + margin


boxes = []
buildings = []

random.seed(42)
attempts = 0
while len(boxes) < 30 and attempts < 1500:
    attempts += 1
    x = random.uniform(-42, 42)
    z = random.uniform(-42, 42)
    width = random.uniform(3, 7)
    depth = random.uniform(3, 7)
    height = random.uniform(4, 15)
    hw, hd = width / 2, depth / 2

    blocked = False
    for px, pz in ((0, 0), (20, 20), (-10, -10), (0, -15), (15, -5)):
        if near_box(x, z, hw, hd, px, pz, 6):
            blocked = True
    for r in rings:                       # keep every ring gate clear
        if near_box(x, z, hw, hd, r.pos.x, r.pos.z, 5):
            blocked = True
    for b in boxes:                       # no overlapping buildings
        if (abs(x - b.cx) < hw + b.hx + 3 and abs(z - b.cz) < hd + b.hz + 3):
            blocked = True
    if blocked:
        continue

    boxes.append(Box(x, z, hw, hd, height))
    base = (random.randint(80, 150), random.randint(80, 150), random.randint(90, 170))
    buildings.append(Entity(
        model="cube",
        position=(x, height / 2, z),
        scale=(width, height, depth),
        color=rgb(*base),
        collider="box",
    ))
    band_col = rgb(int(base[0] * 0.55), int(base[1] * 0.55), int(base[2] * 0.6))
    for level in range(1, int(height // 3) + 1):        # window bands
        Entity(model="cube", position=(x, level * 3 - 0.6, z),
               scale=(width + 0.03, 0.9, depth + 0.03), color=band_col)
    Entity(model="cube", position=(x, height + 0.06, z),  # roof cap
           scale=(width + 0.1, 0.12, depth + 0.1), color=rgb(200, 200, 210))


def surface_height(x, z, include_buildings=True):
    """Height of the highest surface directly under (x, z)."""
    h = GROUND_Y
    for pad in PADS:
        if abs(x - pad.x) <= pad.half and abs(z - pad.z) <= pad.half:
            h = max(h, pad.top)
    if include_buildings:
        for b in boxes:
            if abs(x - b.cx) <= b.hx and abs(z - b.cz) <= b.hz:
                h = max(h, b.top)
    return h


# ============================================================
# DRONE MODEL
# ============================================================

drone = Entity(position=(0, 2, 0))

Entity(parent=drone, model="cube", scale=(0.9, 0.26, 1.3), color=color.azure)              # body
Entity(parent=drone, model="cube", scale=(0.5, 0.18, 0.6), position=(0, 0.2, -0.05), color=color.blue)
Entity(parent=drone, model="cube", scale=(0.35, 0.16, 0.25), position=(0, 0.0, 0.7), color=color.red)  # nose
for _rot in (45, -45):                                                                      # X arms
    Entity(parent=drone, model="cube", scale=(0.12, 0.1, 2.5), rotation=(0, _rot, 0), color=color.dark_gray)

propellers = []
motor_layout = (
    (-0.88, 0.14, 0.88, color.red, 1), (0.88, 0.14, 0.88, color.red, -1),
    (-0.88, 0.14, -0.88, color.white, -1), (0.88, 0.14, -0.88, color.white, 1),
)
for mx, my, mz, pcol, spin_dir in motor_layout:
    motor = Entity(parent=drone, model="cube", scale=(0.22, 0.2, 0.22), position=(mx, my, mz), color=color.black)
    blade = Entity(parent=motor, model="cube", scale=(4.2, 0.12, 0.5), position=(0, 0.6, 0), color=pcol)
    blade.spin_dir = spin_dir
    propellers.append(blade)

# landing gear
for gx in (-0.35, 0.35):
    Entity(parent=drone, model="cube", scale=(0.06, 0.3, 1.0), position=(gx, -0.2, 0), color=color.black)

status_led = Entity(parent=drone, model="cube", scale=(0.12, 0.08, 0.12), position=(0, 0.32, -0.3), color=color.lime)

# soft blob shadow on whatever surface is below the drone
shadow = Entity(model="circle", rotation_x=90, scale=2.0, color=rgb(0, 0, 0, 110), double_sided=True)

# ============================================================
# FLIGHT STATE
# ============================================================


class Flight:
    def __init__(self):
        self.best_time = None
        self.wind_on = False
        self.reset()

    def reset(self):
        self.pos = Vec3(0, PAD_HEIGHT + GEAR, 0)
        self.vel = Vec3(0, 0, 0)
        self.pitch = self.roll = self.yaw = 0.0
        self.tumble = Vec3(0, 0, 0)
        self.stick = [0.0, 0.0, 0.0]          # pitch, roll, yaw (smoothed -1..1)
        self.throttle = 0.0
        self.thrust = 0.0
        self.mode = 0                          # 0 ANGLE / 1 ACRO
        self.althold = False
        self.hold_alt = 0.0
        self.i_alt = 0.0
        self.battery = 100.0
        self.grounded = True
        self.crashed = False
        self.has_flown = False
        self.rest_time = 0.0
        self.landing_scored = False
        self.score = 0
        self.pads_scored = set()
        self.mission_done = False
        self.flight_time = 0.0
        self.sim_time = 0.0
        self.acc = 0.0
        self.boundary_cooldown = 0.0
        self.wind = Vec3(0, 0, 0)
        # per-frame commands
        self.cmd = [0.0, 0.0, 0.0]
        self.cmd_throttle = 0.0


fl = Flight()
paused = False
camera_mode = 0
show_help = True
notice_timer = 0.0

# ============================================================
# HUD
# ============================================================

hud = Text(text="", position=(-0.87, 0.48), origin=(-0.5, 0.5), scale=1.1, color=color.white)
notice_text = Text(text="", position=(0, 0.40), origin=(0, 0), scale=1.6, color=color.yellow)
mode_text = Text(text="", position=(0, -0.46), origin=(0, 0), scale=0.95, color=color.white)
guide_text = Text(text="", position=(0, 0.30), origin=(0, 0), scale=1.05, color=color.white)

help_text = Text(
    text=(
        "CONTROLS\n\n"
        "SPACE       Throttle Up\n"
        "SHIFT       Throttle Down\n"
        "W / S       Pitch Forward / Back\n"
        "A / D       Roll Left / Right\n"
        "Q / E       Yaw Left / Right\n"
        "R           Reset Drone\n"
        "C           Change Camera\n"
        "H           Toggle Help\n"
        "ESC         Quit\n\n"
        "F           Altitude Hold\n"
        "M           ANGLE / ACRO Mode\n"
        "N           Wind On / Off\n"
        "P           Pause"
    ),
    position=(0.50, 0.40),
    origin=(-0.5, 0.5),
    scale=0.8,
    color=color.white,
    background=True,
)


def make_bar(x, y, w, h, col, label):
    Entity(parent=camera.ui, model="quad", color=rgb(0, 0, 0, 150),
           position=(x, y), scale=(w, h), origin=(-0.5, 0))
    fill = Entity(parent=camera.ui, model="quad", color=col,
                  position=(x, y, -0.01), scale=(w, h), origin=(-0.5, 0))
    Text(text=label, parent=camera.ui, position=(x - 0.012, y), origin=(0.5, 0), scale=0.8, color=color.white)
    return fill


BAR_W = 0.22
throttle_bar = make_bar(-0.82, -0.36, BAR_W, 0.022, color.azure, "THR")
battery_bar = make_bar(-0.82, -0.41, BAR_W, 0.022, color.lime, "BAT")

# arrow that points at the next ring / pad
guide_arrow = Entity(
    parent=camera.ui,
    model=Mesh(vertices=[Vec3(0, 0.5, 0), Vec3(-0.35, -0.5, 0), Vec3(0.35, -0.5, 0)],
               triangles=[(0, 1, 2)], mode="triangle"),
    position=(0, 0.22), scale=0.05, color=color.orange, double_sided=True,
)

crash_flash = Entity(parent=camera.ui, model="quad", scale=(3, 2), z=5, color=rgb(255, 0, 0, 0))

# ---------------- minimap ----------------

MAP_SIZE = 0.30
MAP_CENTER = Vec2(0.70, -0.28)
MAP_SCALE = MAP_SIZE / WORLD_SIZE


def map_pos(x, z):
    return Vec2(MAP_CENTER.x + x * MAP_SCALE, MAP_CENTER.y + z * MAP_SCALE)


Entity(parent=camera.ui, model="quad", position=MAP_CENTER, scale=MAP_SIZE, color=rgb(0, 0, 0, 130))
for _b in boxes:
    Entity(parent=camera.ui, model="quad", position=map_pos(_b.cx, _b.cz),
           scale=(_b.hx * 2 * MAP_SCALE, _b.hz * 2 * MAP_SCALE), color=rgb(150, 150, 160, 220), z=-0.01)
for _pad in PADS:
    Entity(parent=camera.ui, model="quad", position=map_pos(_pad.x, _pad.z),
           scale=6 * MAP_SCALE * 1.4, color=_pad.color, z=-0.02)
ring_dots = []
for _r in rings:
    ring_dots.append(Entity(parent=camera.ui, model="circle", position=map_pos(_r.pos.x, _r.pos.z),
                            scale=0.012, color=RING_IDLE, z=-0.02))
map_drone = Entity(
    parent=camera.ui,
    model=Mesh(vertices=[Vec3(0, 0.5, 0), Vec3(-0.35, -0.5, 0), Vec3(0.35, -0.5, 0)],
               triangles=[(0, 1, 2)], mode="triangle"),
    position=MAP_CENTER, scale=0.018, color=color.cyan, z=-0.03, double_sided=True,
)

# ============================================================
# MESSAGES
# ============================================================


def notify(message, seconds=2.5, col=None):
    global notice_timer
    notice_text.text = message
    notice_text.color = col if col is not None else color.yellow
    notice_timer = seconds


# ============================================================
# GAME EVENTS
# ============================================================


def next_target():
    """Next ring to fly, or the nearest landing pad once all rings are done."""
    for r in rings:
        if not r.passed:
            return "RING %d" % (r.index + 1), r.pos
    best = min(PADS, key=lambda p: distance_xz(fl.pos, Vec3(p.x, 0, p.z)))
    return best.name, Vec3(best.x, 0, best.z)


def refresh_ring_colors():
    first = True
    for r, dot_ in zip(rings, ring_dots):
        if r.passed:
            r.set_color(RING_DONE)
            dot_.color = RING_DONE
        elif first:
            r.set_color(RING_NEXT)
            dot_.color = RING_NEXT
            first = False
        else:
            r.set_color(RING_IDLE)
            dot_.color = RING_IDLE


def reset_drone():
    global fl
    best, wind = fl.best_time, fl.wind_on
    fl.reset()
    fl.best_time, fl.wind_on = best, wind
    for r in rings:
        r.passed = False
    refresh_ring_colors()
    crash_flash.color = rgb(255, 0, 0, 0)
    notify("Drone reset. Hold SPACE to take off.", 3.0, color.white)


def crash(reason):
    if fl.crashed:
        return
    fl.crashed = True
    fl.throttle = 0.0
    fl.althold = False
    fl.tumble = Vec3(random.uniform(-170, 170), random.uniform(-90, 90), random.uniform(-170, 170))
    crash_flash.color = rgb(255, 0, 0, 120)
    notify("CRASH!\n%s\nPress R to reset" % reason, 1e9, color.red)


def mark_ring(ring):
    ring.passed = True
    fl.score += RING_POINTS
    done = sum(1 for r in rings if r.passed)
    refresh_ring_colors()
    if done == len(rings):
        notify("ALL RINGS CLEARED! +%d\nNow land on a pad" % RING_POINTS, 3.5, color.lime)
    else:
        notify("RING %d PASSED! +%d  (%d/%d)" % (ring.index + 1, RING_POINTS, done, len(rings)), 2.0, color.lime)


def check_rings(prev, cur):
    """Detect a proper pass through the ring opening (segment crosses ring plane)."""
    for r in rings:
        if r.passed:
            continue
        a0 = dot(prev - r.pos, r.normal)
        a1 = dot(cur - r.pos, r.normal)
        if a0 == a1 or a0 * a1 > 0:
            continue
        t = a0 / (a0 - a1)
        q = prev + (cur - prev) * t - r.pos
        lateral, vertical = dot(q, r.right), q.y
        if abs(lateral) < RING_HOLE and abs(vertical) < RING_HOLE:
            mark_ring(r)
        elif abs(lateral) < RING_SIZE / 2 + 0.6 and abs(vertical) < RING_SIZE / 2 + 0.6:
            notify("Clipped ring %d frame - line it up!" % (r.index + 1), 1.5, color.orange)


def pad_under(x, z):
    for pad in PADS:
        if abs(x - pad.x) <= pad.half and abs(z - pad.z) <= pad.half:
            return pad
    return None


def check_landing_score(dt):
    """Award points once the drone has come to rest on a pad."""
    if not fl.grounded or fl.crashed or not fl.has_flown:
        fl.rest_time = 0.0
        if not fl.grounded:
            fl.landing_scored = False
        return
    speed = fl.vel.length()
    fl.rest_time = fl.rest_time + dt if speed < 0.3 else 0.0
    if fl.rest_time < 0.6 or fl.landing_scored:
        return
    fl.landing_scored = True
    pad = pad_under(fl.pos.x, fl.pos.z)
    if pad is None:
        notify("Landed outside a pad - no landing bonus", 3.0, color.orange)
        return
    if pad.name in fl.pads_scored:
        notify("Already scored %s this run" % pad.name, 3.0, color.orange)
        return
    d = distance_xz(fl.pos, Vec3(pad.x, 0, pad.z))
    precision = int(max(0.0, 1.0 - d / pad.half) * 50)
    fl.pads_scored.add(pad.name)
    fl.score += pad.points + precision
    msg = "PRECISION LANDING - %s!  +%d" % (pad.name, pad.points)
    if precision:
        msg += "  (+%d precision)" % precision
    if all(r.passed for r in rings) and not fl.mission_done:
        fl.mission_done = True
        fl.score += MISSION_BONUS
        if fl.best_time is None or fl.flight_time < fl.best_time:
            fl.best_time = fl.flight_time
        msg += "\nMISSION COMPLETE!  +%d   Time %.1fs" % (MISSION_BONUS, fl.flight_time)
    notify(msg, 5.0, color.lime)


# ============================================================
# PHYSICS
# ============================================================


def touchdown(height, dt):
    """Drone's landing gear reached a horizontal surface at `height`."""
    fl.pos.y = height + GEAR
    v = fl.vel
    if fl.crashed:
        v.y = -v.y * 0.2 if v.y < -1.5 else 0.0
        v.x *= 0.6
        v.z *= 0.6
        fl.tumble = fl.tumble * 0.3
        if abs(v.y) < 0.3:
            fl.grounded = True
            fl.tumble = Vec3(0, 0, 0)
        return
    if not fl.grounded:
        vs = -v.y
        tilt = max(abs(fl.pitch), abs(fl.roll))
        side = math.hypot(v.x, v.z)
        if vs > CRASH_VERTICAL_SPEED:
            crash("Hard landing (%.1f m/s)" % vs)
            return
        if tilt > CRASH_TILT_ANGLE:
            crash("Landing tilt exceeded %d degrees" % CRASH_TILT_ANGLE)
            return
        if side > CRASH_SIDE_SPEED:
            crash("Touched down too fast sideways")
            return
        fl.grounded = True
        fl.rest_time = 0.0
    if v.y < 0:
        v.y = 0.0


def resolve_world(prev, dt):
    p, v = fl.pos, fl.vel

    # invisible boundary walls
    lim = WORLD_SIZE / 2 - BODY_R
    for axis in ("x", "z"):
        c = getattr(p, axis)
        if abs(c) > lim:
            setattr(p, axis, sign(c) * lim)
            if sign(getattr(v, axis)) == sign(c):
                setattr(v, axis, 0.0)
            if fl.boundary_cooldown <= 0 and not fl.crashed:
                notify("Edge of the flight area", 1.5, color.orange)
                fl.boundary_cooldown = 2.0

    # ceiling
    if p.y > MAX_ALT:
        p.y = MAX_ALT
        v.y = min(v.y, 0.0)

    # buildings: roofs (landing) and walls (collisions)
    for b in boxes:
        dx, dz = p.x - b.cx, p.z - b.cz
        if abs(dx) >= b.hx + BODY_R or abs(dz) >= b.hz + BODY_R:
            continue
        if p.y - GEAR >= b.top or p.y + 0.3 <= 0:
            continue
        over_roof = abs(dx) < b.hx + 0.3 and abs(dz) < b.hz + 0.3
        if prev.y - GEAR >= b.top - 0.05 and over_roof:
            touchdown(b.top, dt)
            continue
        pen_x = b.hx + BODY_R - abs(dx)
        pen_z = b.hz + BODY_R - abs(dz)
        if pen_x < pen_z:
            n = Vec3(sign(dx), 0, 0)
            p.x += n.x * pen_x
        else:
            n = Vec3(0, 0, sign(dz))
            p.z += n.z * pen_z
        into = -dot(v, n)
        if into > 0:
            if into > WALL_CRASH_SPEED and not fl.crashed:
                crash("Building collision")
                v.x *= -0.25
                v.z *= -0.25
            else:
                v.x += n.x * into * 1.2
                v.z += n.z * into * 1.2

    # ground and pads
    floor = surface_height(p.x, p.z, include_buildings=False)
    if p.y - GEAR <= floor:
        touchdown(floor, dt)

    # left the surface?
    if fl.grounded and p.y - GEAR > surface_height(p.x, p.z) + 0.05:
        fl.grounded = False


def update_stick(dt):
    targets = fl.cmd
    for i in range(3):
        rate = 5.0 if abs(targets[i]) > 0.01 else 9.0
        fl.stick[i] = approach(fl.stick[i], targets[i], rate * dt)


def update_attitude(dt):
    if fl.crashed:
        if not fl.grounded:
            fl.pitch += fl.tumble.x * dt
            fl.yaw += fl.tumble.y * dt
            fl.roll += fl.tumble.z * dt
        return

    sp, sr, sy = fl.stick
    if fl.grounded and fl.thrust < MASS * GRAVITY * 0.95:
        # sitting on the skids: settle level, allow turning in place only when spooled up
        fl.pitch = approach(fl.pitch, 0.0, 120 * dt)
        fl.roll = approach(fl.roll, 0.0, 120 * dt)
        return

    if fl.mode == 0:                                   # ANGLE: self levelling
        for name, target in (("pitch", sp * MAX_TILT), ("roll", sr * MAX_TILT)):
            cur = getattr(fl, name)
            rate = max(-ATT_RATE_LIMIT, min(ATT_RATE_LIMIT, (target - cur) / ATT_TAU))
            setattr(fl, name, cur + rate * dt)
        fl.yaw += sy * YAW_SPEED * dt
    else:                                              # ACRO: sticks command rotation rate
        fl.pitch = max(-75, min(75, fl.pitch + sp * ACRO_RATE * dt))
        fl.roll = max(-75, min(75, fl.roll + sr * ACRO_RATE * dt))
        fl.yaw += sy * ACRO_YAW * dt


def update_throttle(dt, up):
    if fl.crashed or fl.battery <= 0:
        fl.throttle = 0.0
        return
    if fl.althold:
        climb = fl.cmd_throttle
        if fl.grounded and abs(climb) < 0.05:
            fl.throttle = 0.0
            fl.hold_alt = fl.pos.y
            fl.i_alt = 0.0
            return
        base = HOVER_THROTTLE / max(0.35, up.y)
        if abs(climb) > 0.05:
            fl.hold_alt = fl.pos.y
            target_vy = climb * ALT_CLIMB
        else:
            err = fl.hold_alt - fl.pos.y
            fl.i_alt = max(-0.25, min(0.25, fl.i_alt + err * 0.06 * dt))
            target_vy = max(-2.0, min(2.0, err * 1.2))
        cmd = base + 0.12 * (target_vy - fl.vel.y) + fl.i_alt
        fl.throttle = max(0.0, min(1.0, cmd))
    else:
        fl.throttle = max(0.0, min(1.0, fl.throttle + fl.cmd_throttle * THROTTLE_RATE * dt))


def sim_step(dt):
    fl.sim_time += dt
    fl.boundary_cooldown = max(0.0, fl.boundary_cooldown - dt)
    fl.wind = wind_at(fl.sim_time) if fl.wind_on else Vec3(0, 0, 0)

    update_stick(dt)
    up = up_vector(fl.pitch, fl.yaw, fl.roll)
    update_throttle(dt, up)
    update_attitude(dt)
    up = up_vector(fl.pitch, fl.yaw, fl.roll)

    # motors: first-order spool-up, battery voltage sag
    sag = 0.85 + 0.15 * min(1.0, fl.battery / 25.0)
    target_thrust = 0.0 if (fl.crashed or fl.battery <= 0) else fl.throttle * MAX_THRUST * sag
    fl.thrust += (target_thrust - fl.thrust) * (1.0 - math.exp(-dt / MOTOR_TAU))

    load = fl.thrust / MAX_THRUST
    if not fl.crashed:
        fl.battery = max(0.0, fl.battery - (BATTERY_IDLE_DRAIN * (fl.thrust > 0.5) + BATTERY_LOAD_DRAIN * load ** 2) * dt)

    agl = fl.pos.y - GEAR - surface_height(fl.pos.x, fl.pos.z)
    ground_effect = 1.0 + 0.12 * math.exp(-max(agl, 0.0) / 0.7)

    thrust_force = up * (fl.thrust * ground_effect)
    gravity_force = Vec3(0, -GRAVITY * MASS, 0)
    v_rel = fl.vel - fl.wind
    drag_force = -(v_rel * DRAG + v_rel * (v_rel.length() * DRAG2))

    acceleration = (thrust_force + gravity_force + drag_force) / MASS
    fl.vel += acceleration * dt
    if fl.vel.length() > MAX_SPEED:
        fl.vel = fl.vel.normalized() * MAX_SPEED

    if fl.grounded:                                     # skid friction
        k = max(0.0, 1.0 - 6.0 * dt)
        fl.vel.x *= k
        fl.vel.z *= k

    prev = Vec3(fl.pos.x, fl.pos.y, fl.pos.z)
    fl.pos = fl.pos + fl.vel * dt
    resolve_world(prev, dt)

    if not fl.crashed:
        if not fl.grounded and not fl.has_flown:
            fl.has_flown = True
        if fl.has_flown and not fl.mission_done:
            fl.flight_time += dt
        check_rings(prev, fl.pos)
        check_landing_score(dt)


def wind_at(t):
    a = math.radians(WIND_DIR)
    speed = WIND_BASE + 1.5 * math.sin(t * 0.45) + 1.0 * math.sin(t * 1.3 + 2) + 0.5 * math.sin(t * 3.1)
    return Vec3(math.sin(a) * speed, 0.4 * math.sin(t * 0.9), math.cos(a) * speed)


# ============================================================
# CAMERA
# ============================================================

camera.position = (10, 7, -14)
camera.look_at(drone.position)
camera_smoothness = 5
camera.fov = 70


def update_camera(dt):
    k = min(1.0, dt * camera_smoothness)
    yaw_r = math.radians(fl.yaw)
    flat_forward = Vec3(math.sin(yaw_r), 0, math.cos(yaw_r))
    target_fov = 70

    if camera_mode == 0:                                # chase (follows yaw only, no tilt wobble)
        target = fl.pos - flat_forward * 11 + Vec3(0, 4.5, 0)
        target.y = max(1.0, target.y)
        camera.position = lerp(camera.position, target, k)
        camera.look_at(fl.pos + Vec3(0, 1, 0))
    elif camera_mode == 1:                              # FPV with racing-style uptilt
        camera.position = fl.pos + flat_forward * 0.7 + Vec3(0, 0.25, 0)
        camera.rotation = Vec3(fl.pitch - FPV_UPTILT, fl.yaw, fl.roll)
        target_fov = 100
    else:                                               # high orbit / top-down
        target = fl.pos + Vec3(0, 28, -0.01)
        camera.position = lerp(camera.position, target, k)
        camera.rotation = Vec3(90, 0, 0)                # straight down, north is up
        target_fov = 60
    camera.fov = lerp(camera.fov, target_fov, k)


# ============================================================
# HUD UPDATE
# ============================================================


def compass(yaw):
    names = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return names[int(((yaw % 360) + 22.5) // 45) % 8]


def fmt_time(t):
    return "%02d:%04.1f" % (int(t // 60), t % 60)


def update_hud(dt):
    global notice_timer
    altitude = max(0.0, fl.pos.y - GEAR)
    speed = math.hypot(fl.vel.x, fl.vel.z)
    heading = fl.yaw % 360
    best = fmt_time(fl.best_time) if fl.best_time is not None else "--:--.-"

    hud.text = (
        "ALTITUDE : %5.1f m\n"
        "SPEED    : %5.1f m/s\n"
        "V-SPEED  : %+5.1f m/s\n"
        "THROTTLE : %5.0f %%\n"
        "BATTERY  : %5.0f %%\n"
        "HEADING  : %3.0f %s\n"
        "PITCH/ROLL: %+3.0f / %+3.0f\n"
        "SCORE    : %d\n"
        "TIME     : %s   BEST %s"
    ) % (altitude, speed, fl.vel.y, fl.throttle * 100, fl.battery, heading, compass(heading),
         fl.pitch, fl.roll, fl.score, fmt_time(fl.flight_time), best)

    throttle_bar.scale_x = BAR_W * max(0.001, fl.throttle)
    battery_bar.scale_x = BAR_W * max(0.001, fl.battery / 100.0)
    battery_bar.color = color.lime if fl.battery > 30 else (color.orange if fl.battery > 15 else color.red)

    wind_txt = "WIND %.1f m/s" % fl.wind.length() if fl.wind_on else "WIND OFF"
    mode_text.text = "MODE %s  |  ALT HOLD %s  |  %s  |  CAM %s%s" % (
        MODE_NAMES[fl.mode], "ON" if fl.althold else "OFF", wind_txt,
        CAMERA_NAMES[camera_mode], "  |  PAUSED" if paused else "")

    # guidance
    if fl.crashed or fl.mission_done:
        guide_text.text = ""
        guide_arrow.enabled = False
    else:
        label, target = next_target()
        dx, dz = target.x - fl.pos.x, target.z - fl.pos.z
        rel = ((math.degrees(math.atan2(dx, dz)) - fl.yaw + 180) % 360) - 180
        guide_arrow.enabled = True
        guide_arrow.rotation_z = rel
        guide_text.text = "%s  -  %.0f m" % (label, math.sqrt(dx * dx + dz * dz))

    # minimap
    map_drone.position = map_pos(fl.pos.x, fl.pos.z)
    map_drone.rotation_z = fl.yaw

    # notices / warnings
    if notice_timer > 0:
        notice_timer -= dt
        if notice_timer <= 0:
            notice_text.text = ""
    if fl.battery < 15 and fl.battery > 0 and not fl.crashed and notice_timer <= 0:
        notify("LOW BATTERY - land now!", 0.5, color.red)
    if fl.battery <= 0 and not fl.crashed and not fl.grounded and notice_timer <= 0:
        notify("BATTERY EMPTY", 0.5, color.red)

    if crash_flash.color.a > 0:
        c = crash_flash.color
        crash_flash.color = color.Color(c.r, c.g, c.b, max(0.0, c.a - dt * 0.45))


# ============================================================
# INPUT
# ============================================================


def key_down(*names):
    return any(held_keys[n] for n in names)


def input(key):
    global camera_mode, show_help, paused

    if key == "r":
        reset_drone()
    elif key == "c":
        camera_mode = (camera_mode + 1) % 3
    elif key == "h":
        show_help = not show_help
        help_text.enabled = show_help
    elif key == "m" and not fl.crashed:
        fl.mode = 1 - fl.mode
        notify("%s mode" % MODE_NAMES[fl.mode], 1.5, color.white)
    elif key == "f" and not fl.crashed:
        fl.althold = not fl.althold
        fl.hold_alt = fl.pos.y
        fl.i_alt = 0.0
        notify("Altitude hold %s" % ("ON" if fl.althold else "OFF"), 1.5, color.white)
    elif key == "n":
        fl.wind_on = not fl.wind_on
        notify("Wind %s" % ("ON" if fl.wind_on else "OFF"), 1.5, color.white)
    elif key == "p":
        paused = not paused
    elif key == "escape":
        application.quit()


def read_controls():
    fl.cmd[0] = (1 if key_down("w") else 0) - (1 if key_down("s") else 0)                    # pitch fwd / back
    fl.cmd[1] = (1 if key_down("d") else 0) - (1 if key_down("a") else 0)                    # roll right / left
    fl.cmd[2] = (1 if key_down("e") else 0) - (1 if key_down("q") else 0)                    # yaw right / left
    fl.cmd_throttle = (1 if key_down("space") else 0) - (
        1 if key_down("shift", "left shift", "right shift") else 0)


# ============================================================
# MAIN UPDATE
# ============================================================

led_clock = 0.0


def update():
    global led_clock
    dt = min(time.dt, 0.1)

    if not paused:
        read_controls()
        fl.acc += dt
        steps = 0
        while fl.acc >= STEP and steps < 12:
            sim_step(STEP)
            fl.acc -= STEP
            steps += 1
        if steps == 12:
            fl.acc = 0.0

        spin = 3200.0 * min(1.0, fl.thrust / MAX_THRUST)
        for blade in propellers:
            blade.rotation_y += blade.spin_dir * spin * dt
        led_clock += dt

    drone.position = fl.pos
    drone.rotation = Vec3(fl.pitch, fl.yaw, fl.roll)

    if fl.crashed:
        status_led.color = color.red
    elif fl.battery < 15:
        status_led.color = color.red if int(led_clock * 4) % 2 == 0 else color.black
    else:
        status_led.color = color.lime if int(led_clock * 2) % 2 == 0 else color.green

    # blob shadow
    sh = surface_height(fl.pos.x, fl.pos.z)
    agl = max(0.0, fl.pos.y - GEAR - sh)
    shadow.position = Vec3(fl.pos.x, sh + 0.03, fl.pos.z)
    shadow.scale = max(0.8, 2.4 - agl * 0.04)
    shadow.color = rgb(0, 0, 0, int(max(25, 120 - agl * 4)))

    update_camera(dt)
    update_hud(dt)


# ============================================================
# START
# ============================================================

reset_drone()
notify("Hold SPACE to take off  -  hover is about 50 % throttle", 6.0, color.white)

if __name__ == "__main__":
    app.run()
