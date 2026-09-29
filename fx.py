"""Procedural sound effects + scenery for the Drone Simulator (no asset files needed)."""
import math
import os
import random
import tempfile
import wave
from array import array

from panda3d.core import Filename
from ursina import *
from ursina.shaders import unlit_shader

SR = 22050


def C(r, g, b, a=255):
    """0-255 colour helper (color.rgb/rgba expect 0-1 floats in newer Ursina versions)."""
    return color.Color(r / 255, g / 255, b / 255, a / 255)


def _sfx(loader, name, seconds, fn, loop=False):
    """Synthesize fn(t, dur) -> [-1..1] into a temp .wav and load it as a Panda3D sound."""
    data = array("h", (int(max(-1, min(1, fn(i / SR, seconds))) * 14000) for i in range(int(seconds * SR))))
    path = os.path.join(tempfile.gettempdir(), f"dronesim_{name}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    s = loader.loadSfx(Filename.fromOsSpecific(path))
    s.setLoop(loop)
    return s


def load_sounds(loader):
    rnd, tau = random.Random(1), math.tau
    partials = [(rnd.randint(40, 700), rnd.uniform(0, tau)) for _ in range(28)]

    def motor(t, d):  # 4 slightly detuned rotors beat against each other; integer Hz => seamless loop
        return .07 * sum(math.sin(tau * fr * k * t) / k ** .8 for fr in (92, 95, 98, 101) for k in range(1, 7)) \
            + .05 * rnd.uniform(-1, 1)

    def music(t, d):  # Am - F - C - G synth loop: pad + bass + arpeggio lead
        ci, n, tt = int(t / 2) % 4, int(t / .25) % 8, t % .25
        root = (110, 87.31, 130.81, 98)[ci]
        third = 1.189 if ci == 0 else 1.26
        arp = root * 4 * (1, third, 1.498, 2, 1.498, third, 1, 1.498)[n]
        pad = .05 * sum(math.sin(tau * root * m * t) for m in (2, 2 * third, 3))
        bass = .28 * math.sin(tau * root * t) * math.exp(-(t % 1) * 2.5)
        lead = .16 * math.sin(tau * arp * t) * math.exp(-tt * 9)
        return (pad + bass + lead) * min(1, t / .03, (d - t) / .03)

    def wind(t, d):   # many sines = noise-like, seamless over 2 s
        return .25 * sum(math.sin(tau * f / 2 * t + p) / (1 + f / 120) for f, p in partials) / 4

    def crash(t, d):
        return (rnd.uniform(-1, 1) * .9 + math.sin(tau * 55 * t)) * math.exp(-t * 4.5) * .6

    def notes(freqs, per):
        def f(t, d):
            i = min(int(t / per), len(freqs) - 1)
            return math.sin(tau * freqs[i] * t) * math.exp(-(t - i * per) * 7) * .8
        return f

    def thud(t, d):
        return math.sin(tau * (75 - 40 * t) * t) * math.exp(-t * 16) + .15 * rnd.uniform(-1, 1) * math.exp(-t * 30)

    def beep(t, d):
        return math.sin(tau * 1100 * t) * (1 if t < .11 else 0) * .6

    def buzz(t, d):
        return (1 if math.sin(tau * 140 * t) > 0 else -1) * .35 * math.exp(-t * 6)

    return {
        "motor": _sfx(loader, "motor", 1.0, motor, True),
        "music": _sfx(loader, "music", 8.0, music, True),
        "wind": _sfx(loader, "wind", 2.0, wind, True),
        "crash": _sfx(loader, "crash", 1.4, crash),
        "chime": _sfx(loader, "chime", .7, notes([784, 1047, 1319, 1568], .07)),
        "buzz": _sfx(loader, "buzz", .3, buzz),
        "fanfare": _sfx(loader, "fanfare", 1.2, notes([523, 659, 784, 1046], .22)),
        "thud": _sfx(loader, "thud", .3, thud),
        "beep": _sfx(loader, "beep", .15, beep),
    }


class Cloud(Entity):
    def update(self):
        self.x += self.sp * time.dt
        if self.x > 420:
            self.x = -420


class Blink(Entity):
    def update(self):
        self.color = color.red if int(time.time() * 1.6 + self.ph) % 2 else C(90, 0, 0)


def scenery(buildings, keep):
    """Roof details + blinking aviation lights, trees, drifting clouds."""
    r = random.Random(5)
    asphalt, edge = C(48, 50, 56), C(235, 235, 235)
    for sx, sz in ((10, 600), (600, 10)):  # two crossing roads with edge lines
        Entity(model="quad", rotation_x=90, position=(0, .02, 0), scale=(sx, sz), color=asphalt)
    for s_ in (-4.6, 4.6):
        Entity(model="quad", rotation_x=90, position=(s_, .03, 0), scale=(.25, 600), color=edge, shader=unlit_shader)
        Entity(model="quad", rotation_x=90, position=(0, .03, s_), scale=(600, .25), color=edge, shader=unlit_shader)
    for bx, bz, hw, hd, h in buildings:
        Entity(model="cube", position=(bx - hw * .2, h + .6, bz), scale=(hw * 1.1, 1.2, hd * .8), color=C(70, 72, 80))
        Entity(model="cube", position=(bx + hw * .4, h + 3, bz + hd * .3), scale=(.18, 6, .18), color=color.dark_gray)
        if h > 25:
            Blink(model="sphere", position=(bx + hw * .4, h + 6.2, bz + hd * .3), scale=.6,
                  shader=unlit_shader, ph=r.random() * 2)
    n = 0
    while n < 110:
        x, z = r.uniform(-285, 285), r.uniform(-285, 285)
        if math.hypot(x, z) < 22 or abs(x) < 8 or abs(z) < 8 or any(abs(x - b[0]) < b[2] + 5 and abs(z - b[1]) < b[3] + 5 for b in buildings) \
                or any(math.hypot(x - k.x, z - k.z) < 10 for k in keep):
            continue
        n += 1
        h = r.uniform(4, 8)
        Entity(model="cube", origin_y=-.5, position=(x, 0, z), scale=(.5, h * .45, .5), color=C(90, 60, 35))
        Entity(model="sphere", position=(x, h * .7, z), scale=(h * .55, h * .75, h * .55),
               color=C(30, r.randint(70, 130), 40))
    for _ in range(24):
        Cloud(model="sphere", position=(r.uniform(-400, 400), r.uniform(110, 190), r.uniform(-300, 300)),
              scale=(r.uniform(50, 110), r.uniform(8, 16), r.uniform(30, 60)),
              color=C(255, 255, 255, 190), shader=unlit_shader, sp=r.uniform(1, 4))


def sky_extras():
    """Stars (night only) + a sun/moon disc that always faces the camera."""
    r = random.Random(9)
    stars = Entity(enabled=False)
    for _ in range(140):
        a, e = r.uniform(0, math.tau), r.uniform(.15, 1.4)
        Entity(parent=stars, model="sphere", shader=unlit_shader, scale=r.uniform(2, 5), color=C(255, 255, 255, 230),
               position=(math.cos(a) * math.cos(e) * 900, math.sin(e) * 900, math.sin(a) * math.cos(e) * 900))
    disc = Entity(model="circle", billboard=True, shader=unlit_shader, position=(-300, 500, -200),
                  scale=70, color=C(255, 235, 170))
    return stars, disc


def draw_track(rings):
    """Glowing guide dots from the launch pad through every gate, in order."""
    pts = [Vec3(0, 3, 0)] + [g.position for g in rings]
    dots = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        n = max(1, int((b - a).length() / 7))
        for j in range(1, n):
            d = Entity(model="cube", shader=unlit_shader, scale=.3, color=C(80, 220, 255, 200), position=lerp(a, b, j / n))
            d.seg = i
            dots.append(d)
    return dots


class Spark(Entity):
    def __init__(self, pos, v, col):
        super().__init__(model="cube", position=pos, scale=.28, color=col, shader=unlit_shader)
        self.v, self.life = v, 0.0

    def update(self):
        self.life += time.dt
        self.v.y -= 5 * time.dt
        self.position += self.v * time.dt
        self.scale = max(.01, .28 * (1 - self.life / .9))
        if self.life > .9:
            destroy(self)


class Pop(Entity):
    """Expanding shock-wave disc at a cleared ring."""
    def __init__(self, pos, yaw):
        super().__init__(model="circle", position=pos, rotation_y=yaw, scale=6, shader=unlit_shader,
                         color=C(120, 255, 140, 200), double_sided=True)
        self.life = 0.0

    def update(self):
        self.life += time.dt
        self.scale = 6 + self.life * 34
        self.color = C(120, 255, 140, int(max(0, 200 * (1 - self.life / .6))))
        if self.life > .6:
            destroy(self)


def ring_burst(pos, yaw_deg):
    y = math.radians(yaw_deg)
    right, fwd = Vec3(math.cos(y), 0, -math.sin(y)), Vec3(math.sin(y), 0, math.cos(y))
    Pop(pos, yaw_deg)
    for i in range(40):
        a = i / 40 * math.tau
        d = right * math.cos(a) + Vec3(0, math.sin(a), 0)
        Spark(pos + d * 4, d * random.uniform(6, 14) + fwd * random.uniform(2, 8),
              random.choice([color.gold, color.lime, color.white, color.orange]))
