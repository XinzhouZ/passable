"""建筑平面拓扑:读 JSON 规格建 NetworkX 无向图,按身体半径扫描门的可通行性。

用法(仓库根目录):python src/topology.py [specs/xxx.json](默认 specs/demo.json)
终端照常打印三张表,同时各存一份 CSV 到 outputs/:doors_<规格名>.csv、
sweep_<规格名>.csv、impacts_<规格名>.csv(utf-8-sig 编码,Excel 直接打开不乱码)。
"""

import csv
import itertools
import json
import sys
from pathlib import Path

import networkx as nx


def load_spec(path):
    """读取 JSON 规格文件,返回 dict。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_graph(spec, body_radius=0.3, margin=0.0):
    """把规格转成无向图:节点 = 房间(带矩形范围),边 = 门(带位置和宽度)。

    body_radius: 通行者半径(米)。
    margin: 安全裕量(米),默认 0。建边规则:width >= 2*body_radius + margin。

    压线档警告:width 恰好等于 2*body_radius 时,真值检验(truth_check.py,
    MiniWorld 实测 60 次)发现结局由 ~1e-16 的浮点舍入决定——门洞端点坐标
    的 portal 算术路径不同,名义相同的缺口有的能过有的被拦。该点应视为
    未定区;需要保守结论时给正的 margin(如 0.01),把压线档显式判为不过。
    """
    G = nx.Graph()
    for room in spec["rooms"]:
        G.add_node(room["id"], min_x=room["min_x"], max_x=room["max_x"],
                   min_z=room["min_z"], max_z=room["max_z"])
    for door in spec["doors"]:
        if door["width"] < 2 * body_radius + margin:
            continue
        G.add_edge(door["a"], door["b"], pos=door["pos"], width=door["width"])
    return G


def write_csv(path, header, rows):
    """utf-8-sig 写 CSV,Excel 直接打开不乱码。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


# ---------------------------------------------------------------- 门清单

def door_rows(spec):
    """门清单行:(a, b, 宽度, 失效半径),按失效半径升序,同宽保持 JSON 顺序。"""
    doors = sorted(spec["doors"], key=lambda d: d["width"] / 2)
    return [(d["a"], d["b"], d["width"], d["width"] / 2) for d in doors]


def print_door_thresholds(rows):
    """打印门清单。失效半径 = width/2:body_radius 恰好等于它时仍可通行
    (规则是严格小于),一旦超过,这扇门在图中就不存在了。"""
    print(f"{'门':<24} {'宽度':>4}  失效半径")
    for a, b, width, thr in rows:
        print(f"{a + ' <-> ' + b:<24} {width:>4.2f}  {thr:>6.2f}")


# ---------------------------------------------------------------- 扫描

def sweep_rows(spec, r_min=0.2, r_max=0.8, step=0.05):
    """扫描行:(r, 边数, 连通分支数, 不可达房间列表)。"""
    n_steps = round((r_max - r_min) / step) + 1
    rows = []
    for i in range(n_steps):
        r = round(r_min + i * step, 2)  # 取两位小数,避免浮点累加污染边界判断
        G = build_graph(spec, body_radius=r)
        reachable = nx.shortest_path_length(G, source=spec["start"])
        unreachable = [node for node in G.nodes if node not in reachable]
        rows.append((r, G.number_of_edges(),
                     nx.number_connected_components(G), unreachable))
    return rows


def print_sweep(rows, start):
    print(f"{'r':>5}  {'边数':>4}  {'分支':>4}  不可达房间(入口: {start})")
    for r, edges, comps, unreachable in rows:
        unreachable_str = ", ".join(unreachable) if unreachable else "-"
        print(f"{r:>5.2f}  {edges:>4}  {comps:>4}  {unreachable_str}")


# ---------------------------------------------------------------- 扰动

def edge_impacts(spec, body_radius=0.3):
    """对图里每条边,计算拆掉它之后的影响,按影响从大到小排序。

    约定:房间对不可达时,距离按 n(节点数)记惩罚——否则拆掉桥边后
    可达对变少,"两两最短路总和"反而缩小,排序会撒谎。平均深度同理。
    返回 (基准指标, [(边, Δ最短路总和, Δ平均深度, Δ连通分支), ...])。
    """
    G = build_graph(spec, body_radius=body_radius)
    n = G.number_of_nodes()
    start = spec["start"]

    def metrics(g):
        total = 0
        for u, v in itertools.combinations(g.nodes, 2):
            try:
                total += nx.shortest_path_length(g, u, v)
            except nx.NetworkXNoPath:
                total += n
        depth_sum = 0
        for room in g.nodes:
            try:
                depth_sum += nx.shortest_path_length(g, start, room)
            except nx.NetworkXNoPath:
                depth_sum += n
        return total, depth_sum / n, nx.number_connected_components(g)

    base = metrics(G)
    rows = []
    for e in G.edges:
        g2 = G.copy()
        g2.remove_edge(*e)
        total, avg_depth, comps = metrics(g2)
        rows.append((e, total - base[0], avg_depth - base[1], comps - base[2]))
    rows.sort(key=lambda r: (r[1], r[2], r[3]), reverse=True)
    return base, rows


def print_edge_impacts(base, rows, body_radius=0.3):
    print(f"基准(body_radius={body_radius}):边数 {len(rows)} | "
          f"两两最短路总和 {base[0]} | 平均深度 {base[1]:.3f} | 连通分支 {base[2]}")
    print(f"{'拆除的门':<24} {'Δ最短路总和':>9}  {'Δ平均深度':>9}  {'Δ连通分支':>6}")
    for (u, v), d_sum, d_depth, d_comp in rows:
        comp_str = f"{d_comp:+d}" if d_comp else "0"
        print(f"{u + ' <-> ' + v:<24} {d_sum:>+9}  {d_depth:>+9.3f}  {comp_str:>6}")


# ---------------------------------------------------------------- 主流程

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "specs/demo.json"
    stem = Path(path).stem
    spec = load_spec(path)
    Path("outputs").mkdir(exist_ok=True)

    doors = door_rows(spec)
    print_door_thresholds(doors)
    write_csv(f"outputs/doors_{stem}.csv",
              ["a", "b", "width_m", "fail_radius_m"], doors)
    print()

    sweep = sweep_rows(spec)
    print_sweep(sweep, spec["start"])
    write_csv(f"outputs/sweep_{stem}.csv",
              ["body_radius_m", "edges", "components", "unreachable"],
              [(r, e, c, ";".join(u)) for r, e, c, u in sweep])
    print()

    base, impacts = edge_impacts(spec)
    print_edge_impacts(base, impacts)
    write_csv(f"outputs/impacts_{stem}.csv",
              ["a", "b", "delta_sum", "delta_avg_depth", "delta_components",
               "base_sum", "base_avg_depth", "base_components"],
              [(a, b, d_sum, d_depth, d_comp, base[0], base[1], base[2])
               for (a, b), d_sum, d_depth, d_comp in impacts])


if __name__ == "__main__":
    main()
