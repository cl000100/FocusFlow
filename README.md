
# FocusFlow 项目开发文档

## 1. 项目概述
**FocusFlow** 是一个面向专业动画师/剪辑师的跨平台生产力工时统计工具。它能够在后台静默记录用户在 After Effects、Premiere Pro 等软件上的实际工作时长，并根据文件路径自动归档至用户自定义的“项目”中，最终生成可视化报表。

## 2. 核心架构 (Directory Structure)
本项目采用分层架构，确保逻辑解耦：

*   `FocusFlow/`
    *   `core/`：核心引擎与数据库管理。
        *   `database.py`：负责 SQLite 连接、初始化表结构（`activity_log` 和 `project_map`）。
    *   `modules/`：功能模块与逻辑规则。
        *   `app_detector.py`：多软件识别引擎，通过窗口标题提取 `.aep` 或 `.prproj` 文件路径。
        *   `rule_engine.py`：待扩展的智能匹配逻辑（当前集成在 GUI 中）。
    *   `gui/`：前端仪表盘。
        *   `dashboard.py`：使用 `customtkinter` 构建的 GUI，负责数据报表展示与项目规则配置。
    *   `data/`：数据存储。
        *   `tracker.db`：SQLite 数据库。
    *   `service_daemon.py`：后台采集守护进程，负责循环采集并写入日志。
    *   `requirements.txt`：项目依赖（包含 `customtkinter`, `psutil`, `pandas`, `pyobjc` 等）。

## 3. 技术栈
*   **语言**: Python 3.12
*   **界面库**: `customtkinter` (现代化 UI)
*   **数据库**: `sqlite3`
*   **数据分析**: `pandas` (用于高效聚合工时)
*   **系统调用**: `pyobjc` (macOS 系统 API 交互), `psutil` (进程管理)

## 4. 已实现功能
1.  **静默采集**: 后台实时监听 AE 和 PR 的活跃状态，利用系统 API 获取当前活动工程的绝对路径。
2.  **权限处理**: 成功绕过 macOS 的屏幕录制与辅助功能权限拦截，实现稳定读取。
3.  **智能归档**: GUI 支持自定义“路径关键词”与“项目名称”映射，实现工时按项目归类。
4.  **仪表盘系统**: 一键刷新今日报表，文字化展示当前项目工时，支持动态添加项目规则。
5.  **工程化路径优化**: 所有数据存储与读取均基于绝对路径，避免了工程重名引起的统计混乱。

## 5. 当前统计逻辑
*   **闲置判定**: 超过 30 秒无键鼠操作则暂停计时。
*   **周期**: 以 5 秒为周期进行心跳记录，写入 `activity_log` 表。
*   **归档**: 报表生成时，通过 `pandas` 对路径进行模糊匹配，将命中规则的路径合并统计。

## 6. 未来开发路线 (TODO List)
1.  **自动化部署**: 将 `service_daemon.py` 封装为 macOS 的 `LaunchAgent` (.plist) 实现开机自启。
2.  **报表强化**: 增加“导出至 Excel/CSV”功能，支持自定义时间范围（周报/月报）。
3.  **图表可视化**: 接入 `matplotlib` 或 `plotly` 实现饼图/柱状图展示。
4.  **黑/白名单机制**: 提供配置页面屏蔽非生产力软件（如浏览器、聊天工具）。
5.  **渲染检测**: 优化采集逻辑，实现“即使闲置，只要处于渲染状态仍计费”的功能。
6.  **Windows 适配**: 引入 `win32gui` 和 `win32process` 替换 macOS 的 Quartz API，实现完全的跨平台。

---

**给后续开发者的说明：**
本项目的数据库文件位于 `data/tracker.db`，核心逻辑在 `core/` 和 `modules/` 目录下。任何修改请务必保持采集器 (`service_daemon.py`) 的轻量级，避免阻塞主循环。