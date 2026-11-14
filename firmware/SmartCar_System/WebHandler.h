#ifndef WEBHANDLER_H
#define WEBHANDLER_H

#include <WiFi.h>
#include <WebServer.h>
#include "config.h"

// 系统模式枚举
enum SysMode {
    MODE_MANUAL = 0,  // 手动模式
    MODE_TRACE = 1,   // 循迹模式
    MODE_AVOID = 2    // 避障模式
};

// Web处理器类
class WebHandler {
public:
    WebHandler();

    // Web系统初始化
    void begin();

    // 处理Web请求
    void loop();

    // 获取/设置模式
    SysMode getMode();
    void setMode(SysMode mode);

    // 风扇控制
    bool getFanState();
    void setFanState(bool state);

private:
    WebServer server;
    SysMode currentMode;
    bool fanState;

    // 速度历史记录
    static const int MAX_HISTORY = 50;
    float speedHistory[MAX_HISTORY];
    int historyIndex;

    // 有效速度记录（最近5次）
    static const int VALID_SPEED_COUNT = 5;
    float validSpeeds[VALID_SPEED_COUNT];
    int validSpeedIndex;

    unsigned long lastSpeedUpdate;
    String logBuffer;
    unsigned long lastLogTime;

    // 请求处理函数
    void handleRoot();
    void handleCmd();
    void handleData();
    void handleSpeedHistory();

    // 辅助函数
    void updateSpeedHistory(float speed);
    void updateValidSpeed(float speed);
    void addLog(String msg);
};

extern WebHandler WebSys;

#endif // WEBHANDLER_H
