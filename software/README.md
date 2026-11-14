# software/

救援指挥上位机（Python + Flask + OpenCV）。入口 `web_server.py`，浏览器访问 `http://<电脑IP>:5000`。

```bash
pip install -r requirements.txt
cp config.example.py config.py   # 填入现场 IP
python web_server.py
```

`config.py` 是本地文件（不进 Git）。DeepSeek Key 只从环境变量 `DEEPSEEK_API_KEY` 读取。

单测（不用真摄像头，合成画面跑逻辑）：

```bash
pip install pytest
python -m pytest software/tests -q
```

详见 `../docs/software.md` 和 `../docs/setup.md`。
