"""建筑平面拓扑:读 JSON 规格建 NetworkX 无向图,按身体半径扫描门的可通行性。

用法:python topology.py [spec.json](默认 demo.json)
"""

import itertools
import json
import sys

import networkx as nx


def load_spec(path):
    """读取 JSON 规格文件,返回 dict。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_graph(spec, body_radius=0.3):
    """把规格转成无向图:节点 = 房间(带矩形范围),边 = 门(带位置和宽度)。

    body_radius: 通行者半径(米)。门洞宽度小于 2*body_radius 视为挤不过去,不建边。
    """
    G = nx.Graph()
    for room in spec["rooms"]:
        G.add_node(room["id"], min_x=room["min_x"], max_x=room["max_x"],
                   min_z=room["min_z"], max_z=room["max_z"])
    for door in spec["doors"]:
        if door["width"] < 2 * body_radius:
            continue
        G.add_edge(door["a"], door["b"], pos=door["pos"], width=door["width"])
    return G


def print_door_thresholds(spec):
    """打印每扇门:连接的房间、宽度、失效半径。

    失效半径 = width/2:body_radius 恰好等于它时仍可通行(规则是严格小于),
    一旦超过,这扇门在图中就不存在了。
    """
    doors = sorted(spec["doors"], key=lambda d: d["width"] / 2)  # 稳定排序,同宽保持 JSON 顺序
    print(f"{'门':<24} {'宽度':>4}  失效半径")
    for d in doors:
        pair = f"{d['a']} <-> {d['b']}"
        print(f"{pair:<24} {d['width']:>4.2f}  {d['width'] / 2:>6.2f}")


def sweep_body_radius(spec, r_min=0.2, r_max=0.8, step=0.05):
    """扫描 body_radius,每档打印:剩余边数、连通分支数、入口不可达的房间。"""
    n_steps = round((r_max - r_min) / step) + 1
    print(f"{'r':>5}  {'边数':>4}  {'分支':>4}  不可达房间(入口: {spec['start']})")
    for i in range(n_steps):
        r = round(r_min + i * step, 2)  # 取两位小数,避免浮点累加污染边界判断
        G = build_graph(spec, body_radius=r)
        reachable = nx.shortest_path_length(G, source=spec["start"])
        unreachable = [n for n in G.nodes if n not in reachable]
        unreachable_str = ", ".join(unreachable) if unreachable else "-"
        print(f"{r:>5.2f}  {G.number_of_edges():>4}  "
              f"{nx.number_connected_components(G):>4}  {unreachable_str}")


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


def print_edge_impacts(spec, body_radius=0.3):
    """打印拆边影响报告。"""
    base, rows = edge_impacts(spec, body_radius)
    print(f"基准(body_radius={body_radius}):边数 {len(rows)} | "
          f"两两最短路总和 {base[0]} | 平均深度 {base[1]:.3f} | 连通分支 {base[2]}")
    print(f"{'拆除的门':<24} {'Δ最短路总和':>9}  {'Δ平均深度':>9}  {'Δ连通分支':>6}")
    for (u, v), d_sum, d_depth, d_comp in rows:
        comp_str = f"{d_comp:+d}" if d_comp else "0"
        print(f"{u + ' <-> ' + v:<24} {d_sum:>+9}  {d_depth:>+9.3f}  {comp_str:>6}")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "demo.json"
    spec = load_spec(path)
    print_door_thresholds(spec)
    print()
    sweep_body_radius(spec)
    print()
    print_edge_impacts(spec)


if __name__ == "__main__":
    main()
