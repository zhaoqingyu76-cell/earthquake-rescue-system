# Changelog

## Unreleased

### Added

- `software/tests/`：检测去噪 + 决策单测（pytest，13 个用例），CI 自动跑。
- README / `docs/software.md`：mermaid 架构数据流图。
- 检测去噪：面积门槛、形状过滤、同类合并、每类上限、跨帧稳定、场地 ROI。

### Fixed

- Web 主流程：小车进入危险区警戒框时自动停车并触发一次 DeepSeek 研判；定位丢失时停车。
- Flask 控制接口增加 `CONTROL_TOKEN` 口令（`/api/cmd`、`/api/mode` 等写接口）。
- 配置清理：`AUTO_ON` → `ONBOARD_ENABLE`，绕行时间常量改名秒（`ROUND_*_S`），删除未用常量，`requirements.txt` 加版本上限。
- README 按真实代码重写：定位为空地协同语义风险代价地图 + 坐标导航，Web 主流程人工在回路、零自动行驶。

## v1.0.0 - 2026-11-15

- 首次公开：重组后的双语仓库（固件 / 软件 / 文档 / CI），Apache-2.0。
