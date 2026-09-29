from ursina import *

app = Ursina()

# Ground
ground = Entity(
    model='plane',
    scale=(100, 1, 100),
    color=color.green,
    texture='grass',
    texture_scale=(20, 20),
    collider='box'
)

# Drone
drone = Entity(
    model='cube',
    color=color.orange,
    scale=(1, 0.3, 1),
    position=(0, 5, 0)
)

# Altitude display
altitude_text = Text(
    text="Altitude: 5 m",
    position=(-0.85, 0.45),
    scale=1.5
)

speed_text = Text(
    text="Speed: 0 m/s",
    position=(-0.85, 0.40),
    scale=1.5
)

previous_position = Vec3(drone.position)

throttle = 50
vertical_velocity = 0

throttle_text = Text(
    text="Throttle: 50%",
    position=(-0.85, 0.35),
    scale=1.5
)
# Camera
camera.position = (0, 10, -20)
camera.look_at(drone)

def update():
    global throttle, vertical_velocity

    speed = 5 * time.dt

    if held_keys['w']:
        drone.z += speed
    if held_keys['s']:
        drone.z -= speed
    if held_keys['a']:
        drone.x -= speed
    if held_keys['d']:
        drone.x += speed

    # Throttle control
    if held_keys['space']:
        throttle = min(100, throttle + 30 * time.dt)

    if held_keys['left shift']:
        throttle = max(0, throttle - 30 * time.dt)

    throttle_text.text = f"Throttle: {throttle:.0f}%"

    # Gravity and lift
    gravity = 9.81
    lift = (throttle / 50) * gravity
    acceleration = lift - gravity

    vertical_velocity += acceleration * time.dt
    drone.y += vertical_velocity * time.dt

    if drone.y <= 0.3:
        drone.y = 0.3
        vertical_velocity = 0

    camera.position = drone.position + Vec3(0, 10, -20)
    camera.look_at(drone)

    altitude_text.text = f"Altitude: {drone.y:.1f} m"

    speed = (drone.position - previous_position).length() / time.dt
    speed_text.text = f"Speed: {speed:.1f} m/s"
    previous_position.set(drone.x, drone.y, drone.z)

app.run()