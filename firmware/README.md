# firmware/

ESP32 智能小车固件（Arduino）。入口 `SmartCar_System.ino`。

- `SpeedDrive`：电机驱动与测速
- `TraceControl`：循迹
- `AvoidControl`：避障
- `WebHandler`：Web 控制台（AP + STA）

`config.h` 是本地文件（不进 Git），从 `firmware/SmartCar_System/config.example.h` 复制后按接线修改。
`WebHandler.cpp` 里的热点密码只在本地填写，不要提交。

另外 `firmware/camera/` 是车载图传摄像头（ESP32-CAM，GC2145）的 Web 页面源码，
见该目录下的 README。

详见 `../docs/hardware.md`。
