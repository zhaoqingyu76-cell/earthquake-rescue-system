# 硬件端（firmware/）

ESP32 智能小车固件，Arduino 框架。

## 文件

| 文件 | 作用 |
|---|---|
| `SmartCar_System.ino` | 主程序：初始化各模块，每 50ms 按当前模式调度 |
| `config.h` | 电机/传感器引脚、速度与循迹/避障参数（本地文件，不进 Git；用 `firmware/SmartCar_System/config.example.h` 起步） |
| `SpeedDrive` | 四轮电机驱动、测速（脉冲计数 + 平滑滤波） |
| `TraceControl` | 循迹：5 路传感器读线，调速转向 |
| `AvoidControl` | 避障：超声波测距 + 舵机左右扫描，三方向距离决策前进/转向/后退/掉头 |
| `WebHandler` | Web 控制台：AP + STA 混合模式，网页手动控制、模式切换、风扇、速度历史与日志 |
| `camera/camera_web.html` | 车载图传摄像头（ESP32-CAM，GC2145）的 Web 页面源码：`:80` 控制页、`:81/stream` 图传流，见 `firmware/camera/README.md` |

## 模式

- `manual` 手动：网页按钮 / 上位机 HTTP 指令直接控制
- `trace` 循迹：沿黑线行驶
- `avoid` 避障：遇障减速、转向或后退脱困

三种模式互斥，切换时另一路自动功能会先停掉。

## 引脚（见 config.h）

- 电机：左前 25/26、右前 13/12、左后 32/33、右后 14/27
- 测速 34；循迹 17/16/4/2/15；超声波 Trig 23 / Echo 22；舵机 21；风扇 5

## 烧录

1. Arduino IDE 安装 ESP32 开发板支持。
2. 打开 `firmware/SmartCar_System/SmartCar_System.ino`。
3. `firmware/SmartCar_System/config.example.h` 复制为同目录下的 `config.h`，按接线核对引脚。
4. 在 `WebHandler.cpp` 里填入**自己的**热点名称和密码（本地修改，不要提交这个文件）。
5. 编译、烧录，串口监视器（115200）查看启动日志和 STA 模式本机 IP。
