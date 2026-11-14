# firmware/camera/

车载图传摄像头（ESP32-CAM，GC2145 传感器）的网页源码。

- `camera_web.html`：摄像头 Web 控制页面（原文件 `esp32.txt`，1131 行）。
  由图传设备在 `:80` 提供，页面里可调分辨率、曝光、白平衡、人脸检测等参数；
  视频流在 `:81/stream`，单帧抓拍在 `/capture`，参数控制在 `/control`，状态在 `/status`。
- 上位机 `software/config.py` 里的 `ONBOARD_IP` / `ONBOARD_STREAM_URL`
  指的就是这台设备：控制页在 `:80`，MJPEG 流在 `:81/stream`。
  注意它和小车控制接口（`CAR_IP`，`:80` 的 `/cmd`、`/mode`）是两个独立地址。
