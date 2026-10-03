"""把 body_radius 扫描结果画成退化曲线,存 breakdown_curve.png。"""

import matplotlib.pyplot as plt
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
C_COLLAPSE = "#d03b3b"  # 状态色:critical,只用于坍缩标注


def sweep_data(spec, r_min=0.2, r_max=0.8, step=0.05):
    """计算扫描曲线:每档的 body_radius、边数、连通分支数。"""
    n_steps = round((r_max - r_min) / step) + 1
    radii, edges, comps = [], [], []
    for i in range(n_steps):
        r = round(r_min + i * step, 2)
        G = build_graph(spec, body_radius=r)
        radii.append(r)
        edges.append(G.number_of_edges())
        import networkx as nx
        comps.append(nx.number_connected_components(G))
    return radii, edges, comps


def door_thresholds(spec):
    """按门宽聚合失效半径:[(width/2, width, 同宽门数), ...] 按半径升序。"""
    by_width = {}
    for d in spec["doors"]:
        by_width[d["width"]] = by_width.get(d["width"], 0) + 1
    return sorted((w / 2, w, n) for w, n in by_width.items())


def main():
    spec = load_spec("demo.json")
    radii, edges, comps = sweep_data(spec)

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    # 左轴:边数;右轴:连通分支数(两者都是 0~6 的整数,两轴取同一量程)
    ax2 = ax.twinx()
    for axis, data, color, label in ((ax, edges, C_EDGES, "图里的边数"),
                                     (ax2, comps, C_COMPS, "连通分支数")):
        axis.plot(radii, data, color=color, linewidth=2, label=label,
                  marker="o", markersize=7, markeredgecolor=SURFACE,
                  markeredgewidth=2, solid_capstyle="round", zorder=3)
        axis.set_ylim(-0.4, 6.4)
        axis.yaxis.set_major_locator(MultipleLocator(1))
        axis.tick_params(colors=MUTED, labelsize=9)

    # 每扇门的失效半径:竖虚线 + 门宽标注(同宽合并,标注 ×N)
    label_heights = [6.0, 5.4, 4.8, 6.0]  # 0.35/0.40/0.45 挨得近,标注错开高度
    for (thr, width, count), h in zip(door_thresholds(spec), label_heights):
        ax.axvline(thr, color=MUTED, linewidth=1, linestyle="--", alpha=0.7, zorder=1)
        suffix = f" ×{count}" if count > 1 else ""
        ax.text(thr, h, f"{width}m{suffix}", ha="center", va="top",
                fontsize=8.5, color=INK_2,
                bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.5))

    # 坍缩点:r=0.45→0.50,两条 0.9 通路同刻失效,bedroom1 断开
    ax.axvspan(0.45, 0.50, color=C_COLLAPSE, alpha=0.10, zorder=0)
    ax.annotate("环路坍缩:两扇 0.9m 门同刻失效,\nbedroom1 与入口断开",
                xy=(0.475, 2.0), xytext=(0.555, 3.3),
                fontsize=9, color=INK, ha="left",
                arrowprops=dict(arrowstyle="->", color=INK_2, linewidth=1))

    # 轴、网格、图例
    ax.set_xlabel("body_radius(米)", fontsize=10, color=INK_2)
    ax.set_ylabel("图里的边数", fontsize=10, color=INK_2)
    ax2.set_ylabel("连通分支数", fontsize=10, color=INK_2)
    ax.set_xticks(radii)
    ax.set_xticklabels([f"{r:.2f}" for r in radii], fontsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax2.grid(False)
    for spine in ("top",):
        ax.spines[spine].set_visible(False)
        ax2.spines[spine].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower center", bbox_to_anchor=(0.5, 1.01),
              ncol=2, frameon=False, fontsize=10)
    ax.set_title("body_radius 扫描:门宽约束下的图退化", fontsize=13,
                 color=INK, pad=30)

    fig.savefig("breakdown_curve.png", bbox_inches="tight",
                facecolor=fig.get_facecolor())
    print("已保存 breakdown_curve.png")


if __name__ == "__main__":
    main()
