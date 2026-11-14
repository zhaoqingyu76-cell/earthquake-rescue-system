# 部署与运行（setup）

## 0. 先处理密钥

- DeepSeek Key：去 DeepSeek 后台作废旧 Key、生成新 Key，只放环境变量或本地 `.env`，不要写进任何代码文件。
- 手机热点密码：改掉旧密码；在 `firmware/SmartCar_System/WebHandler.cpp` 里本地填写，**不要提交这个文件的修改**。
- 现场 IP 每次联网都可能变，填在本地的 `config.py` / `.env` 里即可。
- 控制口令（可选但建议）：设环境变量 `CONTROL_TOKEN`（比如 `set CONTROL_TOKEN=agcdr2026`），再在网页“手动操控”下方的口令框里填同一个口令；没设口令时，同一局域网内任何人都能调用控制接口开车。

## 1. 硬件端

见 [docs/hardware.md](hardware.md)：Arduino IDE 打开 `firmware/SmartCar_System/SmartCar_System.ino`，烧录后从串口监视器记下小车 STA 模式本机 IP。

## 2. 软件端

```bash
cd software
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp config.example.py config.py
# 把 config.py 里的 CAR_IP、ONBOARD_IP 改成现场实际 IP
# （可选）DeepSeek Key：export DEEPSEEK_API_KEY="YOUR_DEEPSEEK_API_KEY"，或者启动时直接输入（程序会问你，回车跳过）

python tools/probe_camera.py   # 确认全景摄像头编号，填到 config.py 的 CAMERA_ID
python web_server.py           # 浏览器访问 http://<电脑IP>:5000
```

## 3. 推到 GitHub

> 注意：这个文件夹里的 `software/config.py`、`firmware/SmartCar_System/config.h`、
> `firmware/SmartCar_System/WebHandler.cpp`（填了真实热点密码后）都**不要**提交，
> 它们已被 `.gitignore` 忽略或只应保留本地修改。
> 旧的公开仓库如果已经推过带真实密钥的历史，请先作废密钥，
> 再重写历史或删库重建，不要只在新提交里删文件。

```bash
cd earthquake-rescue-system
git init
git add .
git commit -m "feat: initial public release"
git branch -M main
git remote add origin https://github.com/zhaoqingyu76-cell/earthquake-rescue-system.git
git push -u origin main
```

之后在仓库右侧 About 里填简介、topics 和网站；攒到一个能跑的版本就打 tag：

```bash
git tag v1.0.0
git push origin v1.0.0
```

再到 GitHub 的 Releases 里基于这个 tag 发一个 Release。
