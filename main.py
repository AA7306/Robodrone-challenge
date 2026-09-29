"""Drone Flight Training Simulator - Python + Ursina (Panda3D)."""
import json
import math
import os
import random
from ursina import *

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
window.color = color.rgb(120, 170, 230)
Sky()
rng = random.Random(42)

# ------------------------------------------------------------------- world
Entity(model="plane", scale=600, texture="white_cube", texture_scale=(150, 150),
       color=color.rgb(70, 120, 60))

pad_state = {}
for name, p in PADS:
    Entity(model="circle", position=p + Vec3(0, .04, 0), rotation_x=90,
           scale=PAD_R * 2, color=color.rgb(230, 230, 230))
    Entity(model="circle", position=p + Vec3(0, .05, 0), rotation_x=90,
           scale=PAD_R * 1.4, color=color.azure if name == "HOME" else color.violet)
    Entity(model="circle", position=p + Vec3(0, .06, 0), rotation_x=90,
           scale=PAD_R * .5, color=color.white)
    Text(name, parent=scene, position=p + Vec3(-1.2, 0.08, -PAD_R - .4), rotation_x=90,
         scale=14, color=color.black)
    pad_state[name] = True  # armed for scoring


class Ring(Entity):
    def __init__(self, pos, yaw):
        super().__init__(position=pos, rotation_y=yaw)
        self.got = False
        self.bits = []
        for i in range(24):
            a = i / 24 * math.tau
            self.bits.append(Entity(parent=self, model="cube", color=color.orange,
                                    position=(math.cos(a) * RING_R, math.sin(a) * RING_R, 0),
                                    scale=.55, rotation_z=math.degrees(a)))

    def set_got(self, v):
        self.got = v
        for b in self.bits:
            b.color = color.lime if v else color.orange


rings = []
for i in range(8):
    ang = i * 45 + 10
    r = 40 + i * 12
    pos = Vec3(math.sin(math.radians(ang)) * r, 6 + (i % 4) * 4.5, math.cos(math.radians(ang)) * r)
    rings.append(Ring(pos, ang))

keep_clear = [p for _, p in PADS] + [r.position for r in rings]
buildings = []  # (x, z, half_w, half_d, height)
tries = 0
while len(buildings) < 30 and tries < 2000:
    tries += 1
    x, z = rng.uniform(-250, 250), rng.uniform(-250, 250)
    w, d, h = rng.uniform(6, 14), rng.uniform(6, 14), rng.uniform(10, 45)
    if math.hypot(x, z) < 16 or any(math.hypot(x - k.x, z - k.z) < 13 + max(w, d) / 2 for k in keep_clear):
        continue
    if any(abs(x - b[0]) < 22 and abs(z - b[1]) < 22 for b in buildings):
        continue
    buildings.append((x, z, w / 2, d / 2, h))
    shade = rng.randint(90, 170)
    Entity(model="cube", origin_y=-.5, position=(x, 0, z), scale=(w, h, d),
           texture="white_cube", texture_scale=(w / 2, h / 2),
           color=color.rgb(shade, shade + 10, shade + 25))


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
    "M timed MISSION: clear all rings, then land on a pad\n\n"
    "Fly through orange rings, land softly (<4.5 m/s, <15 deg tilt)\n"
    "on pads for precision points. Landing on a pad recharges battery."))

S = {"score": 0, "msg_t": 0.0, "time": 0.0, "mission": False, "mtime": 0.0, "assist": False}

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


mm(0, 0, .32, .32, color.rgba(0, 0, 0, 150), 0)
for bx, bz, hw, hd, h in buildings:
    mm(bx, bz, max(2 * hw * K, .004), max(2 * hd * K, .004), color.gray)
for _, pp in PADS:
    mm(pp.x, pp.z, .012, .012, color.azure)
ring_dots = [mm(r.x, r.z, .009, .009, color.orange, -.02) for r in rings]
me = mm(0, 0, .011, .011, color.white, -.03)
nose = mm(0, 0, .007, .007, color.red, -.04)
beam = Entity(model="cube", scale=(.5, 140, .5), color=color.rgba(255, 230, 0, 80))


def say(text, col=color.white, secs=2.5):
    msg_txt.text, msg_txt.color, S["msg_t"] = text, col, secs


# ------------------------------------------------------------------- drone
class Drone(Entity):
    def __init__(self):
        super().__init__(position=SPAWN)
        self.tilt = Entity(parent=self)
        t = self.tilt
        Entity(parent=t, model="cube", scale=(.5, .14, .5), y=.15, color=color.dark_gray)
        Entity(parent=t, model="cube", scale=(1.3, .05, .08), y=.15, rotation_y=45, color=color.gray)
        Entity(parent=t, model="cube", scale=(1.3, .05, .08), y=.15, rotation_y=-45, color=color.gray)
        Entity(parent=t, model="cube", scale=(.12, .1, .16), position=(0, .15, .3), color=color.lime)   # front
        Entity(parent=t, model="cube", scale=(.12, .1, .1), position=(0, .15, -.28), color=color.red)  # rear
        self.blades = []
        for sx in (-1, 1):
            for sz in (-1, 1):
                Entity(parent=t, model="cube", scale=(.08, .1, .08), position=(sx * .46, .12, sz * .46), color=color.black)
                self.blades.append(Entity(parent=t, model="cube", scale=(.55, .02, .06),
                                          position=(sx * .46, .2, sz * .46), color=color.white50))
        self.shadow = Entity(model="circle", rotation_x=90, color=color.rgba(0, 0, 0, 120))
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
        if S["msg_t"] <= 0 and not self.crashed:
            msg_txt.text = ""
        for d in self.debris:  # explosion debris
            d.v.y -= G * dt
            d.position += d.v * dt
            if d.y < .05:
                d.y, d.v = .05, Vec3(0, 0, 0)
        if self.crashed:
            self.camera_update(dt)
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
        self.shadow.color = color.rgba(0, 0, 0, int(max(20, 130 - alt * 3)))
        self.update_hud(alt)
        self.camera_update(dt)

    def on_touchdown(self):
        if S["mission"] and all(r.got for r in rings) and \
                any(math.hypot(self.x - p.x, self.z - p.z) < PAD_R for _, p in PADS):
            bonus = max(0, 500 - int(S["mtime"] * 2))
            S["score"] += bonus
            S["mission"] = False
            if BEST["time"] is None or S["mtime"] < BEST["time"]:
                BEST["time"] = round(S["mtime"], 1)
            record()
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
        for r in rings:
            if not r.got and (c - r.position).length() < RING_HIT:
                r.set_got(True)
                S["score"] += 100
                n = sum(x.got for x in rings)
                if n == len(rings):
                    S["score"] += 300
                    say("ALL RINGS CLEARED!  +300 bonus", color.gold, 4)
                else:
                    say(f"Ring {n}/{len(rings)}  +100", color.orange, 1.5)

    def update_hud(self, alt):
        spd = self.vel.length()
        nxt = [r for r in rings if not r.got]
        if nxt:
            tgt = min(nxt, key=lambda r: (r.position - self.position).length())
            beam.enabled, beam.position = True, Vec3(tgt.x, 70, tgt.z)
            nline = f"NEXT  {(tgt.position - self.position).length():6.0f} m"
        else:
            beam.enabled, nline = False, "NEXT  land on a pad"
        for r, dot in zip(rings, ring_dots):
            dot.color = color.lime if r.got else color.orange
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


drone = Drone()


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
        S.update(score=0, time=0, mtime=0, mission=True)
        for r in rings:
            r.set_got(False)
        say("MISSION: clear all 8 rings, then land on a pad. GO!", color.gold, 4)
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
app.run()
