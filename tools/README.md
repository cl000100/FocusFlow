# FocusFlow 打包工具

这个目录包含 FocusFlow 项目的自动化打包工具，提供 GUI 和命令行两种界面。

## 文件说明

- **build_tool.py** - GUI 版本打包工具，提供可视化界面
- **build_cli.py** - 命令行版本打包工具，适合自动化脚本
- **build_config.json** - 配置文件，保存用户偏好设置
- **README.md** - 本文件，使用说明

## 使用方法

### GUI 版本（推荐）

```bash
# 在项目根目录下运行
python tools/build_tool.py
```

**功能特点**：
- 可视化界面，操作直观
- 单选框选择打包模式
- 复选框选择可选步骤
- 实时显示打包进度
- 日志输出窗口
- 自动保存用户偏好

**界面说明**：
1. **打包模式**：
   - 完整打包（推荐）：清理 + 备份 + 打包 + 发布
   - 仅打包（不清理）：直接打包，不清理旧文件
   - 仅清理：只清理旧文件，不打包

2. **窗口模式**：
   - 无控制台窗口（发布用）：打包后的程序无控制台窗口
   - 带控制台窗口（调试用）：打包后的程序带控制台窗口，方便调试

3. **可选步骤**：
   - 备份数据：打包前备份 data 目录
   - 打包后测试：打包完成后显示测试提示
   - 生成日志文件：将打包日志保存到文件
   - 清理临时文件：打包完成后删除临时文件

### 命令行版本

```bash
# 在项目根目录下运行
python tools/build_cli.py [选项]
```

**命令行选项**：
- `--clean` - 只清理旧文件，不打包
- `--no-clean` - 只打包，不清理旧文件
- `--console` - 打包带控制台窗口的版本（调试用）
- `--no-backup` - 跳过数据备份步骤
- `--test` - 打包后运行测试
- `--log` - 生成日志文件
- `--clean-temp` - 打包完成后清理临时文件

**使用示例**：
```bash
# 完整打包流程（默认）
python tools/build_cli.py

# 打包带控制台窗口的版本（调试用）
python tools/build_cli.py --console

# 只清理不打包
python tools/build_cli.py --clean

# 只打包不清理
python tools/build_cli.py --no-clean

# 跳过备份步骤
python tools/build_cli.py --no-backup

# 打包并测试
python tools/build_cli.py --test

# 生成日志文件
python tools/build_cli.py --log

# 清理临时文件
python tools/build_cli.py --clean-temp

# 组合使用多个选项
python tools/build_cli.py --console --test --log
```

## 打包流程

1. **清理旧文件**（可选）
   - 删除 build 目录
   - 删除 dist 目录

2. **备份数据**（可选）
   - 备份 data 目录到 data_backup_YYYYMMDD_HHMMSS

3. **检查进程**
   - 关闭占用文件的进程（FocusFlow、service_daemon、python）

4. **打包后台服务**
   - 使用 PyInstaller 打包 service_daemon.py
   - 使用 --collect-all pywin32 --collect-all win32 确保模块正确打包

5. **打包 GUI 应用**
   - 使用 PyInstaller 打包 launcher.pyw
   - 使用 --hidden-import 确保依赖正确打包

6. **创建发布目录**
   - 创建 Release 目录
   - 复制 service_daemon.exe
   - 复制 FocusFlow.exe
   - 复制 data 目录

7. **清理临时文件**（可选）
   - 删除 spec 文件
   - 删除 build 目录

8. **测试**（可选）
   - 显示测试提示

## 配置文件

配置文件 `build_config.json` 保存用户的偏好设置：

```json
{
  "build_mode": "full",
  "console_mode": false,
  "backup_data": true,
  "test_after_build": false,
  "generate_log": false,
  "clean_temp": false
}
```

**配置说明**：
- `build_mode`：打包模式（full/build_only/clean_only）
- `console_mode`：是否显示控制台窗口
- `backup_data`：是否备份数据
- `test_after_build`：是否打包后测试
- `generate_log`：是否生成日志文件
- `clean_temp`：是否清理临时文件

## 注意事项

1. **运行环境**：
   - 必须在虚拟环境中运行
   - 确保已安装所有依赖（PyInstaller、PySide6 等）

2. **进程占用**：
   - 打包前会自动关闭占用文件的进程
   - 如果关闭失败，请手动关闭相关进程

3. **数据备份**：
   - 建议在打包前备份数据
   - 备份文件会保存到项目根目录

4. **打包时间**：
   - 首次打包可能需要较长时间
   - 后续打包会快一些

5. **错误处理**：
   - 如果打包失败，查看日志输出
   - 可以尝试清理后重新打包

## 常见问题

**Q: 打包失败怎么办？**
A: 查看日志输出，根据错误信息处理。常见原因：
- 依赖未安装：运行 `pip install -r requirements-windows.txt`
- 进程占用：手动关闭相关进程
- 权限问题：以管理员身份运行

**Q: 打包后的程序无法运行？**
A: 检查以下几点：
- 是否缺少依赖
- 是否缺少数据文件
- 是否有权限问题

**Q: 如何更新打包工具？**
A: 直接修改 `build_tool.py` 或 `build_cli.py` 文件即可

## 更新日志

### v1.0 (2026-03-15)
- 初始版本
- 支持 GUI 和命令行两种界面
- 支持多种打包模式和选项
- 自动保存用户偏好
