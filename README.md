# earthquake-rescue-system

空地联动震后救援辅助决策系统（AGCDR）——地面小车 + 无人机 + 上位机软件。

面向震后复杂废墟场景：地面小车与无人机同步采集定位和实时视频，上位机在地图上实时显示两设备位置、轨迹和传感器数据，并可独立控制两设备，实现手动、循迹、避障三种模式切换。系统重点解决坐标与国内地图不匹配、断网环境下轨迹易丢失、双路视频不稳定、空地设备难以协同控制的问题，为救援指挥提供实时态势感知和决策支撑。

> 本仓库是国家级大学生创新创业训练计划项目 AGCDR 的开源代码仓库。

## 仓库结构

```
earthquake-rescue-system/
├── firmware/                 # 硬件端：ESP32 智能小车固件（Arduino）
│   └── SmartCar_System/      # Arduino 工程目录（目录名须与 .ino 同名）
│       ├── SmartCar_System.ino   # 主程序：初始化、模式调度
│       ├── config.h              # 引脚与控制参数（本地配置见 config.example.h）
│       ├── SpeedDrive.cpp/.h     # 电机驱动与测速
│       ├── TraceControl.cpp/.h   # 循迹控制（5 路传感器）
│       ├── AvoidControl.cpp/.h   # 避障控制（超声波 + 舵机扫描）
│       └── WebHandler.cpp/.h     # Web 控制台（AP + STA 混合模式）
│   └── camera/               # 车载图传摄像头（ESP32-CAM，GC2145）
│       └── camera_web.html   # 图传 Web 页面源码（:80 控制页、:81/stream）
├── software/                 # 软件端：救援指挥上位机（Python + Flask）
│   ├── web_server.py         # Flask 控制台：全景画面 + AR 导航 + WASD 手动控制
│   ├── rescue_controller.py  # OpenCV 窗口版主控制器（备用）
│   ├── car.py                # 小车 HTTP 控制层
│   ├── detection.py          # 颜色分割检测 + ArUco 小车定位
│   ├── decision.py           # 危险判定与停车研判决策
│   ├── deepseek.py           # DeepSeek 战术研判（无 Key 时本地降级）
│   ├── config.py             # 现场配置（IP、摄像头、检测参数；密钥只走环境变量）
│   ├── web/index.html        # 控制台前端页面
│   ├── demo/                 # 全流程概念演示（仿真，不接硬件）
│   │   └── sim_tactical_brain_cartoon.py
│   └── tools/                # 摄像头编号探测、HSV 颜色标定工具
├── docs/
│   ├── hardware.md
│   ├── software.md
│   └── setup.md
└── .github/workflows/ci.yml  # CI：Python 语法检查 + ESP32 固件编译检查
```

## 快速开始

### 1. 硬件端（小车）

1. 用 Arduino IDE 打开 `firmware/SmartCar_System/SmartCar_System.ino`，安装 ESP32 开发板支持。
2. 复制 `firmware/SmartCar_System/config.example.h` 为同目录下的 `config.h`，按实际接线确认引脚。
3. 在 `firmware/SmartCar_System/WebHandler.cpp` 里填入**你自己的**手机热点名称和密码（不要提交真实密码，见下）。
4. 编译并烧录，打开串口监视器，记下小车在 STA 模式下的本机 IP。

### 2. 软件端（上位机）

```bash
cd software
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 1) 填配置：复制 config.example.py 为 config.py，
#    把串口读到的 ESP32 IP、车载图传 IP 填进去
# 2) DeepSeek 研判（二选一）：设环境变量 export DEEPSEEK_API_KEY="YOUR_DEEPSEEK_API_KEY"，
#    或者启动时直接输入 Key（程序会问你，直接回车就是不用）。不设也能跑，会用本地降级文案
python web_server.py
# 浏览器访问 http://<电脑IP>:5000
```

第一次跑之前，先用 `tools/probe_camera.py` 确认全景摄像头的编号，再填到 `config.py` 的 `CAMERA_ID`。

详细步骤见 [docs/setup.md](docs/setup.md)。

## 三种模式

| 模式 | 说明 |
|---|---|
| 手动 | WASD / 网页按钮直接控制小车 |
| 循迹 | 5 路传感器沿黑线行驶 |
| 避障 | 超声波 + 舵机扫描，遇障减速、转向或后退脱困 |

软件端另有一套“人在回路”流程：全景摄像头定位小车（ArUco 码）→ 识别水源/坑等危险区 → 小车进入警戒区时停车，DeepSeek 给出研判建议，由搜救人员决定绕行还是直穿；系统只给建议，不自动开车。

## 安全提醒

**不要把真实密钥、密码提交到这个仓库。**

- `firmware/SmartCar_System/WebHandler.cpp` 里的热点名称/密码：本地填写，不要提交。
- `software/config.py` 里的 DeepSeek Key：只从环境变量 `DEEPSEEK_API_KEY` 读取，或者启动时输入，不要写进代码。
- 现场 IP（小车、图传）每次联网都可能变，填在本地的 `config.py` / `.env` 里；`.env` 已在 `.gitignore` 中忽略。
- 如果你曾经把带真实密钥的代码推到过公开仓库，**只删文件不够**，历史提交里还能找到：请先去对应平台作废/轮换那个密钥，再重写历史或删库重建。

## License

Apache-2.0，见 [LICENSE](LICENSE)。
