"""摄像头编号探测工具 —— 找到「外接全景摄像头」正确的编号。

为什么需要：你看到指挥台显示"电脑摄像头"，说明当前 config.CAMERA_ID
配置成了内置摄像头(或旧编号)。外接 USB 全景摄像头在系统里会被分配一个
索引号(通常 0/1/2)，每次插拔 USB 口可能变化。

用法：
  1. 运行本脚本，会循环打开 0~5 号摄像头，并弹出预览窗口；
  2. 用肉眼找出哪一个是「外接全景摄像头」（能拍到地面/你的场景），
     注意旁边窗口标题的数字就是它的编号；
  3. 记下那个编号，按 q 关闭所有预览；
  4. 把编号填到 config.py 的 CAMERA_ID，再运行 web_server.py。
"""
import cv2


def probe():
    print("=" * 50)
    print("摄像头编号探测：循环打开 0~5 号摄像头并预览")
    print("按 q 关闭窗口退出。窗口标题里的数字 = 该摄像头的编号")
    print("=" * 50)

    caps = []
    for i in range(6):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            caps.append((i, cap))
            print(f"  [{i}] 摄像头可用，已打开预览窗口")
        else:
            cap.release()

    if not caps:
        print("没有找到任何可用摄像头。请检查摄像头是否插好、驱动是否正常。")
        return

    while True:
        any_alive = False
        for i, cap in caps:
            ok, frame = cap.read()
            if not ok:
                continue
            any_alive = True
            win = f"Camera {i}"
            cv2.imshow(win, frame)
        if not any_alive:
            print("摄像头均读不到画面，可能被其它程序占用，请关闭其它占用程序后重试。")
            break
        k = cv2.waitKey(10) & 0xFF
        if k == ord("q"):
            break

    for _i, cap in caps:
        cap.release()
    cv2.destroyAllWindows()
    print("已退出。把记下的编号填到 config.py 的 CAMERA_ID。")


if __name__ == "__main__":
    probe()