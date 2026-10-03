"""真值检验:图预测 vs MiniWorld 实测通行。

对规格里每扇门 × 每个身体半径:
  reset 世界 → place_agent 到门洞一侧(离墙 APPROACH、正对门洞中心)→
  连续 move_forward → 用 Room.point_inside 判断是否到达对面房间。
图预测规则与 topology.build_graph 一致:width >= 2*radius 即可过。

用法:python truth_check.py [spec.json](默认 flat130.json)
"""

import sys

import numpy as np
from miniworld.miniworld import MiniWorldEnv

from topology import load_spec
from world import SpecWorld

EPS = 1e-6
RADII = [0.3, 0.35, 0.4, 0.45, 0.5]
APPROACH = 0.3   # 起点离墙距离(米,本侧房间内)
MAX_STEPS = 40   # 每次穿越尝试的最大步数(每步前进约 0.15m)

# 源码 entity.py:96-103:dir_vec = [cos(dir), 0, -sin(dir)],注意 z 是负 sin
# (orient, a 所在一侧)→ 正对墙的朝向角
FACING = {("x", +1): 0.0, ("x", -1): np.pi,
          ("z", +1): -np.pi / 2, ("z", -1): np.pi / 2}


def shared_wall(a, b):
    """两房间的共享墙:返回 (朝向, 坐标)。与 world.py 同一套判定。"""
    if abs(a["max_x"] - b["min_x"]) < EPS or abs(b["max_x"] - a["min_x"]) < EPS:
        return "x", a["max_x"] if abs(a["max_x"] - b["min_x"]) < EPS else b["max_x"]
    if abs(a["max_z"] - b["min_z"]) < EPS or abs(b["max_z"] - a["min_z"]) < EPS:
        return "z", a["max_z"] if abs(a["max_z"] - b["min_z"]) < EPS else b["max_z"]
    raise ValueError(f"房间 {a['id']} 和 {b['id']} 没有共享墙")


def crossing_pose(a, b, door):
    """起点(a 侧、离墙 APPROACH、门洞中心线上)与正对墙的朝向,返回 (pos, dir, 对面id)。"""
    orient, coord = shared_wall(a, b)
    if orient == "x":
        side = +1 if abs(a["max_x"] - coord) < EPS else -1
        start = np.array([coord - side * APPROACH, 0.0, door["pos"]])
    else:
        side = +1 if abs(a["max_z"] - coord) < EPS else -1
        start = np.array([door["pos"], 0.0, coord - side * APPROACH])
    return start, FACING[(orient, side)], b["id"]


def rooms_by_rect(env):
    """Room 对象不带 id,按矩形范围和规格对上。"""
    mapping = {}
    for r in env.spec["rooms"]:
        for room in env.rooms:
            if (abs(room.min_x - r["min_x"]) < EPS and abs(room.max_x - r["max_x"]) < EPS
                    and abs(room.min_z - r["min_z"]) < EPS
                    and abs(room.max_z - r["max_z"]) < EPS):
                mapping[r["id"]] = room
                break
        else:
            raise RuntimeError(f"房间里找不到 {r['id']}")
    return mapping


def try_cross(env, rooms, start, direction, target_id):
    target = rooms[target_id]
    env.place_agent(pos=start, dir=direction)
    for _ in range(MAX_STEPS):
        env.step(MiniWorldEnv.Actions.move_forward)
        if target.point_inside(env.agent.pos):
            return True
    return False


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "flat130.json"
    spec = load_spec(path)
    rects = {r["id"]: r for r in spec["rooms"]}

    env = SpecWorld(spec)  # 不弹窗:只用离屏渲染,不设 render_mode

    rows = []
    for radius in RADII:
        env.body_radius = radius
        env.reset()          # reset 会重建 agent 并按 body_radius 设半径
        rooms = rooms_by_rect(env)
        for d in spec["doors"]:
            start, direction, target_id = crossing_pose(
                rects[d["a"]], rects[d["b"]], d)
            reached = try_cross(env, rooms, start, direction, target_id)
            predicted = d["width"] >= 2 * radius
            rows.append((d["a"], d["b"], d["width"], radius, predicted, reached))
    env.close()

    print(f"{'边':<26} {'门宽':>5} {'半径':>5}  图预测  实测  一致")
    mismatches = []
    last_pair = None
    for a, b, w, r, pred, real in rows:
        if (a, b) != last_pair:
            print(f"{'— ' + a + ' ↔ ' + b + ' —':<30}")
            last_pair = (a, b)
        ok = pred == real
        mismatches.append((a, b, w, r, pred, real)) if not ok else None
        print(f"{w:>9.2f}m {r:>6.2f}m   {'可过' if pred else '不过':^4}   "
              f"{'可过' if real else '不过':^4}    {'✓' if ok else '✗'}")

    print(f"\n共 {len(rows)} 次试验,不一致 {len(mismatches)} 行")
    for a, b, w, r, pred, real in mismatches:
        verdict = "图说能过但走不过去" if pred else "图说过不去但走过去了"
        print(f"  {a} <-> {b}  宽 {w:.2f}m  r={r:.2f}  {verdict}")


if __name__ == "__main__":
    main()
