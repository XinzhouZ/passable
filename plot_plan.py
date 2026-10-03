"""从 JSON 规格直接绘制建筑平面图:粗线墙、门洞缺口、房间名与面积、门宽标注。

独立于 MiniWorld——这是规格的"图纸上"的样子,用于和 world_top.png 肉眼比对。
用法:python plot_plan.py [spec.json](默认 demo.json)
可选的 "entrance" 字段描述入口门(入口不是房间,不进 doors):
  {"room": 房间id, "orient": "x"|"z", "coord": 墙坐标, "pos": 沿墙位置, "width": 宽}
"""

import sys

import matplotlib.pyplot as plt

from topology import load_spec

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

EPS = 1e-6
INK = "#0b0b0b"      # 墙线
INK_2 = "#52514e"    # 房间标注
MUTED = "#898781"    # 门洞与门宽
FILL = "#f9f9f7"     # 房间底色


def find_shared_wall(a, b):
    """判断两房间的共享墙。返回 (朝向, 坐标):朝向 'x' 表示墙垂直于 x(恒定 x)。"""
    if abs(a["max_x"] - b["min_x"]) < EPS or abs(b["max_x"] - a["min_x"]) < EPS:
        return "x", a["max_x"] if abs(a["max_x"] - b["min_x"]) < EPS else b["max_x"]
    if abs(a["max_z"] - b["min_z"]) < EPS or abs(b["max_z"] - a["min_z"]) < EPS:
        return "z", a["max_z"] if abs(a["max_z"] - b["min_z"]) < EPS else b["max_z"]
    raise ValueError(f"房间 {a['id']} 和 {b['id']} 没有共享墙")


def collect_gaps(spec):
    """把每扇门换算成缺口区间,登记到两个房间各自的墙上。

    返回 {room_id: {(朝向, 坐标): [(g0, g1), ...]}}:
    朝向 'x' 的墙缺口是 z 区间,朝向 'z' 的墙缺口是 x 区间。
    """
    rects = {r["id"]: r for r in spec["rooms"]}
    gaps = {r["id"]: {} for r in spec["rooms"]}
    for d in spec["doors"]:
        a, b = rects[d["a"]], rects[d["b"]]
        orient, coord = find_shared_wall(a, b)
        g0, g1 = d["pos"] - d["width"] / 2, d["pos"] + d["width"] / 2
        gaps[d["a"]].setdefault((orient, coord), []).append((g0, g1))
        gaps[d["b"]].setdefault((orient, coord), []).append((g0, g1))
    return gaps


def wall_segments(p0, p1, gaps):
    """把墙线段 p0→p1 按 gaps(沿墙方向的坐标区间)挖门洞,返回剩余小段。"""
    along = 0 if abs(p1[0] - p0[0]) > abs(p1[1] - p0[1]) else 1  # 墙沿哪个轴延伸
    fixed = p0[1 - along]
    t0, t1 = p0[along], p1[along]

    def pt(t):
        return (t, fixed) if along == 0 else (fixed, t)

    cuts = sorted((max(g0, t0), min(g1, t1)) for g0, g1 in gaps if g1 > t0 and g0 < t1)
    segs, cursor = [], t0
    for c0, c1 in cuts:
        if c0 > cursor:
            segs.append((pt(cursor), pt(c0)))
        cursor = max(cursor, c1)
    if cursor < t1:
        segs.append((pt(cursor), pt(t1)))
    return segs


def draw_plan(spec, ax):
    gaps = collect_gaps(spec)

    # 入口:不是房间,直接在指定房间的指定墙上挖缺口
    e = spec.get("entrance")
    if e:
        g0, g1 = e["pos"] - e["width"] / 2, e["pos"] + e["width"] / 2
        gaps[e["room"]].setdefault((e["orient"], e["coord"]), []).append((g0, g1))

    # 房间底色、名称与面积(窄房间缩小字号,竖向窄房旋转 90°)
    for r in spec["rooms"]:
        x0, x1 = r["min_x"], r["max_x"]
        z0, z1 = r["min_z"], r["max_z"]
        w, h = x1 - x0, z1 - z0
        ax.fill([x0, x1, x1, x0], [z0, z0, z1, z1], color=FILL, zorder=0)
        rotation = 90 if (w < h and w < 1.8) else 0
        fontsize = 8 if min(w, h) < 2.0 else 10
        ax.text((x0 + x1) / 2, (z0 + z1) / 2,
                f"{r['id']}\n{w * h:.1f} ㎡",
                ha="center", va="center", fontsize=fontsize, color=INK_2,
                rotation=rotation, zorder=3)

    # 墙:逐面画粗线,门洞处断开
    for r in spec["rooms"]:
        x0, x1, z0, z1 = r["min_x"], r["max_x"], r["min_z"], r["max_z"]
        walls = [
            ((x0, z0), (x1, z0), ("z", z0)),   # 南墙
            ((x0, z1), (x1, z1), ("z", z1)),   # 北墙
            ((x0, z0), (x0, z1), ("x", x0)),   # 西墙
            ((x1, z0), (x1, z1), ("x", x1)),   # 东墙
        ]
        for p0, p1, key in walls:
            for sa, sb in wall_segments(p0, p1, gaps[r["id"]].get(key, [])):
                ax.plot([sa[0], sb[0]], [sa[1], sb[1]], color=INK,
                        linewidth=3, solid_capstyle="butt", zorder=2)

    # 门洞:细虚线封口 + 门宽标注(每扇门只标一次)
    rects = {r["id"]: r for r in spec["rooms"]}
    for d in spec["doors"]:
        orient, coord = find_shared_wall(rects[d["a"]], rects[d["b"]])
        g0, g1 = d["pos"] - d["width"] / 2, d["pos"] + d["width"] / 2
        mid = (g0 + g1) / 2
        if orient == "x":  # 恒定 x 的墙,缺口沿 z
            ax.plot([coord, coord], [g0, g1], color=MUTED, linewidth=1,
                    linestyle=(0, (2, 2)), zorder=1)
            ax.text(coord + 0.12, mid, f"{d['width']}m", ha="left", va="center",
                    fontsize=8, color=MUTED, zorder=3)
        else:              # 恒定 z 的墙,缺口沿 x
            ax.plot([g0, g1], [coord, coord], color=MUTED, linewidth=1,
                    linestyle=(0, (2, 2)), zorder=1)
            ax.text(mid, coord + 0.12, f"{d['width']}m", ha="center", va="bottom",
                    fontsize=8, color=MUTED, zorder=3)

    # 入口:虚线封口 + 标注,文字放在墙外侧(背离房间中心一侧)
    if e:
        g0, g1 = e["pos"] - e["width"] / 2, e["pos"] + e["width"] / 2
        mid = (g0 + g1) / 2
        room_c = next(r for r in spec["rooms"] if r["id"] == e["room"])
        label = f"入口 {e['width']}m"
        if e["orient"] == "x":
            ax.plot([e["coord"], e["coord"]], [g0, g1], color=MUTED, linewidth=1,
                    linestyle=(0, (2, 2)), zorder=1)
            inward = 1 if e["coord"] <= (room_c["min_x"] + room_c["max_x"]) / 2 else -1
            ax.text(e["coord"] - 0.15 * inward, mid, label,
                    ha="right" if inward == 1 else "left", va="center",
                    fontsize=8, color=MUTED, zorder=3)
        else:
            ax.plot([g0, g1], [e["coord"], e["coord"]], color=MUTED, linewidth=1,
                    linestyle=(0, (2, 2)), zorder=1)
            inward = 1 if e["coord"] <= (room_c["min_z"] + room_c["max_z"]) / 2 else -1
            ax.text(mid, e["coord"] - 0.15 * inward, label,
                    ha="center", va="bottom" if inward == 1 else "top",
                    fontsize=8, color=MUTED, zorder=3)

    ax.set_aspect("equal")
    ax.axis("off")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "demo.json"
    spec = load_spec(path)
    fig, ax = plt.subplots(figsize=(9, 8.5), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    draw_plan(spec, ax)
    ax.set_title(f"建筑平面图({path})", fontsize=13, color=INK, pad=12)
    ax.autoscale()
    ax.margins(0.08)
    fig.savefig("plan.png", bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"已保存 plan.png({path}),{len(spec['rooms'])} 个房间,"
          f"{len(spec['doors'])} 扇门"
          + (",含入口" if spec.get("entrance") else ""))


if __name__ == "__main__":
    main()
