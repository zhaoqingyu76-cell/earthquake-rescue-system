/**************************************************************************************
 * 文件: /SmartCar_System/SmartCar_System.ino
 * 作者：零知实验室（深圳市在芯间科技有限公司）
 * -^^- 零知实验室，让电子制作变得更简单！ -^^-
 * 时间: 2026-3-7 10:36:27
 * 说明: ESP32 智能小车控制系统主程序，负责系统初始化、模块调度与模式管理。

 * 功能: 整合电机驱动、循迹控制、避障控制、Web 服务提供网页控制台，支持模式切换、风扇控制、运动操作及速度数据使用CSV 格式导出，
   实时日志记录系统操作与状态变化，支持 AP+STA 混合模式（同时工作在热点模式和局域网模式）。
 ***************************************************************************************/

#include "config.h"
#include "SpeedDrive.h"
#include "TraceControl.h"
#include "AvoidControl.h"
#include "WebHandler.h"

// 系统状态
unsigned long lastModeCheck = 0;
const unsigned long MODE_CHECK_INTERVAL = 50; // 50ms检查一次模式

void setup() {
    Serial.begin(115200);
    Serial.println("\n========================================");
    Serial.println("  ESP32 智能小车系统启动");
    Serial.println("  模式: AP热点模式");
    Serial.println("========================================");

    // 初始化各个模块
    Serial.println("[初始化] 电机驱动系统...");
    CarDrive.begin();

    Serial.println("[初始化] 循迹控制系统...");
    Tracer.begin();

    Serial.println("[初始化] 避障控制系统...");
    Avoider.begin();

    Serial.println("[初始化] Web服务系统...");
    WebSys.begin();

    // 确保初始状态为停止
    CarDrive.stop();

    Serial.println("\n系统就绪!");
    Serial.println("请访问串口监视器查看IP地址信息\n");
}

void loop() {
    // 1. 最高优先级：处理Web请求
    WebSys.loop();

    // 2. 计算实时速度（后台任务）
    CarDrive.loop();

    // 3. 根据模式执行对应的控制逻辑
    //    每个模式是独立的，互不干扰
    unsigned long now = millis();
    if (now - lastModeCheck >= MODE_CHECK_INTERVAL) {
        SysMode currentMode = WebSys.getMode();

        switch (currentMode) {
            case MODE_TRACE:
                // 循迹模式 - 独立运行
                Avoider.stop();  // 确保避障停止
                Tracer.run();
                break;

            case MODE_AVOID:
                // 避障模式 - 独立运行
                Tracer.stop();   // 确保循迹停止
                Avoider.run();
                break;

            case MODE_MANUAL:
                // 手动模式 - 停止所有自动功能
                Tracer.stop();
                Avoider.stop();
                // 手动控制已经在 WebSys.loop() 中处理
                break;
        }

        lastModeCheck = now;
    }

    // 4. 微小延时，防止看门狗超时
    delay(1);
}

/******************************************************************************
 * 深圳市在芯间科技有限公司
 * 淘宝店铺：在芯间科技零知板
 ******************************************************************************/
