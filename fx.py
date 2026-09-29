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

    def motor(t, d):  # harmonic stack, integer cycles per second => seamless loop
        return .22 * sum(math.sin(tau * 95 * k * t) / k ** .8 for k in range(1, 9)) + .05 * rnd.uniform(-1, 1)

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

    return {
        "motor": _sfx(loader, "motor", 1.0, motor, True),
        "wind": _sfx(loader, "wind", 2.0, wind, True),
        "crash": _sfx(loader, "crash", 1.4, crash),
        "chime": _sfx(loader, "chime", .5, notes([880, 1320], .12)),
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
    for bx, bz, hw, hd, h in buildings:
        Entity(model="cube", position=(bx - hw * .2, h + .6, bz), scale=(hw * 1.1, 1.2, hd * .8), color=C(70, 72, 80))
        Entity(model="cube", position=(bx + hw * .4, h + 3, bz + hd * .3), scale=(.18, 6, .18), color=color.dark_gray)
        if h > 25:
            Blink(model="sphere", position=(bx + hw * .4, h + 6.2, bz + hd * .3), scale=.6,
                  shader=unlit_shader, ph=r.random() * 2)
    n = 0
    while n < 110:
        x, z = r.uniform(-285, 285), r.uniform(-285, 285)
        if math.hypot(x, z) < 22 or any(abs(x - b[0]) < b[2] + 5 and abs(z - b[1]) < b[3] + 5 for b in buildings) \
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
