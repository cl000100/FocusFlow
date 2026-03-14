# FocusFlow 打包指南

## 打包环境准备

1. **激活虚拟环境**：
   ```powershell
   venv\Scripts\activate
   ```

2. **清理旧的打包产物**：
   ```powershell
   Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
   ```

3. **备份数据**：
   ```powershell
   Copy-Item data\tracker.db data\tracker_backup.db -Force
   New-Item -ItemType Directory -Path data_backup -Force
   Copy-Item data -Recurse -Destination data_backup -Force
   ```

4. **安装打包工具**：
   ```powershell
   pip install pyinstaller pipdeptree
   ```

5. **安装依赖**：
   ```powershell
   pip install -r requirements-windows.txt
   pip install PySide6
   ```

6. **验证依赖**：
   ```powershell
   pipdeptree > dependencies.txt
   pip check
   ```

## 代码修复

### 1. 修复后台服务启动
修改 `launcher.pyw` 文件，确保在打包后能正确启动 `service_daemon.exe`：

```python
# 检查后台服务是否已在运行（防止重复启动）
import psutil
service_running = False
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
        # 检查是否是 service_daemon 进程，且不是当前进程
        if ('service_daemon.py' in cmdline or 'service_daemon.exe' in cmdline) and proc.info['pid'] != os.getpid():
            service_running = True
            print(f"ℹ️  后台服务已在运行 (PID: {proc.info['pid']})")
            break
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue

if not service_running:
    print("🚀 启动后台服务...")
    # 启动后台服务（无窗口）
    if getattr(sys, 'frozen', False):
        # 打包后的环境，启动 service_daemon.exe
        service_exe = os.path.join(PROJECT_ROOT, "service_daemon.exe")
        subprocess.Popen(
            [service_exe],
            creationflags=subprocess.CREATE_NO_WINDOW,
            cwd=PROJECT_ROOT
        )
    else:
        # 开发环境，启动 service_daemon.py
        subprocess.Popen(
            [python_exe, "service_daemon.py"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            cwd=PROJECT_ROOT
        )
    # 等待服务启动
    time.sleep(1)
    print("✅ 后台服务已启动")
else:
    print("✅ 后台服务已在运行")
```

### 2. 修复重启功能
修改 `gui/dashboard_v2.py` 文件，确保重启功能在打包环境中正常工作：

```python
def restart_app(self):
    """重启程序"""
    # 保存当前状态
    floating_visible = "true" if self.dashboard.floating_widget.isVisible() else "false"
    set_config("floating_visible", floating_visible)
    
    # 保存悬浮窗位置
    floating = self.dashboard.floating_widget
    set_config("floating_position_x", str(floating.x()))
    set_config("floating_position_y", str(floating.y()))
    
    # 关闭所有窗口
    self.dashboard.close()
    
    # 重启进程
    if getattr(sys, 'frozen', False):
        # 打包后的环境，重启主可执行文件
        main_exe = sys.executable
        subprocess.Popen([main_exe])
    else:
        # 开发环境，重启脚本
        python = sys.executable
        script = os.path.abspath(__file__)
        subprocess.Popen([python, script])
    
    # 退出当前进程
    sys.exit(0)
```

## 打包步骤

### 1. 打包后台服务（已验证）
```powershell
# 使用 --collect-all 选项强制收集所有 pywin32 和 win32 相关文件
pyinstaller --collect-all pywin32 --collect-all win32 service_daemon.py --onefile --console --name service_daemon --noconfirm
```

**重要说明**：
- `--collect-all pywin32`：收集所有 pywin32 相关的文件
- `--collect-all win32`：收集所有 win32 相关的文件
- `--console`：显示控制台窗口，便于调试（确认无问题后可改为 `--noconsole`）
- `--onefile`：打包为单个可执行文件

### 2. 打包 GUI 应用（已验证）
```powershell
pyinstaller --onefile --noconsole --name FocusFlow launcher.pyw --hidden-import=PySide6 --hidden-import=pandas
```

**重要说明**：
- `--onefile`：打包为单个可执行文件
- `--noconsole`：不显示控制台窗口
- `--hidden-import=PySide6`：确保 PySide6 模块被正确打包
- `--hidden-import=pandas`：确保 pandas 模块被正确打包

### 3. 复制文件
```powershell
# 创建发布目录
New-Item -ItemType Directory -Path Release -Force

# 复制服务文件
Copy-Item dist\service_daemon.exe Release\ -Force

# 复制 GUI 文件
Copy-Item dist\FocusFlow.exe Release\ -Force

# 复制数据目录
New-Item -ItemType Directory -Path Release\data -Force
Copy-Item data\* Release\data\ -Recurse -Force
```

## 测试步骤

### 1. 测试后台服务（已验证）
```powershell
# 启动服务
& 'dist\service_daemon.exe'

# 检查服务是否运行
Get-Process | Where-Object {$_.ProcessName -eq 'service_daemon'}
```

**验证成功标志**：
- ✅ 控制台显示 `[DEBUG] Windows modules imported successfully`
- ✅ 控制台显示 `[DEBUG] Detected: WindowsTerminal | ...`
- ✅ 控制台显示 `✅ 记入数据库 -> 应用: ...`
- ✅ 任务管理器中有 `service_daemon` 进程

### 2. 测试 GUI 应用（已验证）
```powershell
# 启动应用
& 'Release\FocusFlow.exe'

# 检查应用是否运行
Get-Process | Where-Object {$_.ProcessName -eq 'FocusFlow'}
```

**验证成功标志**：
- ✅ GUI 界面正常显示
- ✅ 系统托盘出现 FocusFlow 图标
- ✅ 后台服务自动启动
- ✅ 能够创建项目和记录时间

### 3. 功能测试
- 启动 `FocusFlow.exe`
- 检查 GUI 是否正常显示
- 检查系统托盘是否出现
- 检查后台服务是否自动启动
- 操作数据（创建项目、记录时间）
- 重启程序，验证数据是否保存

## 优化建议

### 1. 减小文件大小
- 使用 `upx=True` 压缩可执行文件
- 排除不必要的依赖
- 优化导入顺序，减少启动时间

### 2. 启动速度优化
- 延迟加载非必要模块
- 优化服务启动时间
- 减少启动时的初始化操作

### 3. 错误处理
- 确保所有错误都有日志记录
- 添加用户友好的错误提示
- 实现自动错误报告功能

## 常见问题及解决方案

### 1. ImportError: No module named 'xxx'
**解决方案**：在打包命令中添加 `--hidden-import=xxx`

### 2. FileNotFoundError: data/tracker.db
**解决方案**：确保数据目录被正确复制到打包目录

### 3. 后台服务启动失败
**解决方案**：检查服务路径是否正确，尝试以管理员身份运行

### 4. 系统托盘不显示
**解决方案**：检查 PySide6 版本，确保系统托盘功能正常

### 5. 应用崩溃或无响应
**解决方案**：检查 `launcher_error.log` 文件，查看错误信息

### 6. 跟踪项目一直显示 "Windowsterminal service_daemon.exe"，切换其他程序没反应（已解决）
**问题原因**：
- `service_daemon.exe` 没有正确启动或崩溃
- Windows 检测逻辑中 `WindowsTerminal` 被错误处理
- **关键问题**：打包后的 service_daemon.exe 运行时提示 `ModuleNotFoundError: No module named 'win32api'`
- PyInstaller 无法正确打包 `pywin32` 模块，导致运行时缺少必要的 Windows API 模块

**解决方案**：

1. **添加调试信息到 `service_daemon.py`**：
```python
import sys
import traceback

# 添加调试信息
print(f"[DEBUG] Python version: {sys.version}")
print(f"[DEBUG] Platform: {platform.system()}")
print(f"[DEBUG] Current directory: {os.getcwd()}")

# 在关键位置添加 try-except 块
try:
    from core.database import init_db, get_connection
    print("[DEBUG] Successfully imported database modules")
except Exception as e:
    print(f"[ERROR] Failed to import database modules: {e}")
    print(traceback.format_exc())
    sys.exit(1)
```

2. **修复 `modules/app_detector.py` 中的 Windows 检测逻辑**：
```python
def _get_active_app_windows():
    try:
        import win32gui
        import win32process
        import psutil
        
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd: 
            print("[DEBUG] No foreground window found")
            return "Unknown", "N/A"
        
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        try:
            process = psutil.Process(pid)
            app_name = process.name().replace(".exe", "")
        except psutil.NoSuchProcess:
            print(f"[DEBUG] Process {pid} not found")
            return "Unknown", "N/A"
        
        # 扩展系统噪音列表
        system_noise = ["SearchHost", "ShellExperienceHost", "explorer", "TextInputHost", "StartMenuExperienceHost"]
        if app_name in system_noise: 
            print(f"[DEBUG] Ignoring system process: {app_name}")
            return "Unknown", "N/A"
        
        # 对于 Windows Terminal，使用窗口标题作为文件路径
        file_path = title.strip() if title else f"[{app_name}]"
        
        print(f"[DEBUG] Detected: {app_name} | {file_path}")
        return app_name, file_path
    except Exception as e:
        print(f"[DEBUG] Error in _get_active_app_windows: {e}")
        return "Unknown", "N/A"
```

3. **关键步骤：使用 --collect-all 选项重新打包服务**：
```powershell
# 使用 --collect-all 选项强制收集所有 pywin32 和 win32 相关文件
pyinstaller --collect-all pywin32 --collect-all win32 service_daemon.py --onefile --console --name service_daemon --noconfirm

# 复制到发布目录
Copy-Item dist\service_daemon.exe Release\ -Force
```

4. **测试服务**：
   - 双击 `service_daemon.exe` 应该能看到调试输出
   - 检查任务管理器中是否有 `service_daemon` 进程
   - 启动 `FocusFlow.exe` 查看是否能正确跟踪程序
   - 验证日志中是否显示 `[DEBUG] Windows modules imported successfully`

5. **验证成功标志**：
   - ✅ `[DEBUG] Windows modules imported successfully` - win32api 导入成功
   - ✅ `[DEBUG] Detected: WindowsTerminal | C:\Users\cx178\Documents\FocusFlow\Release\service_daemon.exe` - 成功检测到活动窗口
   - ✅ `✅ 记入数据库 -> 应用: WindowsTerminal | 窗口: C:\Users\cx178\Documents\FocusFlow\Release\service_daemon.exe` - 成功将数据写入数据库

**注意事项**：
- 使用 `--collect-all` 选项会使可执行文件变大，但这是确保 `pywin32` 模块正确打包的最可靠方法
- 如果确认服务运行正常，可以将 `--console` 改为 `--noconsole` 来隐藏控制台窗口
- 主程序启动时会自动启动 `service_daemon.exe`，使用 `subprocess.CREATE_NO_WINDOW` 标志隐藏窗口

### 7. 数据库 disk I/O error 错误
**问题原因**：
- 数据库文件被其他进程锁定
- WAL 模式在某些 Windows 环境下不兼容
- 文件权限问题

**解决方案**：

1. **检查并关闭占用数据库的进程**：
```powershell
# 查找占用数据库的进程
Get-Process | Where-Object {$_.ProcessName -match "python|FocusFlow|service_daemon"}

# 关闭这些进程
Stop-Process -Name "FocusFlow" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "service_daemon" -Force -ErrorAction SilentlyContinue
```

2. **修改 `core/database.py` 添加 WAL 模式错误处理**：
```python
# ================= 性能优化：启用 WAL 模式 =================
# WAL (Write-Ahead Logging) 允许读写并发，提升性能
# 必须在其他操作之前执行
# 注意：在某些 Windows 环境下可能会失败，需要错误处理
try:
    cursor.execute('''PRAGMA journal_mode = WAL''')
    print("[DEBUG] WAL mode enabled successfully")
except sqlite3.OperationalError as e:
    print(f"[WARNING] Failed to enable WAL mode: {e}")
    print("[WARNING] Continuing without WAL mode...")
    # 尝试使用 DELETE 模式（默认模式）
    try:
        cursor.execute('''PRAGMA journal_mode = DELETE''')
        print("[DEBUG] Using DELETE journal mode instead")
    except:
        pass
```

3. **在新电脑上首次运行时**：
   - 确保 `data/` 目录有写入权限
   - 建议删除旧的数据库文件（如果有）
   - 让程序自动创建新的数据库

4. **创建测试脚本** `test_service.py`：
```python
#!/usr/bin/env python3
import sys
import os
import platform
import traceback

print("=" * 60)
print("FocusFlow 服务测试脚本")
print("=" * 60)

try:
    from core.database import init_db, get_connection
    print("✅ 数据库模块导入成功")
    init_db()
    print("✅ 数据库初始化成功")
except Exception as e:
    print(f"❌ 数据库错误: {e}")
    print(traceback.format_exc())

try:
    from modules.app_detector import get_active_app_info
    app_name, file_path = get_active_app_info()
    print(f"✅ 检测到: {app_name} | {file_path}")
except Exception as e:
    print(f"❌ 检测错误: {e}")
```

## 打包后验证与维护

### 1. 数据库问题解决方案

**问题**：打包后运行时可能出现 `disk I/O error` 错误
**原因**：用户数据目录中的数据库文件或 WAL 文件被锁定
**解决方案**：
```powershell
# 清理用户数据目录中的数据库文件
# 注意：这会删除所有历史数据，仅在必要时执行
Remove-Item "C:\Users\$env:USERNAME\AppData\Roaming\FocusFlow\data\*.db*" -Force -ErrorAction SilentlyContinue
```

### 2. 进程占用处理

**问题**：复制文件时出现 "文件被另一进程使用" 错误
**解决方案**：
```powershell
# 查找并关闭占用文件的进程
Get-Process | Where-Object {$_.ProcessName -match "FocusFlow|service_daemon"} | Stop-Process -Force -ErrorAction SilentlyContinue
```

### 3. 详细的验证步骤

**后台服务验证**：
- 双击 `service_daemon.exe` 查看控制台输出
- 确认显示 `[DEBUG] Windows modules imported successfully`
- 确认显示 `[DEBUG] Successfully imported database modules`
- 任务管理器中查看是否有 `service_daemon` 进程

**GUI 应用验证**：
- 双击 `FocusFlow.exe` 启动应用
- 检查 GUI 界面是否正常显示
- 检查系统托盘是否出现 FocusFlow 图标
- 任务管理器中查看是否有 `FocusFlow` 进程

### 4. 打包后测试清单

1. **基础功能测试**：
   - 启动应用
   - 创建新项目
   - 开始/停止跟踪
   - 查看统计数据
   - 重启应用

2. **后台服务测试**：
   - 检查服务是否自动启动
   - 切换窗口时是否正确跟踪
   - 数据是否正确写入数据库

3. **稳定性测试**：
   - 运行 30 分钟以上
   - 切换多个应用
   - 最小化到系统托盘
   - 重启应用后数据是否保留

### 5. 发布注意事项

- 确保 `Release` 目录包含所有必要文件
- 测试在不同 Windows 版本上的兼容性
- 建议创建详细的安装说明文档
- 考虑添加版本号和发布日期到应用

## 发布准备

1. **创建发布目录**：
   ```powershell
   New-Item -ItemType Directory -Path Release -Force
   Copy-Item dist\service_daemon.exe Release\ -Force
   Copy-Item dist\FocusFlow.exe Release\ -Force
   New-Item -ItemType Directory -Path Release\data -Force
   Copy-Item data\* Release\data\ -Recurse -Force
   ```

2. **创建 README 文件**：包含安装说明和常见问题解答

3. **创建快捷方式**：为 `FocusFlow.exe` 创建桌面快捷方式

4. **打包为压缩文件**：压缩发布目录为 `.zip` 文件

## 打包配置文件

### service_daemon.spec（已验证）
```python
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os
import sys

# 找到 win32 目录
win32_dir = None
for path in sys.path:
    if os.path.exists(os.path.join(path, 'win32')):
        win32_dir = os.path.join(path, 'win32')
        break

a = Analysis(
    ['service_daemon.py'],
    pathex=[],
    binaries=[],
    datas=[(win32_dir, 'win32')] if win32_dir else [],
    hiddenimports=collect_submodules('win32') + collect_submodules('pywintypes') + ['psutil', 'win32api', 'win32gui', 'win32process'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='service_daemon',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='service_daemon',
)
```

### FocusFlow.spec（已验证）
```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['launcher.pyw'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PySide6', 'pandas'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FocusFlow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FocusFlow',
)
```

---

**最后更新**：2026-03-14
**版本**：v2.0
**打包环境**：Windows 10/11, Python 3.11+
**打包工具**：PyInstaller 6.19.0

**验证状态**：
- ✅ 后台服务打包：已验证
- ✅ GUI 应用打包：已验证
- ✅ 后台服务测试：已验证
- ✅ GUI 应用测试：已验证
