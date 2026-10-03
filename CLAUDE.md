这是一个分析建筑平面拓扑的研究项目。核心想法:一份 JSON 规格同时用来建 NetworkX 图和 MiniWorld 三维世界,然后比对两者。

环境:Python 3.11,虚拟环境在 venv/。系统的 python 命令不可用要用 py,但 venv 激活后 python 可用。已装 miniworld 2.1.0、pyglet 1.5.31、gymnasium 1.3.0、numpy 2.4.6。

规矩:涉及 miniworld 的 API 时必须先读 reference/Miniworld/ 下的源码确认真实函数签名,不要凭记忆写。每次只实现一个功能,并给出一个可以肉眼验证的输出。写完用中文解释这段在算什么。
