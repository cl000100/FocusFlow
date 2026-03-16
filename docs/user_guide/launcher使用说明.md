# 🚀 launcher.pyw 使用说明

**文件位置**: `/Users/chenglei/Documents/VScode_CL/FocusFlow/launcher.pyw`

---

## 📋 这是什么？

`launcher.pyw` 是 Windows 专用的启动器，特点：

1. ✅ **无窗口残留** - `.pyw` 文件运行不显示控制台
2. ✅ **自动防重复** - 不会启动多个后台服务
3. ✅ **一键启动** - 同时启动后台服务和 GUI

---

## 🎯 核心功能

### 1. 防止重复启动

**代码逻辑**:
```python
# 检查后台服务是否已在运行
import psutil
service_running = False
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    if 'service_daemon.py' in cmdline:
        service_running = True
        break

if not service_running:
    # 启动新进程
    subprocess.Popen([python_exe, "service_daemon.py"])
else:
    print("✅ 后台服务已在运行")
```

**效果**:
- ✅ 第 1 次启动：启动后台服务 + GUI
- ✅ 第 2 次启动：只启动 GUI，不会重复启动后台服务
- ✅ 第 3 次启动：只启动 GUI，不会重复启动后台服务

---

## 📂 文件位置

**项目根目录**:
```
FocusFlow/
├── launcher.pyw          ← 在这里！
├── scripts/
│   ├── start.bat
│   └── start.sh
├── gui/
│   └── dashboard_v2.py
└── service_daemon.py
```

**完整路径**:
```
/Users/chenglei/Documents/VScode_CL/FocusFlow/launcher.pyw
```

---

## 🔧 使用方法

### Windows 用户

**方法 1: 双击运行**
```
1. 找到 launcher.pyw
2. 双击
3. GUI 窗口出现
4. 完成！
```

**方法 2: 创建快捷方式**
```
1. 右键 launcher.pyw
2. 发送到 → 桌面快捷方式
3. 双击桌面快捷方式
```

**方法 3: 固定到任务栏**
```
1. 右键 launcher.pyw
2. 固定到任务栏
3. 以后点击任务栏图标
```

---

## 🎨 运行效果

### 第 1 次启动（后台服务未运行）
```
双击 launcher.pyw
    ↓
（无窗口 - .pyw 不显示控制台）
    ↓
后台服务启动（静默）
    ↓
GUI 窗口出现
    ↓
✅ 可以开始使用
```

### 第 2 次启动（后台服务已在运行）
```
双击 launcher.pyw
    ↓
检测到后台服务正在运行
    ↓
只启动 GUI，不启动后台服务
    ↓
GUI 窗口出现
    ↓
✅ 不会重复启动
```

---

## 🆚 与 start.bat 的对比

| 特性 | start.bat | launcher.pyw |
|------|-----------|--------------|
| **窗口残留** | ❌ CMD 窗口 | ✅ 无窗口 |
| **防重复启动** | ✅ 有 | ✅ 有 |
| **用户体验** | ⚠️ 一般 | ✅ 优秀 |
| **适用场景** | 开发调试 | 日常使用 |

---

## 🧪 测试验证

### 测试 1: 正常启动
```
1. 确保后台服务未运行
2. 双击 launcher.pyw
3. 预期：GUI 出现，后台服务启动
```

### 测试 2: 重复启动
```
1. 已经有一个 GUI 在运行
2. 再次双击 launcher.pyw
3. 预期：只启动新的 GUI，不会重复启动后台服务
```

### 测试 3: 关闭 GUI 后重启
```
1. 关闭所有 GUI 窗口
2. 后台服务继续运行
3. 双击 launcher.pyw
4. 预期：检测到后台服务，只启动 GUI
```

---

## ⚠️ 注意事项

### 1. 文件扩展名
- 必须是 `.pyw`（不是 `.py`）
- `.pyw` 在 Windows 上无控制台窗口
- `.py` 会显示控制台窗口

### 2. 关联程序
- Windows 默认用 `pythonw.exe` 打开 `.pyw`
- 如果不是，右键 → 打开方式 → 选择默认程序 → pythonw.exe

### 3. 虚拟环境
- 自动检测并使用虚拟环境的 Python
- 路径：`venv\Scripts\python.exe`
- 如果没有虚拟环境，使用系统 Python

---

## 🐛 故障排除

### Q1: 双击没反应
**原因**: 没有关联 `.pyw` 文件

**解决**:
```
1. 右键 launcher.pyw
2. 打开方式 → 选择默认程序
3. 浏览到 C:\Python39\pythonw.exe
4. 勾选"始终使用此应用"
```

### Q2: 出现控制台窗口
**原因**: 用 `.py` 的方式打开了

**解决**:
```
确保文件扩展名是 .pyw（不是 .py）
```

### Q3: 提示找不到 Python
**原因**: 未安装 Python 或虚拟环境

**解决**:
```
1. 安装 Python 3.8+
2. 创建虚拟环境：python -m venv venv
3. 安装依赖：pip install -r requirements-windows.txt
```

### Q4: 启动了多个后台服务
**原因**: 检测逻辑失效

**解决**:
```
1. 打开任务管理器
2. 结束所有 python.exe 进程
3. 重新双击 launcher.pyw
```

---

## 📊 进程关系图

```
双击 launcher.pyw
        ↓
    检查进程列表
        ↓
    ┌─────────────┐
    │ 后台服务运行中？│
    └─────────────┘
        ↓
    是        否
    ↓         ↓
  跳过    启动后台服务
    ↓         ↓
    └────┬────┘
         ↓
    启动 GUI
         ↓
    显示窗口
```

---

## 🎯 总结

**launcher.pyw 的优势**:
1. ✅ 无窗口残留 - 用户体验优秀
2. ✅ 自动防重复 - 不会启动多个后台服务
3. ✅ 一键启动 - 简单方便
4. ✅ 智能检测 - 自动判断是否需要启动后台服务

**推荐使用场景**:
- ✅ Windows 用户日常使用
- ✅ 双击启动，无需命令行
- ✅ 需要良好的用户体验

**文件位置**: 项目根目录 `/Users/chenglei/Documents/VScode_CL/FocusFlow/launcher.pyw`

---

**文档生成时间**: 2026-03-14  
**版本**: v1.0
