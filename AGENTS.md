## 项目概述
独立小车（机器人）远程控制前端应用。从 AGCDR Software 中摘离"小车控制"相关组件构成，剔除了图传视频、GPS 定位、数据库存储、无人机控制等无关功能。

## 技术栈
- React 18 + Vite 5（前端 SPA）
- pnpm 包管理器
- @vitejs/plugin-react

## 目录结构
- `src/App.jsx` — 应用入口组件
- `src/index.jsx` — React 挂载入口
- `src/components/ControlPanel.jsx` + `.css` — 小车控制面板：方向控制(f/b/l/r/s)、模式切换(manual/trace/avoid)、连接状态检测、键盘控制(WASD/方向键/空格)、小车 IP 配置
- `src/services/api.js` — 小车 API：
  - `getCarData()` 获取实时数据/连接状态
  - `sendControlCommand(cmd)` 方向命令 f/b/l/r/s
  - `setMode(mode)` 模式 manual/trace/avoid
  - `toggleFan()` 风扇开关
- `vite.config.js` / `index.html` — 构建配置

## 运行与预览
- 预览型 web 项目，端口取 `.preview` 的 `expose_port=5000`
- 安装：`pnpm install --ignore-scripts`
- 开发：`pnpm run dev:web`（vite --host, 5173）
- 预览：`pnpm exec vite preview --host 0.0.0.0 --port 5000`
- 构建：`pnpm run build` → `dist/`

## 关键配置
- 小车默认为 `http://10.40.47.150`，控制面板可改 IP，存于 localStorage `carConfig`（key: carIP）
- 真实小车需提供 `/data`、`/cmd?go=xx`、`/cmd?mode=xx` 接口

## 用户偏好与长期约束
- Node 只用 pnpm，禁止 npm/yarn
- 端口 5000 / 5173，不碰 9000

## 常见问题和预防
- 无真实小车时连接状态显示"未连接"为正常现象，不影响前端演示
- 依赖不带 Electron（纯前端），无需 --ignore-scripts 之外的特殊处理