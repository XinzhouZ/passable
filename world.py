"""把 JSON 规格建成 MiniWorld 三维世界,渲染俯视图做肉眼比对。"""

import matplotlib.pyplot as plt
from miniworld.miniworld import MiniWorldEnv

from topology import load_spec

WALL_EPS = 1e-6  # 判断两矩形是否共享墙的容差

# 每个房间的地板纹理:俯视图里墙是侧棱对着相机、投影为零宽度,唯一能
# 区分房间的是地板。给足对比度,门洞会显示为条状的同色过道。
# 纹理名必须是 textures/ 下带 _N 后缀的文件(如 wood_1.png)。
FLOOR_TEXES = {
    "living": "floor_tiles_bw",   # 黑白棋盘
    "kitchen": "wood_planks",     # 木条
    "bedroom1": "wood",           # 木纹(主卧)
    "bedroom2": "marble",         # 大理石(次卧)
    "bathroom": "white",          # 纯白(卫生间)
    "balcony": "grass",           # 绿色(阳台,南方阳台放绿植)
}


class SpecWorld(MiniWorldEnv):
    """接受本仓库 JSON 规格的 MiniWorld 环境。

    门洞的 pos 字段 = 门洞中心在共享墙上的坐标:
    墙垂直于 x(两个房间左右相邻)时 pos 是 z 坐标,传 min_z/max_z;
    墙垂直于 z(两个房间上下相邻)时 pos 是 x 坐标,传 min_x/max_x。
    """

    def __init__(self, spec, body_radius=0.3, **kwargs):
        self.spec = spec
        self.body_radius = body_radius
        super().__init__(**kwargs)

    def _gen_world(self):
        # 房间:建矩形,保存返回的 Room 对象供 connect_rooms 使用
        rooms = {}
        for r in self.spec["rooms"]:
            rooms[r["id"]] = self.add_rect_room(
                min_x=r["min_x"], max_x=r["max_x"],
                min_z=r["min_z"], max_z=r["max_z"],
                floor_tex=FLOOR_TEXES.get(r["id"], "floor_tiles_bw"),
            )

        # 门洞:按共享墙朝向选 min/max 轴
        for d in self.spec["doors"]:
            a, b = rooms[d["a"]], rooms[d["b"]]
            half = d["width"] / 2
            pos = d["pos"]
            share_x_wall = (abs(a.max_x - b.min_x) < WALL_EPS
                            or abs(b.max_x - a.min_x) < WALL_EPS)
            share_z_wall = (abs(a.max_z - b.min_z) < WALL_EPS
                            or abs(b.max_z - a.min_z) < WALL_EPS)
            if share_x_wall:
                self.connect_rooms(a, b, min_z=pos - half, max_z=pos + half)
            elif share_z_wall:
                self.connect_rooms(a, b, min_x=pos - half, max_x=pos + half)
            else:
                raise ValueError(f"房间 {d['a']} 和 {d['b']} 没有共享墙,开不了门")

        # agent 半径在 _gen_world 里设:reset() 每次都会重建 self.agent
        self.agent.radius = self.body_radius

        # 入口房间:放在房间中心、朝东,固定不随机,保证每次渲染一致
        s = next(r for r in self.spec["rooms"] if r["id"] == self.spec["start"])
        self.place_agent(
            room=rooms[self.spec["start"]],
            pos=[(s["min_x"] + s["max_x"]) / 2, 0, (s["min_z"] + s["max_z"]) / 2],
            dir=0,
        )


class CountingSpecWorld(SpecWorld):
    """带 connect_rooms 插桩的变体:数调用次数和过道房间数。"""

    def __init__(self, *args, **kwargs):
        self.connect_calls = 0
        self.passage_rooms = 0
        super().__init__(*args, **kwargs)

    def reset(self, *args, **kwargs):
        # __init__ 里会隐式 reset 一次,main 里又显式 reset 一次,
        # 每次都清零,保证计数对应最后一次构建
        self.connect_calls = 0
        self.passage_rooms = 0
        return super().reset(*args, **kwargs)

    def connect_rooms(self, *args, **kwargs):
        self.connect_calls += 1
        n_before = len(self.rooms)
        super().connect_rooms(*args, **kwargs)
        # 源码 :834 只有过道分支才会 append 新 Room
        self.passage_rooms += len(self.rooms) - n_before


def main():
    spec = load_spec("demo.json")
    # obs_width/height 决定俯视图像素(render_top_view 默认用 obs_fb);
    # 不设 render_mode、不调 render(),只用离屏渲染,不会弹窗
    env = CountingSpecWorld(spec, obs_width=1000, obs_height=900)
    env.reset()
    img = env.render_top_view()
    plt.imsave("world_top.png", img)
    env.close()

    portal_total = sum(len(p) for room in env.rooms for p in room.portals)
    print(f"已保存 world_top.png({img.shape[1]}x{img.shape[0]})")
    print(f"JSON 门数:      {len(spec['doors'])}")
    print(f"connect_rooms:  成功调用 {env.connect_calls} 次"
          f"(失败会触发 assert 直接崩,不存在静默失败)")
    print(f"过道 Room:      生成 {env.passage_rooms} 个")
    print(f"env.rooms:      {len(env.rooms)} 个 = 房间 {len(spec['rooms'])}"
          f" + 过道 {env.passage_rooms}")
    print(f"portal 总数:    {portal_total} 个(每扇门在两侧墙各留一个开口)")
    print(f"agent 半径:     {env.agent.radius}m,位于 {env.spec['start']} 房间中心")


if __name__ == "__main__":
    main()
