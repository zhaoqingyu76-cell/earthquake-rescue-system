#include "WebHandler.h"
#include "SpeedDrive.h"

WebHandler WebSys;

// STA模式配置（连接到手机热点）
const char* HOTSPOT_SSID = "YOUR_HOTSPOT_SSID";  // 本地填写：手机热点名称（不要提交真实密码）
const char* HOTSPOT_PASSWORD = "YOUR_HOTSPOT_PASSWORD";  // 本地填写：手机热点密码（不要提交真实密码）

// 现代化简约式HTML页面
const char* html_page = R"=====(
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ESP32 智能小车控制台</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
  padding: 20px;
  color: #fff;
}
.container { max-width: 600px; margin: 0 auto; }
.card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 20px;
  padding: 25px;
  margin-bottom: 20px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  color: #333;
}
h1 {
  text-align: center;
  font-size: 28px;
  margin-bottom: 10px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  margin-bottom: 20px;
}
.speed-display {
  font-size: 36px;
  font-weight: bold;
  color: #fff;
}
.speed-unit { font-size: 14px; opacity: 0.9; }
.mode-indicator {
  padding: 8px 16px;
  background: rgba(255,255,255,0.2);
  border-radius: 20px;
  font-size: 14px;
  backdrop-filter: blur(10px);
}
.btn-fan {
  width: 45px;
  height: 45px;
  border-radius: 50%;
  border: none;
  background: rgba(255,255,255,0.2);
  backdrop-filter: blur(10px);
  cursor: pointer;
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}
.btn-fan:hover { background: rgba(255,255,255,0.3); }
.btn-fan.active {
  background: #28a745;
  animation: spin 2s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.chart-container {
  height: 180px;
  background: #f8f9fa;
  border-radius: 12px;
  padding: 15px;
  margin-bottom: 20px;
  position: relative;
  overflow: hidden;
}
.chart-canvas { width: 100%; height: 100%; }
.btn-group {
  display: grid;
  gap: 12px;
  margin-bottom: 20px;
}
.btn {
  padding: 16px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.btn:active { transform: translateY(2px); box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
.btn-mode {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}
.btn-mode:hover { opacity: 0.9; }
.btn-mode.active {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  box-shadow: 0 6px 20px rgba(245, 87, 108, 0.4);
}
.control-pad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  max-width: 280px;
  margin: 0 auto;
}
.btn-ctrl {
  width: 70px;
  height: 70px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-size: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
}
.btn-ctrl:active { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
.btn-stop {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  font-size: 18px;
  font-weight: bold;
}
.export-section {
  display: flex;
  gap: 10px;
}
.btn-export {
  flex: 1;
  padding: 12px;
  background: #28a745;
  color: white;
  border-radius: 10px;
}
.log-container {
  max-height: 100px;
  overflow-y: auto;
  background: #f8f9fa;
  padding: 10px;
  border-radius: 10px;
  font-size: 13px;
  color: #666;
  font-family: monospace;
}
.log-item { padding: 4px 0; border-bottom: 1px solid #eee; }
.hidden { display: none; }
</style>
</head>
<body>
<div class="container">
  <h1>🚗 ESP32 智能小车</h1>

  <div class="status-bar">
    <div>
      <div class="speed-display" id="speed">0.00</div>
      <div class="speed-unit">cm/s</div>
    </div>
    <div style="display: flex; gap: 10px; align-items: center;">
      <div class="mode-indicator" id="mode-display">手动模式</div>
      <button class="btn-fan" id="fan-btn" onclick="toggleFan()" title="风扇控制">
        <span id="fan-icon">🌀</span>
      </button>
    </div>
  </div>

  <div class="card">
    <div class="chart-container">
      <canvas id="speedChart" class="chart-canvas"></canvas>
    </div>
  </div>

  <div class="card">
    <div class="btn-group">
      <button class="btn btn-mode active" data-mode="manual" onclick="setMode('manual')">
        🎮 手动控制
      </button>
      <button class="btn btn-mode" data-mode="trace" onclick="setMode('trace')">
        🛤️ 自动循迹
      </button>
      <button class="btn btn-mode" data-mode="avoid" onclick="setMode('avoid')">
        🚧 智能避障
      </button>
    </div>
  </div>

  <div class="card" id="manual-ctrl">
    <div class="control-pad">
      <div></div>
      <button class="btn btn-ctrl" onmousedown="move('f')" onmouseup="move('s')" ontouchstart="move('f')" ontouchend="move('s')">▲</button>
      <div></div>
      <button class="btn btn-ctrl" onmousedown="move('l')" onmouseup="move('s')" ontouchstart="move('l')" ontouchend="move('s')">◀</button>
      <button class="btn btn-ctrl btn-stop" onclick="move('s')">■</button>
      <button class="btn btn-ctrl" onmousedown="move('r')" onmouseup="move('s')" ontouchstart="move('r')" ontouchend="move('s')">▶</button>
      <div></div>
      <button class="btn btn-ctrl" onmousedown="move('b')" onmouseup="move('s')" ontouchstart="move('b')" ontouchend="move('s')">▼</button>
      <div></div>
    </div>
  </div>

  <div class="card">
    <div class="export-section">
      <button class="btn btn-export" onclick="copyData()">📋 复制数据</button>
      <button class="btn btn-export" onclick="exportCSV()">📊 导出CSV</button>
    </div>
  </div>

  <div class="card">
    <h3 style="margin-bottom:10px;font-size:16px;">系统日志</h3>
    <div class="log-container" id="log"></div>
  </div>
</div>

<textarea id="csv-data" class="hidden">Time,Speed(cm/s)</textarea>

<script>
let currentMode = 'manual';
let speedData = [];
let chart;

// 初始化图表
function initChart() {
  const canvas = document.getElementById('speedChart');
  const ctx = canvas.getContext('2d');
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;

  chart = {
    canvas: canvas,
    ctx: ctx,
    data: [],
    maxPoints: 50,
    draw: function() {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      if (this.data.length < 2) return;

      const w = this.canvas.width;
      const h = this.canvas.height;
      const padding = 20;
      const plotW = w - padding * 2;
      const plotH = h - padding * 2;

      // 找最大值
      const maxSpeed = Math.max(...this.data, 50);

      // 绘制网格
      this.ctx.strokeStyle = '#e0e0e0';
      this.ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = padding + (plotH / 4) * i;
        this.ctx.beginPath();
        this.ctx.moveTo(padding, y);
        this.ctx.lineTo(w - padding, y);
        this.ctx.stroke();
      }

      // 绘制曲线
      this.ctx.strokeStyle = '#667eea';
      this.ctx.lineWidth = 2;
      this.ctx.beginPath();

      for (let i = 0; i < this.data.length; i++) {
        const x = padding + (plotW / (this.maxPoints - 1)) * i;
        const y = h - padding - (this.data[i] / maxSpeed) * plotH;
        if (i === 0) this.ctx.moveTo(x, y);
        else this.ctx.lineTo(x, y);
      }
      this.ctx.stroke();

      // 绘制坐标轴标签
      this.ctx.fillStyle = '#666';
      this.ctx.font = '12px sans-serif';
      this.ctx.fillText('0', 5, h - padding + 15);
      this.ctx.fillText(maxSpeed.toFixed(0), 5, padding + 5);
    },
    addData: function(value) {
      this.data.push(value);
      if (this.data.length > this.maxPoints) this.data.shift();
      this.draw();
    }
  };
  chart.draw();
}

function move(dir) {
  fetch('/cmd?go=' + dir);
}

function setMode(mode) {
  currentMode = mode;
  fetch('/cmd?mode=' + mode);

  // 更新UI
  document.querySelectorAll('.btn-mode').forEach(btn => {
    btn.classList.remove('active');
    if (btn.dataset.mode === mode) btn.classList.add('active');
  });

  const modeNames = { manual: '手动模式', trace: '循迹模式', avoid: '避障模式' };
  document.getElementById('mode-display').textContent = modeNames[mode];
  document.getElementById('manual-ctrl').style.display = mode === 'manual' ? 'block' : 'none';
}

function addLog(msg) {
  const logDiv = document.getElementById('log');
  const time = new Date().toLocaleTimeString();
  const item = document.createElement('div');
  item.className = 'log-item';
  item.textContent = `[${time}] ${msg}`;
  logDiv.appendChild(item);
  logDiv.scrollTop = logDiv.scrollHeight;

  // 限制日志条目数量
  while (logDiv.children.length > 20) {
    logDiv.removeChild(logDiv.firstChild);
  }
}

function copyData() {
  fetch('/data').then(r => r.json()).then(data => {
    if (data.validSpeeds && data.validSpeeds.length > 0) {
      const text = "最近5次有效速度值:\n" + data.validSpeeds.join(" cm/s\n") + " cm/s";
      navigator.clipboard.writeText(text).then(() => {
        addLog('已复制最近5次有效速度值');
      });
    } else {
      addLog('暂无有效速度数据');
    }
  });
}

function exportCSV() {
  const csv = document.getElementById('csv-data').value;
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.href = url;
  link.download = 'speed_data_' + new Date().getTime() + '.csv';
  link.click();
  URL.revokeObjectURL(url);
  addLog('CSV文件已导出');
}

function toggleFan() {
  fetch('/cmd?fan=toggle').then(() => {
    addLog('切换风扇状态');
  });
}

// 定期更新数据
setInterval(() => {
  fetch('/data').then(r => r.json()).then(data => {
    // 更新速度显示
    document.getElementById('speed').textContent = data.speed.toFixed(2);

    // 更新图表
    chart.addData(data.speed);

    // 记录CSV数据
    const time = new Date().toLocaleTimeString();
    const line = "\n" + time + "," + data.speed.toFixed(2);
    document.getElementById('csv-data').value += line;

    // 更新风扇按钮状态
    const fanBtn = document.getElementById('fan-btn');
    if (data.fan) {
      fanBtn.classList.add('active');
    } else {
      fanBtn.classList.remove('active');
    }

    // 显示日志
    if (data.log) addLog(data.log);
  });
}, 500);

// 页面加载完成后初始化
window.onload = initChart;
</script>
</body>
</html>
)=====";

WebHandler::WebHandler() : server(80) {
    currentMode = MODE_MANUAL;
    fanState = false;
    historyIndex = 0;
    validSpeedIndex = 0;
    lastSpeedUpdate = 0;
    lastLogTime = 0;

    for (int i = 0; i < MAX_HISTORY; i++) {
        speedHistory[i] = 0;
    }

    for (int i = 0; i < VALID_SPEED_COUNT; i++) {
        validSpeeds[i] = 0;
    }
}

// Web系统初始化（STA模式，连接到手机热点）
void WebHandler::begin() {
    Serial.println("[WiFi] 正在配置STA模式，连接到手机热点...");

    // 设置WiFi模式为STA模式
    WiFi.mode(WIFI_STA);
    Serial.println("[WiFi] WiFi模式已设置为STA模式");

    // 连接到手机热点（自动获取IP）
    Serial.println("[STA模式] 正在连接到手机热点（自动获取IP）...");
    Serial.print("[STA模式] 热点名称: ");
    Serial.println(HOTSPOT_SSID);

    WiFi.begin(HOTSPOT_SSID, HOTSPOT_PASSWORD);

    // 等待连接
    int attempts = 0;
    const int maxAttempts = 30;
    Serial.print("[STA模式] 连接中");
    while (WiFi.status() != WL_CONNECTED && attempts < maxAttempts) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[STA模式] WiFi连接成功!");
        Serial.print("[STA模式] 本机IP: ");
        Serial.println(WiFi.localIP());
        Serial.print("[STA模式] 网关IP: ");
        Serial.println(WiFi.gatewayIP());
        Serial.print("[STA模式] 子网掩码: ");
        Serial.println(WiFi.subnetMask());
        Serial.print("[STA模式] 信号强度: ");
        Serial.print(WiFi.RSSI());
        Serial.println(" dBm");
    } else {
        Serial.println("\n[STA模式] WiFi连接失败!");
        Serial.println("[STA模式] 请检查手机热点是否开启");
        Serial.println("[STA模式] 请检查热点名称和密码是否正确");
    }

    Serial.println();

    // 输出访问地址
    Serial.println("========================================");
    Serial.println("  可以通过以下方式访问控制台：");
    Serial.println("========================================");
    Serial.print("[STA模式] 本机IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("[STA模式] 访问地址: http://");
    Serial.println(WiFi.localIP());
    Serial.println("[STA模式] 手机热点: yvluochen");
    Serial.println("[STA模式] 热点密码: Victury3344");
    Serial.println("========================================");
    Serial.println();

    // 初始化风扇引脚
    pinMode(FAN_PIN, OUTPUT);
    digitalWrite(FAN_PIN, LOW);

    // 初始化Web服务器
    server.on("/", [this](){ handleRoot(); });
    server.on("/cmd", [this](){ handleCmd(); });
    server.on("/data", [this](){ handleData(); });
    server.on("/history", [this](){ handleSpeedHistory(); });

    server.begin();
    Serial.println("[Web] 服务器启动完成");
    Serial.println("[Web] 端口: 80");
    Serial.println();
}

void WebHandler::handleRoot() {
    server.send(200, "text/html; charset=utf-8", html_page);
}

void WebHandler::handleCmd() {
    bool handled = false;

    // 模式切换
    if (server.hasArg("mode")) {
        String m = server.arg("mode");
        SysMode newMode = currentMode;

        if (m == "manual") newMode = MODE_MANUAL;
        else if (m == "trace") newMode = MODE_TRACE;
        else if (m == "avoid") newMode = MODE_AVOID;

        if (newMode != currentMode) {
            setMode(newMode);
            handled = true;
        }
    }

    // 风扇控制
    if (server.hasArg("fan")) {
        String cmd = server.arg("fan");
        if (cmd == "toggle") {
            setFanState(!fanState);
            handled = true;
        }
    }

    // 手动控制命令（仅在手动模式下有效）
    if (server.hasArg("go") && currentMode == MODE_MANUAL) {
        String cmd = server.arg("go");

        if (cmd == "f") {
            CarDrive.run(255, 255);
            addLog("前进");
        } else if (cmd == "b") {
            CarDrive.run(-255, -255);
            addLog("后退");
        } else if (cmd == "l") {
            CarDrive.run(-220, 220);
            addLog("左转");
        } else if (cmd == "r") {
            CarDrive.run(220, -220);
            addLog("右转");
        } else if (cmd == "s") {
            CarDrive.stop();
            addLog("停止");
        }
        handled = true;
    }

    server.send(200, "text/plain", handled ? "OK" : "IGNORED");
}

void WebHandler::handleData() {
    float speed = CarDrive.getSmoothedSpeed();

    // 更新速度历史
    updateSpeedHistory(speed);

    // 更新有效速度记录
    updateValidSpeed(speed);

    // 构建JSON响应
    String json = "{";
    json += "\"speed\":" + String(speed, 2);
    json += ",\"stable\":" + String(CarDrive.isSpeedStable() ? "true" : "false");
    json += ",\"fan\":" + String(fanState ? "true" : "false");

    // 添加最近5次有效速度
    json += ",\"validSpeeds\":[";
    for (int i = 0; i < VALID_SPEED_COUNT; i++) {
        if (i > 0) json += ",";
        json += String(validSpeeds[i], 2);
    }
    json += "]";

    // 添加日志
    if (logBuffer.length() > 0) {
        json += ",\"log\":\"" + logBuffer + "\"";
        logBuffer = "";
    }

    json += "}";

    server.send(200, "application/json", json);
}

void WebHandler::handleSpeedHistory() {
    String json = "[";
    for (int i = 0; i < MAX_HISTORY; i++) {
        if (i > 0) json += ",";
        json += String(speedHistory[i], 2);
    }
    json += "]";

    server.send(200, "application/json", json);
}

void WebHandler::updateSpeedHistory(float speed) {
    unsigned long now = millis();
    if (now - lastSpeedUpdate >= 500) { // 每500ms更新一次
        speedHistory[historyIndex] = speed;
        historyIndex = (historyIndex + 1) % MAX_HISTORY;
        lastSpeedUpdate = now;
    }
}

void WebHandler::updateValidSpeed(float speed) {
    // 只记录有效速度（大于0）
    if (speed > 0) {
        validSpeeds[validSpeedIndex] = speed;
        validSpeedIndex = (validSpeedIndex + 1) % VALID_SPEED_COUNT;
    }
}

void WebHandler::setFanState(bool state) {
    fanState = state;
    digitalWrite(FAN_PIN, fanState ? HIGH : LOW);  // 高电平开启，低电平关闭

    String msg = fanState ? "风扇已开启" : "风扇已关闭";
    addLog(msg);
    Serial.println("[风扇] " + msg);
}

bool WebHandler::getFanState() {
    return fanState;
}

void WebHandler::addLog(String msg) {
    unsigned long now = millis();
    if (now - lastLogTime >= 200) { // 限制日志频率
        logBuffer = msg;
        lastLogTime = now;
    }
}

SysMode WebHandler::getMode() {
    return currentMode;
}

void WebHandler::setMode(SysMode mode) {
    if (mode != currentMode) {
        // 停止当前模式
        CarDrive.stop();

        currentMode = mode;

        String modeName[] = {"手动", "循迹", "避障"};
        addLog("切换到" + modeName[mode] + "模式");
        Serial.println("[模式] 切换到 " + modeName[mode] + " 模式");
    }
}

void WebHandler::loop() {
    server.handleClient();
}
