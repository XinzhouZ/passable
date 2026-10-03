"""把 body_radius 扫描结果画成退化曲线,存 breakdown_<规格名>.png。

用法:python plot_sweep.py [spec.json](默认 demo.json)
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.ticker import MultipleLocator

from topology import build_graph, load_spec

# 中文字体:Windows 上用微软雅黑,否则中文显示为方框
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

SURFACE = "#fcfcfb"     # 图表底色
INK = "#0b0b0b"         # 主文字
INK_2 = "#52514e"       # 次级文字
MUTED = "#898781"       # 轴/刻度
GRID = "#e1e0d9"        # 网格
C_EDGES = "#2a78d6"     # 系列1:蓝(已验证调色板 slot 1)
C_COMPS = "#eb6834"     # 系列2:橙(slot 2)
C_FALSE_RED = "#d03b3b"  # 状态色 critical:伪冗余区间
C_TRUE_GREEN = "#0ca30c"  # 状态色 good:真冗余区间

# 按规格名登记的区间标注(伪/真冗余等研究结论的视觉锚点)
ANNOTATIONS = {
    "demo": [
        {"span": (0.45, 0.50), "color": C_FALSE_RED,
         "xy": (0.475, 2.0), "xytext": (0.555, 3.3),
         "text": "环路坍缩:两扇 0.9m 门同刻失效,\nbedroom1 与入口断开"},
    ],
    "flat130": [
        {"span": (0.50, 0.65), "color": C_TRUE_GREEN,
         "xy": (0.575, 5.5), "xytext": (0.615, 2.9),
         "text": "真冗余区间:次卧南直门(0.9m)已断,\n经客厅-观景阳台(瓶颈 1.2m)仍可达"},
    ],
}


def sweep_data(spec, r_min=0.2, r_max=0.8, step=0.05):
    """计算扫描曲线:每档的 body_radius、边数、连通分支数。"""
    n_steps = round((r_max - r_min) / step) + 1
    radii, edges, comps = [], [], []
    for i in range(n_steps):
        r = round(r_min + i * step, 2)
        G = build_graph(spec, body_radius=r)
        radii.append(r)
        edges.append(G.number_of_edges())
        comps.append(nx.number_connected_components(G))
    return radii, edges, comps


def door_thresholds(spec):
    """按门宽聚合失效半径:[(width/2, width, 同宽门数), ...] 按半径升序。"""
    by_width = {}
    for d in spec["doors"]:
        by_width[d["width"]] = by_width.get(d["width"], 0) + 1
    return sorted((w / 2, w, n) for w, n in by_width.items())


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "demo.json"
    spec = load_spec(path)
    radii, edges, comps = sweep_data(spec)

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    # 左轴:边数;右轴:连通分支数(都是整数,两轴取同一量程)
    ytop = max(max(edges), max(comps)) + 1.4  # 顶部留门宽标注的空间
    ax2 = ax.twinx()
    for axis, data, color, label in ((ax, edges, C_EDGES, "图里的边数"),
                                     (ax2, comps, C_COMPS, "连通分支数")):
        axis.plot(radii, data, color=color, linewidth=2, label=label,
                  marker="o", markersize=7, markeredgecolor=SURFACE,
                  markeredgewidth=2, solid_capstyle="round", zorder=3)
        axis.set_ylim(-0.4, ytop)
        axis.yaxis.set_major_locator(MultipleLocator(1))
        axis.tick_params(colors=MUTED, labelsize=9)

    # 每扇门的失效半径:竖虚线 + 门宽标注(同宽合并 ×N,高度循环错开防重叠)
    for i, (thr, width, count) in enumerate(door_thresholds(spec)):
        if thr > radii[-1]:  # 超出扫描范围(如 1.8m 在 r=0.90 才失效),不画
            continue
        ax.axvline(thr, color=MUTED, linewidth=1, linestyle="--", alpha=0.7, zorder=1)
        suffix = f" ×{count}" if count > 1 else ""
        ax.text(thr, ytop - 0.25 - 0.55 * (i % 4), f"{width}m{suffix}",
                ha="center", va="top", fontsize=8.5, color=INK_2,
                bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.5))

    # 按规格名画区间标注
    for ann in ANNOTATIONS.get(Path(path).stem, []):
        ax.axvspan(*ann["span"], color=ann["color"], alpha=0.10, zorder=0)
        ax.annotate(ann["text"], xy=ann["xy"], xytext=ann["xytext"],
                    fontsize=9, color=INK, ha="left",
                    arrowprops=dict(arrowstyle="->", color=INK_2, linewidth=1))

    # 轴、网格、图例
    ax.set_xlabel("body_radius(米)", fontsize=10, color=INK_2)
    ax.set_ylabel("图里的边数", fontsize=10, color=INK_2)
    ax2.set_ylabel("连通分支数", fontsize=10, color=INK_2)
    ax.set_xticks(radii)
    ax.set_xticklabels([f"{r:.2f}" for r in radii], fontsize=8)
    ax.set_xlim(radii[0] - 0.04, radii[-1] + 0.04)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax2.grid(False)
    ax.spines["top"].set_visible(False)
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower center", bbox_to_anchor=(0.5, 1.01),
              ncol=2, frameon=False, fontsize=10)
    ax.set_title(f"body_radius 扫描:门宽约束下的图退化({path})",
                 fontsize=13, color=INK, pad=30)

    out = f"breakdown_{Path(path).stem}.png"
    fig.savefig(out, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"已保存 {out}({path}),r {radii[0]}~{radii[-1]},"
          f"边数峰值 {max(edges)},分支峰值 {max(comps)}")


if __name__ == "__main__":
    main()
