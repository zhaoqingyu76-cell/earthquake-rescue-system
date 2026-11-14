# 软件端（software/）

救援指挥上位机，Python + Flask + OpenCV。

## 文件

| 文件 | 作用 |
|---|---|
| `web_server.py` | Flask 控制台（入口）：全景画面 + AR 导航叠加、小车第一视角、战术决策、WASD 手动控制，`http://<电脑IP>:5000` |
| `rescue_controller.py` | OpenCV 窗口版主控制器（备用）：ArUco 定位 → 自动驾驶两阶段流程 |
| `car.py` | 小车 HTTP 控制层：`/cmd`、`/mode`，方向去重与点动 |
| `detection.py` | 颜色分割检测（水源/坑/倒塌区）+ ArUco 小车定位与朝向 |
| `decision.py` | 危险判定：小车进入色纸警戒框 → 停车研判，否则直行 |
| `deepseek.py` | DeepSeek 战术研判；无 Key / 断网 / 超时时返回本地降级文案，不影响控制 |
| `config.py` | 现场配置：IP、摄像头、检测与控制参数（本地文件，不进 Git；用 `config.example.py` 起步） |
| `web/index.html` | 控制台前端（`web_server.py` 从 `web/index.html` 加载） |
| `demo/sim_tactical_brain_cartoon.py` | 全流程概念演示（仿真版，不接硬件）：阶段一传统红线盲闯失败 → 阶段二本系统绿线 A* 绕行救人，见 `software/demo/README.md` |
| `tools/probe_camera.py` | 摄像头编号探测（0~5 循环预览） |
| `tools/probe_color.py` | HSV 颜色标定（点选紫色纸，打印 H/S/V 范围） |

## 工作流程

1. 全景摄像头俯拍现场，`detection.py` 定位小车（顶部 ArUco 码）和危险区。
2. 小车进入危险区警戒框时停车，`deepseek.py` 给出研判建议。
3. 搜救人员决定绕行还是直穿；系统只给建议和 AR 走向提示，**不自动开车**（`web_server.py` 版）。
4. 小车第一视角来自车载图传（`:81/stream`），与控制接口是两个独立地址，分别填在 `config.py` 里。

## 依赖

见 `software/requirements.txt`：Flask、opencv-python、numpy、requests。
