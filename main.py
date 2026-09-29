from ursina import *
import random
import math

# ============================================================
# DRONE FLIGHT TRAINING SIMULATOR
# Robodrone Challenge
# ============================================================

app = Ursina()

window.title = "Drone Flight Training Simulator"
window.borderless = False
window.fullscreen = False
window.color = color.rgb(120, 170, 190)

# ============================================================
# SETTINGS
# ============================================================

GRAVITY = 9.81
MASS = 1.5

MAX_LIFT_FORCE = MASS * GRAVITY * 2.0
HOVER_THROTTLE = 0.50

DRAG = 0.35

PITCH_SPEED = 55
ROLL_SPEED = 55
YAW_SPEED = 80

MAX_TILT = 35

GROUND_Y = 0

CRASH_VERTICAL_SPEED = 4.5
CRASH_TILT_ANGLE = 15

WORLD_SIZE = 100

score = 0
crashed = False
landed = False

camera_mode = 0
show_help = True

# ============================================================
# WORLD
# ============================================================

Sky()

ground = Entity(
    model="cube",
    scale=(WORLD_SIZE, 0.2, WORLD_SIZE),
    position=(0, -0.1, 0),
    color=color.rgb(70, 110, 70),
    collider="box"
)

# Some distant boundary walls
Entity(
    model="cube",
    scale=(WORLD_SIZE, 5, 0.5),
    position=(0, 2.5, WORLD_SIZE / 2),
    color=color.rgb(90, 90, 90),
)

Entity(
    model="cube",
    scale=(WORLD_SIZE, 5, 0.5),
    position=(0, 2.5, -WORLD_SIZE / 2),
    color=color.rgb(90, 90, 90),
)

Entity(
    model="cube",
    scale=(0.5, 5, WORLD_SIZE),
    position=(WORLD_SIZE / 2, 2.5, 0),
    color=color.rgb(90, 90, 90),
)

Entity(
    model="cube",
    scale=(0.5, 5, WORLD_SIZE),
    position=(-WORLD_SIZE / 2, 2.5, 0),
    color=color.rgb(90, 90, 90),
)

# ============================================================
# DRONE
# ============================================================

drone = Entity(
    position=(0, 2, 0),
    rotation=(0, 0, 0)
)

# Main body
body = Entity(
    parent=drone,
    model="cube",
    scale=(1.4, 0.28, 0.8),
    color=color.azure
)

# Central top
Entity(
    parent=drone,
    model="cube",
    scale=(0.55, 0.18, 0.55),
    position=(0, 0.22, 0),
    color=color.blue
)

# Arms
Entity(
    parent=drone,
    model="cube",
    scale=(3.0, 0.12, 0.12),
    color=color.dark_gray
)

Entity(
    parent=drone,
    model="cube",
    scale=(0.12, 0.12, 2.1),
    color=color.dark_gray
)

# Motors and propellers
motor_positions = [
    (-1.2, 0.15, -0.75),
    (1.2, 0.15, -0.75),
    (-1.2, 0.15, 0.75),
    (1.2, 0.15, 0.75)
]

propellers = []

for pos in motor_positions:

    motor = Entity(
        parent=drone,
        model="cube",
        scale=(0.22, 0.18, 0.22),
        position=pos,
        color=color.black
    )

    propeller = Entity(
        parent=motor,
        model="cube",
        scale=(0.9, 0.035, 0.12),
        position=(0, 0.12, 0),
        color=color.white
    )

    propellers.append(propeller)

# ============================================================
# FLIGHT STATE
# ============================================================

velocity = Vec3(0, 0, 0)

throttle = HOVER_THROTTLE

# ============================================================
# BUILDINGS
# ============================================================

buildings = []

random.seed(42)

protected_positions = [
    (0, 0),       # HOME
    (20, 20),     # PAD B
    (-10, -10),
    (0, -15),
    (15, -5),
]

def position_is_safe(x, z):

    for px, pz in protected_positions:

        if distance_xz(Vec3(x, 0, z), Vec3(px, 0, pz)) < 8:
            return False

    return True


def distance_xz(a, b):
    return math.sqrt(
        (a.x - b.x) ** 2 +
        (a.z - b.z) ** 2
    )


# Create 30 buildings
attempts = 0

while len(buildings) < 30 and attempts < 500:

    attempts += 1

    x = random.uniform(-42, 42)
    z = random.uniform(-42, 42)

    if not position_is_safe(x, z):
        continue

    width = random.uniform(3, 7)
    depth = random.uniform(3, 7)
    height = random.uniform(4, 15)

    building = Entity(
        model="cube",
        position=(x, height / 2, z),
        scale=(width, height, depth),
        color=color.rgb(
            random.randint(80, 150),
            random.randint(80, 150),
            random.randint(90, 170)
        ),
        collider="box"
    )

    buildings.append(building)

# ============================================================
# LANDING PADS
# ============================================================

def create_pad(name, position, pad_color):

    pad = Entity(
        model="cube",
        scale=(6, 0.15, 6),
        position=position,
        color=pad_color
    )

    # Center marking
    Entity(
        parent=pad,
        model="cube",
        scale=(0.15, 1.2, 0.8),
        color=color.white
    )

    Entity(
        parent=pad,
        model="cube",
        scale=(0.8, 1.2, 0.15),
        color=color.white
    )

    Text(
        text=name,
        parent=pad,
        y=1,
        billboard=True,
        scale=2,
        color=color.white
    )

    return pad


home_pad = create_pad(
    "HOME",
    (0, 0.08, 0),
    color.green
)

pad_b = create_pad(
    "PAD B",
    (20, 0.08, 20),
    color.yellow
)

# ============================================================
# PRACTICE RINGS
# ============================================================

rings = []

ring_positions = [
    (-12, 5, 0),
    (-20, 7, 5),
    (-28, 9, 10),
    (-20, 11, 20),
    (-5, 13, 25),
    (10, 10, 28),
    (22, 8, 25),
    (30, 6, 20),
]


def create_ring(index, position):

    parent = Entity(
        position=position,
        rotation=(0, 0, 0)
    )

    # Four orange pieces make a square training ring.
    thickness = 0.18
    size = 4

    Entity(
        parent=parent,
        model="cube",
        scale=(size, thickness, thickness),
        position=(0, size / 2, 0),
        color=color.orange
    )

    Entity(
        parent=parent,
        model="cube",
        scale=(size, thickness, thickness),
        position=(0, -size / 2, 0),
        color=color.orange
    )

    Entity(
        parent=parent,
        model="cube",
        scale=(thickness, size, thickness),
        position=(-size / 2, 0, 0),
        color=color.orange
    )

    Entity(
        parent=parent,
        model="cube",
        scale=(thickness, size, thickness),
        position=(size / 2, 0, 0),
        color=color.orange
    )

    Text(
        text=str(index + 1),
        parent=parent,
        position=(0, 2.8, 0),
        billboard=True,
        scale=1.5,
        color=color.orange
    )

    parent.passed = False

    rings.append(parent)


for i, position in enumerate(ring_positions):
    create_ring(i, position)

# ============================================================
# HUD
# ============================================================

hud = Text(
    text="",
    position=(-0.85, 0.45),
    origin=(0, 0),
    scale=1.2,
    color=color.white
)

status_text = Text(
    text="",
    position=(-0.85, 0.30),
    origin=(0, 0),
    scale=1.1,
    color=color.yellow
)

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
        "ESC         Quit"
    ),
    position=(0.55, 0.42),
    scale=0.85,
    color=color.white,
    background=True
)

# ============================================================
# CAMERA
# ============================================================

camera.position = (10, 7, -14)
camera.look_at(drone.position)

camera_smoothness = 5


def update_camera():

    global camera_mode

    if camera_mode == 0:
        # Chase camera
        target_position = (
            drone.position
            - drone.forward * 12
            + Vec3(0, 6, 0)
        )

        camera.position = lerp(
            camera.position,
            target_position,
            min(1, time.dt * camera_smoothness)
        )

        camera.look_at(
            drone.position + Vec3(0, 1, 0)
        )

    elif camera_mode == 1:
        # FPV
        target_position = (
            drone.position
            + drone.forward * 0.8
            + Vec3(0, 0.4, 0)
        )

        camera.position = target_position

        camera.rotation = drone.rotation

    elif camera_mode == 2:
        # High orbit
        target_position = (
            drone.position
            + Vec3(0, 25, -0.01)
        )

        camera.position = lerp(
            camera.position,
            target_position,
            min(1, time.dt * camera_smoothness)
        )

        camera.look_at(drone.position)

# ============================================================
# RESET
# ============================================================

def reset_drone():

    global velocity
    global throttle
    global score
    global crashed
    global landed

    drone.position = Vec3(0, 2, 0)
    drone.rotation = Vec3(0, 0, 0)

    velocity = Vec3(0, 0, 0)

    throttle = HOVER_THROTTLE

    score = 0

    crashed = False
    landed = False

    for ring in rings:
        ring.passed = False

    status_text.text = "Drone reset."


# ============================================================
# CRASH
# ============================================================

def crash(reason):

    global crashed
    global velocity

    if crashed:
        return

    crashed = True

    velocity = Vec3(0, 0, 0)

    status_text.text = (
        "CRASH!\n"
        + reason
        + "\nPress R to reset"
    )

# ============================================================
# LANDING CHECK
# ============================================================

def check_landing():

    global landed
    global score

    if drone.y > 1.0:
        return

    # Calculate tilt
    tilt = max(
        abs(drone.rotation_x),
        abs(drone.rotation_z)
    )

    vertical_speed = abs(velocity.y)

    # Hard landing
    if vertical_speed > CRASH_VERTICAL_SPEED:
        crash("Hard landing")
        return

    # Tilted landing
    if tilt > CRASH_TILT_ANGLE:
        crash("Landing tilt exceeded 15 degrees")
        return

    # Check landing pad
    home_distance = distance_xz(
        drone.position,
        home_pad.position
    )

    pad_b_distance = distance_xz(
        drone.position,
        pad_b.position
    )

    if home_distance < 3:

        if not landed:
            score += 100
            landed = True

        status_text.text = "PRECISION LANDING - HOME! +100"

    elif pad_b_distance < 3:

        if not landed:
            score += 150
            landed = True

        status_text.text = "PRECISION LANDING - PAD B! +150"

    else:

        crash("Landed outside a landing pad")

# ============================================================
# BUILDING COLLISION
# ============================================================

def check_building_collision():

    for building in buildings:

        horizontal_distance = distance_xz(
            drone.position,
            building.position
        )

        building_radius = max(
            building.scale_x,
            building.scale_z
        ) / 2

        if horizontal_distance < building_radius + 0.8:

            building_bottom = 0
            building_top = building.y + building.scale_y / 2

            if drone.y < building_top + 1:

                crash("Building collision")
                return

# ============================================================
# RING SCORING
# ============================================================

def check_rings():

    global score

    for ring in rings:

        if ring.passed:
            continue

        d = distance_xz(
            drone.position,
            ring.position
        )

        vertical_difference = abs(
            drone.y - ring.y
        )

        # Approximate ring opening
        if d < 3 and vertical_difference < 3:

            ring.passed = True

            score += 25

            status_text.text = (
                "RING PASSED! +25"
            )

# ============================================================
# INPUT
# ============================================================

def input(key):

    global camera_mode
    global show_help

    if key == "r":
        reset_drone()

    elif key == "c":
        camera_mode += 1

        if camera_mode > 2:
            camera_mode = 0

    elif key == "h":
        show_help = not show_help
        help_text.enabled = show_help

    elif key == "escape":
        application.quit()

# ============================================================
# PHYSICS
# ============================================================

def update_physics():

    global throttle
    global velocity
    global crashed
    global landed

    if crashed:
        return

    # --------------------------------------------------------
    # THROTTLE
    # --------------------------------------------------------

    if held_keys["space"]:
        throttle += 0.35 * time.dt

    if held_keys["shift"]:
        throttle -= 0.35 * time.dt

    throttle = clamp(throttle, 0, 1)

    # --------------------------------------------------------
    # ROTATION CONTROL
    # --------------------------------------------------------

    if held_keys["w"]:
        drone.rotation_x -= PITCH_SPEED * time.dt

    if held_keys["s"]:
        drone.rotation_x += PITCH_SPEED * time.dt

    if held_keys["a"]:
        drone.rotation_z += ROLL_SPEED * time.dt

    if held_keys["d"]:
        drone.rotation_z -= ROLL_SPEED * time.dt

    if held_keys["q"]:
        drone.rotation_y -= YAW_SPEED * time.dt

    if held_keys["e"]:
        drone.rotation_y += YAW_SPEED * time.dt

    # Limit pitch/roll
    drone.rotation_x = clamp(
        drone.rotation_x,
        -MAX_TILT,
        MAX_TILT
    )

    drone.rotation_z = clamp(
        drone.rotation_z,
        -MAX_TILT,
        MAX_TILT
    )

    # --------------------------------------------------------
    # LIFT
    # --------------------------------------------------------

    lift_force = throttle * MAX_LIFT_FORCE

    # Drone's local UP direction.
    # When tilted, this vector automatically contains
    # horizontal thrust.
    thrust_force = drone.up * lift_force

    # --------------------------------------------------------
    # GRAVITY
    # --------------------------------------------------------

    gravity_force = Vec3(
        0,
        -GRAVITY * MASS,
        0
    )

    # --------------------------------------------------------
    # AIR DRAG
    # --------------------------------------------------------

    drag_force = -velocity * DRAG

    # --------------------------------------------------------
    # TOTAL FORCE
    # --------------------------------------------------------

    total_force = (
        thrust_force
        + gravity_force
        + drag_force
    )

    acceleration = total_force / MASS

    # --------------------------------------------------------
    # VELOCITY
    # --------------------------------------------------------

    velocity += acceleration * time.dt

    # Prevent insane speeds
    speed = velocity.length()

    if speed > 30:
        velocity = velocity.normalized() * 30

    # --------------------------------------------------------
    # POSITION
    # --------------------------------------------------------

    drone.position += velocity * time.dt

    # --------------------------------------------------------
    # GROUND
    # --------------------------------------------------------

    if drone.y <= 0.5:

        drone.y = 0.5

        check_landing()

        if not crashed:

            # Stop vertical movement after landing
            if velocity.y < 0:
                velocity.y = 0

# ============================================================
# HUD UPDATE
# ============================================================

def update_hud():

    altitude = max(0, drone.y)

    speed = velocity.length()

    hud.text = (
        f"ALTITUDE : {altitude:5.1f} m\n"
        f"SPEED    : {speed:5.1f} m/s\n"
        f"THROTTLE : {throttle * 100:5.0f}%\n"
        f"SCORE    : {score}"
    )

# ============================================================
# MAIN UPDATE
# ============================================================

def update():

    global landed

    # Propellers
    for propeller in propellers:

        propeller.rotation_y += 1000 * time.dt

    if not crashed:

        update_physics()

        check_building_collision()

        check_rings()

    update_camera()

    update_hud()

# ============================================================
# START
# ============================================================

reset_drone()

app.run()