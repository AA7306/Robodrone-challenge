"""Drone Flight Training Simulator - Python + Ursina (Panda3D)."""
import json
import math
import os
import random
from ursina import *
from ursina.lights import AmbientLight, DirectionalLight
from ursina.shaders import basic_lighting_shader, unlit_shader

from fx import C, draw_track, load_sounds, ring_burst, scenery, sky_extras

# ----------------------------------------------------------------- constants
G = 9.81
MAX_TILT = 35.0          # degrees of commanded pitch / roll
YAW_RATE = 100.0         # deg/s
THROTTLE_RATE = 0.5      # throttle change per second
MAX_LAND_SPEED = 4.5     # m/s vertical, faster = crash
MAX_LAND_TILT = 15.0     # degrees, more tilted = crash
MAX_LAND_HSPEED = 8.0    # m/s horizontal on touchdown
WORLD_LIMIT = 290
RING_R, RING_HIT = 4.0, 3.6
PAD_R = 4.0
PADS = [("HOME", Vec3(0, 0, 0)), ("PAD B", Vec3(60, 0, 90))]
SPAWN = Vec3(0, 0.1, 0)

app = Ursina(title="Drone Flight Training Simulator", vsync=True)
window.exit_button.visible = False
window.color = C(120, 170, 230)
sky = Sky()
SND = load_sounds(app.loader)
# lighting + fog (comment these 5 lines out if your GPU misbehaves)
Entity.default_shader = basic_lighting_shader
sun = DirectionalLight()
sun.look_at(Vec3(.6, -1, .4))
amb = AmbientLight(color=C(95, 100, 125))
scene.fog_color, scene.fog_density = C(150, 185, 225), (90, 450)
rng = random.Random(42)

# ------------------------------------------------------------------- world
Entity(model="plane", scale=600, texture="white_cube", texture_scale=(150, 150),
       color=C(70, 120, 60))

pad_state = {}
for name, p in PADS:
    Entity(model="circle", position=p + Vec3(0, .04, 0), rotation_x=90,
           scale=PAD_R * 2, color=C(230, 230, 230))
    Entity(model="circle", position=p + Vec3(0, .05, 0), rotation_x=90,
           scale=PAD_R * 1.4, color=color.azure if name == "HOME" else color.violet)
    Entity(model="circle", position=p + Vec3(0, .06, 0), rotation_x=90,
           scale=PAD_R * .5, color=color.white)
    Text(name, parent=scene, position=p + Vec3(-1.2, 0.08, -PAD_R - .4), rotation_x=90,
         scale=14, color=color.black)
    pad_state[name] = True  # armed for scoring


class Ring(Entity):
    def __init__(self, pos, yaw, idx):
        super().__init__(position=pos, rotation_y=yaw)
        self.idx, self.prev = idx, None
        self.got = False
        self.bits = []
        for i in range(24):
            a = i / 24 * math.tau
            self.bits.append(Entity(parent=self, model="cube", color=color.orange, shader=unlit_shader,
                                    position=(math.cos(a) * RING_R, math.sin(a) * RING_R, 0),
                                    scale=.55, rotation_z=math.degrees(a)))
        Text(str(idx), parent=self, billboard=True, origin=(0, 0), position=(0, RING_R + 2.4, 0),
             scale=50, color=color.gold)

    def set_got(self, v):
        self.got = v
        for b in self.bits:
            b.color = color.lime if v else color.orange


rings = []
for i in range(8):
    ang = i * 45 + 10
    r = 40 + i * 12
    pos = Vec3(math.sin(math.radians(ang)) * r, 6 + (i % 4) * 4.5, math.cos(math.radians(ang)) * r)
    rings.append(Ring(pos, ang, i + 1))

keep_clear = [p for _, p in PADS] + [r.position for r in rings]
buildings = []  # (x, z, half_w, half_d, height)
tries = 0
while len(buildings) < 30 and tries < 2000:
    tries += 1
    x, z = rng.uniform(-250, 250), rng.uniform(-250, 250)
    w, d, h = rng.uniform(6, 14), rng.uniform(6, 14), rng.uniform(10, 45)
    if abs(x) < 12 or abs(z) < 12 or any(math.hypot(x - k.x, z - k.z) < 13 + max(w, d) / 2 for k in keep_clear):
        continue
    if any(abs(x - b[0]) < 22 and abs(z - b[1]) < 22 for b in buildings):
        continue
    buildings.append((x, z, w / 2, d / 2, h))
    shade = rng.randint(90, 170)
    Entity(model="cube", origin_y=-.5, position=(x, 0, z), scale=(w, h, d),
           texture="white_cube", texture_scale=(w / 2, h / 2),
           color=C(shade, shade + 10, shade + 25))


def floor_at(x, z, prev_y):
    """Support height under (x,z). None means the drone hit a building wall."""
    base = 0.1 if any(math.hypot(x - p.x, z - p.z) < PAD_R for _, p in PADS) else 0.0
    for bx, bz, hw, hd, h in buildings:
        if abs(x - bx) < hw + .5 and abs(z - bz) < hd + .5:
            if prev_y >= h - .15:
                base = max(base, h)
            else:
                return None
    return base


# --------------------------------------------------------------------- HUD
scenery(buildings, keep_clear)
dots = draw_track(rings)
stars, moon = sky_extras()
Entity.default_shader = unlit_shader   # HUD / minimap stay flat-shaded
Entity(parent=camera.ui, model="quad", color=C(0, 0, 0, 110), origin=(-.5, .5),
       position=window.top_left + Vec2(.01, -.01), scale=(.36, .37), z=1)
flash = Entity(parent=camera.ui, model="quad", scale=(3, 2), color=C(255, 40, 20, 0), z=-.9)
pop_txt = Text(parent=camera.ui, text=" ", origin=(0, 0), position=(0, .12), scale=2.5, color=color.lime)
hud = Text(parent=camera.ui, position=window.top_left + Vec2(.02, -.02), scale=1.3,
           origin=(-.5, .5), color=color.white)
score_txt = Text(parent=camera.ui, position=(0, .47), origin=(0, 0), scale=1.8, color=color.yellow)
msg_txt = Text(parent=camera.ui, position=(0, .30), origin=(0, 0), scale=2, color=color.white)
Entity(parent=camera.ui, model="quad", color=color.black66, position=(.8, -.25), scale=(.035, .3))
thr_fill = Entity(parent=camera.ui, model="quad", color=color.orange, origin=(0, -.5),
                  position=(.8, -.4), scale=(.03, .01))
Entity(parent=camera.ui, model="quad", color=color.white, position=(.8, -.25), scale=(.05, .003))
Text("THR", parent=camera.ui, position=(.78, -.42), scale=1, color=color.white)
help_txt = Text(parent=camera.ui, position=(-.85, .2), origin=(-.5, .5), scale=1.2,
                background=True, color=color.white, text=(
    "CONTROLS\n"
    "SPACE / L-SHIFT  throttle up / down (hover ~50%)\n"
    "W / S            pitch forward / back\n"
    "A / D            roll left / right\n"
    "Q / E            yaw left / right\n"
    "R reset drone   T full reset   C camera   H help   ESC quit\n"
    "F altitude-hold assist (release SPACE/SHIFT to hover)\n"
    "M timed MISSION (3-2-1 start): fly the gates IN ORDER, then land\n"
    "L day / night mode   N music on / off\n\n"
    "Fly through the numbered rings IN ORDER (1 to 8) along the cyan path,\nthen land softly (<4.5 m/s, <15 deg tilt)\n"
    "on pads for precision points. Landing on a pad recharges battery."))

S = {"score": 0, "msg_t": 0.0, "time": 0.0, "mission": False, "mtime": 0.0, "assist": False, "wrong_t": 0.0}
POP = {"t": 0.0}

# ---- persistent best score / best mission time
SAVE = os.path.join(os.path.expanduser("~"), "drone_sim_scores.json")
try:
    BEST = json.load(open(SAVE))
except Exception:
    BEST = {"score": 0, "time": None}


def record():
    BEST["score"] = max(BEST["score"], S["score"])
    try:
        json.dump(BEST, open(SAVE, "w"))
    except Exception:
        pass


# ---- minimap (top-right, north = up) + beacon beam over the next ring
K = .32 / (2 * WORLD_LIMIT)
MC = window.top_right + Vec2(-.2, -.2)


def mm(x, z, sx, sy, col, zz=-.01):
    return Entity(parent=camera.ui, model="quad", color=col, scale=(sx, sy),
                  position=(MC.x + x * K, MC.y + z * K, zz))


mm(0, 0, .32, .32, C(0, 0, 0, 150), 0)
for bx, bz, hw, hd, h in buildings:
    mm(bx, bz, max(2 * hw * K, .004), max(2 * hd * K, .004), color.gray)
for _, pp in PADS:
    mm(pp.x, pp.z, .012, .012, color.azure)
ring_dots = [mm(r.x, r.z, .009, .009, color.orange, -.02) for r in rings]
me = mm(0, 0, .011, .011, color.white, -.03)
nose = mm(0, 0, .007, .007, color.red, -.04)
beam = Entity(model="cube", scale=(.5, 140, .5), color=C(255, 230, 0, 80))


def say(text, col=color.white, secs=2.5):
    msg_txt.text, msg_txt.color, S["msg_t"] = text, col, secs


# ------------------------------------------------------------------- drone
class Drone(Entity):
    def __init__(self):
        super().__init__(position=SPAWN)
        self.tilt = Entity(parent=self)
        t = self.tilt
        dk, gr = C(35, 38, 45), C(60, 64, 72)
        Entity(parent=t, model="cube", scale=(.42, .12, .55), y=.16, color=dk)                     # fuselage
        Entity(parent=t, model="cube", scale=(.3, .08, .3), y=.24, color=C(200, 60, 30))  # top shell
        Entity(parent=t, model="sphere", scale=.13, position=(0, .1, .3), color=color.black)      # gimbal camera
        Entity(parent=t, model="cube", scale=(1.25, .045, .09), y=.17, rotation_y=45, color=gr)
        Entity(parent=t, model="cube", scale=(1.25, .045, .09), y=.17, rotation_y=-45, color=gr)
        for sx in (-1, 1):  # landing skids + legs
            Entity(parent=t, model="cube", scale=(.03, .03, .6), position=(sx * .2, .02, 0), color=color.dark_gray)
            for sz in (-1, 1):
                Entity(parent=t, model="cube", scale=(.03, .16, .03), position=(sx * .2, .1, sz * .2), color=color.dark_gray)
        self.blades, self.discs, self.leds, self.puffs = [], [], [], []
        for sx in (-1, 1):
            for sz in (-1, 1):
                Entity(parent=t, model="cube", scale=(.1, .12, .1), position=(sx * .46, .14, sz * .46), color=color.black)
                self.blades.append(Entity(parent=t, model="cube", scale=(.6, .015, .05),
                                          position=(sx * .46, .21, sz * .46), color=color.light_gray))
                self.discs.append(Entity(parent=t, model="circle", rotation_x=90, scale=.62,
                                         position=(sx * .46, .215, sz * .46), color=C(230, 230, 230, 0)))
                self.leds.append(Entity(parent=t, model="sphere", scale=.06, position=(sx * .46, .09, sz * .46),
                                        color=color.green if sz > 0 else color.red, shader=unlit_shader))
        self.shake = self.flash_a = 0.0
        self.flash_col = (255, 40, 20)
        self.glow = Entity(parent=t, model="sphere", scale=.7, y=.05, color=C(60, 200, 255, 70),
                           shader=unlit_shader, enabled=False)   # night underglow
        self.shadow = Entity(model="circle", rotation_x=90, color=C(0, 0, 0, 120))
        self.debris = []
        self.cam_mode = 0
        self.reset()

    def reset(self):
        self.position = SPAWN
        self.vel = Vec3(0, 0, 0)
        self.yaw = self.pitch = self.roll = 0.0
        self.throttle = self.thrust = 0.0
        self.battery = 100.0
        self.crashed = self.landed = False
        for r in rings:
            r.prev = None
        self.rotation_y = 0
        self.tilt.rotation = (0, 0, 0)
        for d in self.debris:
            destroy(d)
        self.debris = []
        camera.fov = 90
        self.visible = True
        msg_txt.text = ""

    # thrust axis in world space (unambiguous: forward/right built from yaw)
    def up_vec(self):
        p, r = math.radians(self.pitch), math.radians(self.roll)
        lx, ly, lz = math.sin(r), math.cos(p) * math.cos(r), math.sin(p)
        n = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / n, ly / n, lz / n
        y = math.radians(self.yaw)
        fwd, right = Vec3(math.sin(y), 0, math.cos(y)), Vec3(math.cos(y), 0, -math.sin(y))
        return right * lx + Vec3(0, ly, 0) + fwd * lz

    def crash(self, why):
        self.crashed = True
        self.visible = False
        self.shadow.visible = False
        record()
        SND["motor"].setVolume(0)
        SND["wind"].setVolume(0)
        SND["crash"].play()
        self.shake, self.flash_a, self.flash_col = 1.2, 170, (255, 40, 20)
        S["mission"] = False
        S["score"] = max(0, S["score"] - 50)
        say(f"CRASHED: {why}   (R to reset)", color.red, 999)
        for _ in range(28):
            d = Entity(model="cube", position=self.position + Vec3(0, .2, 0), scale=rng.uniform(.06, .2),
                       color=rng.choice([color.orange, color.red, color.dark_gray, color.yellow]))
            d.v = Vec3(rng.uniform(-4, 4), rng.uniform(2, 7), rng.uniform(-4, 4))
            self.debris.append(d)

    def update(self):
        dt = min(time.dt, 1 / 30)
        S["time"] += dt
        if S["mission"]:
            S["mtime"] += dt
        S["msg_t"] -= dt
        S["wrong_t"] -= dt
        if S["msg_t"] <= 0 and not self.crashed:
            msg_txt.text = ""
        for d in self.debris:  # explosion debris
            d.v.y -= G * dt
            d.position += d.v * dt
            if d.y < .05:
                d.y, d.v = .05, Vec3(0, 0, 0)
        if self.crashed:
            self.camera_update(dt)
            self.cam_shake(dt)
            return

        # ---- pilot input
        hk = held_keys
        self.throttle = clamp(self.throttle + (hk["space"] - hk["left shift"]) * THROTTLE_RATE * dt, 0, 1)
        if S["assist"] and not self.landed and not (hk["space"] or hk["left shift"]):
            cosa = max(.5, math.cos(math.radians(self.pitch)) * math.cos(math.radians(self.roll)))
            self.throttle += (clamp(.5 / cosa - self.vel.y * .12, 0, 1) - self.throttle) * min(1, 5 * dt)
        self.yaw += (hk["e"] - hk["q"]) * YAW_RATE * dt
        want_p = (hk["w"] - hk["s"]) * MAX_TILT
        want_r = (hk["d"] - hk["a"]) * MAX_TILT
        if self.landed and self.thrust < .55:
            want_p = want_r = 0
        k = min(1, 7 * dt)  # attitude response
        self.pitch += (want_p - self.pitch) * k
        self.roll += (want_r - self.roll) * k

        # ---- battery
        self.battery = max(0, self.battery - (.15 + self.throttle * .6) * dt)
        cmd = self.throttle if self.battery > 0 else 0
        self.thrust += (cmd - self.thrust) * min(1, 9 * dt)  # motor lag

        # ---- forces: thrust (2g at full throttle => hover at 50%), gravity, drag, light wind
        up = self.up_vec()
        acc = up * (self.thrust * 2 * G) + Vec3(0, -G, 0)
        acc -= self.vel * (.15 + .03 * self.vel.length())
        if not self.landed:
            acc += Vec3(math.sin(S["time"] * .3), 0, math.cos(S["time"] * .23)) * .35
        prev_y = self.y
        self.vel += acc * dt
        self.position += self.vel * dt
        self.x, self.z = clamp(self.x, -WORLD_LIMIT, WORLD_LIMIT), clamp(self.z, -WORLD_LIMIT, WORLD_LIMIT)

        # ---- collisions / landing
        fl = floor_at(self.x, self.z, prev_y)
        if fl is None:
            self.crash("hit a building")
            return
        tilt_deg = math.degrees(math.acos(clamp(up.y, -1, 1)))
        if self.y <= fl:
            if self.vel.y < 0:
                hs = Vec3(self.vel.x, 0, self.vel.z).length()
                if -self.vel.y > MAX_LAND_SPEED:
                    return self.crash(f"hard landing ({-self.vel.y:.1f} m/s)")
                if tilt_deg > MAX_LAND_TILT:
                    return self.crash(f"tilted landing ({tilt_deg:.0f} deg)")
                if hs > MAX_LAND_HSPEED:
                    return self.crash("landed too fast sideways")
                if not self.landed:
                    self.on_touchdown()
            self.y, self.vel.y, self.landed = fl, max(0, self.vel.y), True
            f = math.exp(-5 * dt)
            self.vel.x, self.vel.z = self.vel.x * f, self.vel.z * f
        else:
            self.landed = False
        self.check_rings()
        self.check_pads_rearm()

        # ---- visuals
        self.rotation_y = self.yaw
        self.tilt.rotation_x, self.tilt.rotation_z = self.pitch, self.roll
        for i, b in enumerate(self.blades):
            b.rotation_y += (1900 * self.thrust + 300 * (self.battery > 0)) * dt * (1 if i % 2 else -1)
        self.shadow.position = Vec3(self.x, fl + .03, self.z)
        alt = max(0, self.y - fl)
        self.shadow.scale = 1.1 + alt * .04
        self.shadow.color = C(0, 0, 0, int(max(20, 130 - alt * 3)))
        self.update_hud(alt)
        self.fx_update(dt, alt)
        self.camera_update(dt)
        self.cam_shake(dt)

    def cam_shake(self, dt):
        amt = self.shake + max(0, self.vel.length() - 14) * .012
        self.shake = max(0, self.shake - 1.5 * dt)
        self.flash_a = max(0, self.flash_a - 250 * dt)
        flash.color = C(*self.flash_col, int(self.flash_a))
        if POP["t"] > 0:
            POP["t"] -= dt
            k = max(0, POP["t"])
            pop_txt.color = C(140, 255, 140, int(255 * min(1, k * 2)))
            pop_txt.scale = 2.2 + (1 - k) * 1.2
            pop_txt.y = .12 + (1 - k) * .06
        elif pop_txt.text != " ":
            pop_txt.text = " "
        if amt > 0:
            camera.position += Vec3(rng.uniform(-1, 1), rng.uniform(-1, 1), 0) * amt * .3

    def fx_update(self, dt, alt):
        spd = self.vel.length()
        for d in self.discs:  # spinning-prop blur
            d.color = C(230, 230, 230, int(90 * self.thrust))
        blink = int(S["time"] * 3) % 2
        for i, l in enumerate(self.leds):
            if i % 2 == 0:
                l.color = color.red if blink else C(70, 0, 0)
        # ---- sound: motor pitch follows thrust, wind follows speed, low-battery beeps
        SND["motor"].setVolume(.06 + .5 * self.thrust if self.battery > 0 else 0)
        SND["motor"].setPlayRate(.6 + 1.6 * self.thrust)
        SND["wind"].setVolume(min(1, spd / 18) * (.5 + .1 * math.sin(S["time"] * .9)) * 1.2)  # gusting
        self.glow.enabled = bool(S.get("night"))
        SND["wind"].setPlayRate(.8 + spd / 30)
        self.beep_t = getattr(self, "beep_t", 0) - dt
        if 0 < self.battery < 20 and self.beep_t <= 0:
            SND["beep"].play()
            self.beep_t = 1.5
        # ---- prop-wash dust near the ground
        if alt < 3.5 and self.thrust > .25:
            for _ in range(2):
                pf = Entity(model="sphere", shader=unlit_shader, scale=.25, color=C(190, 175, 150, 150),
                            position=(self.x + rng.uniform(-.5, .5), self.y - alt + .1, self.z + rng.uniform(-.5, .5)))
                pf.v, pf.life = Vec3(rng.uniform(-3, 3), rng.uniform(.3, 1.2), rng.uniform(-3, 3)), 0.0
                self.puffs.append(pf)
        for pf in self.puffs[:]:
            pf.life += dt
            pf.position += pf.v * dt
            pf.scale = .25 + pf.life * 1.4
            pf.color = C(190, 175, 150, int(max(0, 150 * (1 - pf.life / .9))))
            if pf.life > .9:
                destroy(pf)
                self.puffs.remove(pf)

    def on_touchdown(self):
        SND["thud"].play()
        if S["mission"] and all(r.got for r in rings) and \
                any(math.hypot(self.x - p.x, self.z - p.z) < PAD_R for _, p in PADS):
            bonus = max(0, 500 - int(S["mtime"] * 2))
            S["score"] += bonus
            S["mission"] = False
            if BEST["time"] is None or S["mtime"] < BEST["time"]:
                BEST["time"] = round(S["mtime"], 1)
            record()
            SND["fanfare"].play()
            say(f"MISSION COMPLETE in {S['mtime']:.1f}s!  +{bonus} time bonus", color.gold, 6)
            return
        for name, p in PADS:
            d = math.hypot(self.x - p.x, self.z - p.z)
            if d < PAD_R and pad_state[name]:
                pts = 50 + int(100 * (1 - d / PAD_R))
                pad_state[name] = False
                S["score"] += pts
                say(f"Landed on {name}!  +{pts}  (precision {100 - int(100 * d / PAD_R)}%)", color.lime)
                return
        say("Soft landing", color.white, 1.2)

    def check_pads_rearm(self):
        for name, p in PADS:
            if math.hypot(self.x - p.x, self.z - p.z) > PAD_R + 3 or self.y > 5:
                pad_state[name] = True
        if self.landed and self.thrust < .05 and self.battery < 100:
            if any(math.hypot(self.x - p.x, self.z - p.z) < PAD_R for _, p in PADS):
                self.battery = min(100, self.battery + 10 * time.dt)

    def check_rings(self):
        c = self.position + Vec3(0, .2, 0)
        nxt = next((r for r in rings if not r.got), None)
        for r in rings:
            y = math.radians(r.rotation_y)
            d = c - r.position
            lz = d.x * math.sin(y) + d.z * math.cos(y)   # signed distance to the ring's plane
            lx = d.x * math.cos(y) - d.z * math.sin(y)
            crossed = r.prev is not None and r.prev != lz and r.prev * lz <= 0
            r.prev = lz
            if r.got or not crossed or math.hypot(lx, d.y) > RING_R - .4:
                continue
            if r is nxt:
                self.ring_cleared(r)
            elif S["wrong_t"] <= 0:
                S["wrong_t"] = 1.5
                SND["buzz"].play()
                say(f"Wrong order! Fly through ring #{nxt.idx} first", color.red, 1.5)

    def ring_cleared(self, r):
        r.set_got(True)
        n = sum(x.got for x in rings)
        SND["chime"].setPlayRate(1 + .06 * n)   # pitch climbs with every ring
        SND["chime"].play()
        ring_burst(r.position, r.rotation_y)
        S["score"] += 100
        self.flash_a, self.flash_col = 70, (60, 255, 120)
        self.shake = max(self.shake, .25)
        POP["t"] = 1.0
        split = f"   split {S['mtime']:.1f}s" if S["mission"] else ""
        if n == len(rings):
            S["score"] += 300
            SND["fanfare"].play()
            pop_txt.text = "ALL 8 RINGS CLEARED!  +400"
            say("Now land on a pad to finish!" + split, color.gold, 4)
        else:
            pop_txt.text = f"RING {r.idx} CLEARED!  +100"
            say(f"Next: ring #{r.idx + 1}" + split, color.yellow, 1.8)

    def update_hud(self, alt):
        spd = self.vel.length()
        nxt = [r for r in rings if not r.got]
        if nxt:
            tgt = nxt[0]
            beam.enabled, beam.position = True, Vec3(tgt.x, 70, tgt.z)
            nline = f"NEXT  #{tgt.idx}  {(tgt.position - self.position).length():4.0f} m"
        else:
            beam.enabled, nline = False, "NEXT  land on a pad"
        for r, dot in zip(rings, ring_dots):
            dot.color = color.lime if r.got else color.orange
        ng = sum(r.got for r in rings)
        for r in rings:
            r.scale = 1
        if nxt:  # pulsing, flashing next gate
            tgt.scale = 1 + .08 * math.sin(S["time"] * 6)
            pc = color.white if int(S["time"] * 4) % 2 else color.gold
            for bt in tgt.bits:
                bt.color = pc
        if ng != S.get("seg"):  # show only the guide dots still ahead of you
            S["seg"] = ng
            for dd in dots:
                dd.enabled = dd.seg >= ng
                dd.scale = .55 if dd.seg == ng else .3
        me.position = Vec3(MC.x + self.x * K, MC.y + self.z * K, -.03)
        yy = math.radians(self.yaw)
        nose.position = me.position + Vec3(math.sin(yy) * .013, math.cos(yy) * .013, -.01)
        if S["score"] > BEST["score"]:
            BEST["score"] = S["score"]
        bcol = "" if self.battery > 20 else " LOW!"
        hud.text = (f"ALT   {alt:6.1f} m\nSPEED {spd * 3.6:6.1f} km/h\nV/S   {self.vel.y:+6.1f} m/s\n"
                    f"HDG   {self.yaw % 360:6.0f} deg\nTHR   {self.throttle * 100:6.0f} %\n"
                    f"BATT  {self.battery:6.0f} %{bcol}\nTIME  {S['time']:6.0f} s\n"
                    f"{nline}\nASSIST {'ON' if S['assist'] else 'off'}   {('MISSION %.1f s' % S['mtime']) if S['mission'] else ''}\n"
                    f"CAM   {['CHASE', 'FPV', 'ORBIT'][self.cam_mode]}   [H] help")
        hud.color = color.red if self.battery < 20 else color.white
        score_txt.text = (f"SCORE {S['score']}    RINGS {sum(r.got for r in rings)}/{len(rings)}    BEST {BEST['score']}"
                          + (f"    BEST TIME {BEST['time']}s" if BEST["time"] else ""))
        thr_fill.scale_y = .3 * self.throttle
        thr_fill.color = color.lime if abs(self.throttle - .5) < .06 else color.orange

    def camera_update(self, dt):
        y = math.radians(self.yaw)
        fwd = Vec3(math.sin(y), 0, math.cos(y))
        if self.cam_mode == 0:    # chase
            tgt = self.position - fwd * 9 + Vec3(0, 3.5, 0)
            camera.position = lerp(camera.position, tgt, min(1, 5 * dt))
            camera.look_at(self.position + Vec3(0, 1, 0))
            camera.fov = lerp(camera.fov, 90 + self.vel.length() * .8, min(1, 3 * dt))
        elif self.cam_mode == 1:  # FPV, camera up-tilted like a racing quad
            camera.position = self.position + fwd * .45 + Vec3(0, .3, 0)
            camera.rotation = Vec3(self.pitch - 20, self.yaw, self.roll)
            camera.fov = 110
        else:                     # high orbit
            camera.position = lerp(camera.position, self.position + Vec3(0, 55, -32), min(1, 3 * dt))
            camera.look_at(self.position)
            camera.fov = 75


Entity.default_shader = basic_lighting_shader
drone = Drone()


def begin_mission():
    if not drone.crashed:
        S["mission"] = True
        SND["chime"].setPlayRate(1.5)
        SND["chime"].play()
        say("GO!", color.lime, 1.5)


def set_night(on):
    S["night"] = on
    sky.enabled = not on
    stars.enabled = on
    tint = C(8, 10, 28) if on else C(150, 185, 225)
    window.color = scene.fog_color = tint
    amb.color = C(30, 36, 70) if on else C(95, 100, 125)
    moon.color = C(225, 230, 255) if on else C(255, 235, 170)
    try:
        sun.color = C(90, 100, 170) if on else color.white
    except Exception:
        pass


def input(key):
    if key == "escape":
        record()
        application.quit()
    elif key == "r":
        record()
        drone.reset()
    elif key == "f":
        S["assist"] = not S["assist"]
        say("Altitude-hold assist " + ("ON" if S["assist"] else "OFF"), color.cyan, 1.5)
    elif key == "m":
        drone.reset()
        S.update(score=0, time=0, mtime=0, mission=False)
        for r in rings:
            r.set_got(False)
        for i, w in enumerate(("3", "2", "1")):   # countdown
            invoke(say, w, color.gold, .9, delay=i)
            invoke(SND["beep"].play, delay=i)
        invoke(begin_mission, delay=3)
    elif key == "l":
        set_night(not S.get("night"))
    elif key == "n":
        S["music"] = not S.get("music")
        SND["music"].play() if S["music"] else SND["music"].stop()
    elif key == "t":
        S["mission"] = False
        drone.reset()
        S["score"] = 0
        for r in rings:
            r.set_got(False)
    elif key == "c":
        drone.cam_mode = (drone.cam_mode + 1) % 3
    elif key == "h":
        help_txt.enabled = not help_txt.enabled


say("Hold SPACE to lift off - hover is ~50% throttle", color.white, 5)
SND["motor"].setVolume(0)
SND["wind"].setVolume(0)
SND["motor"].play()
SND["wind"].play()
SND["music"].setVolume(.3)
SND["music"].play()
S["music"] = True
app.run()
