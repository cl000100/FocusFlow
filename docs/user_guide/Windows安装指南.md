# FocusFlow Windows 安装指南

## 📋 系统要求

- **操作系统**: Windows 10/11 (64 位)
- **Python**: 3.8 或更高版本（推荐 3.12）
- **内存**: 至少 4GB RAM
- **磁盘空间**: 至少 500MB 可用空间

---

## 🚀 安装步骤

### 步骤 1：安装 Python

1. 访问 [Python 官网](https://www.python.org/downloads/)
2. 下载最新版本的 Python 3.12
3. 运行安装程序
4. ⚠️ **重要**: 勾选 "Add Python to PATH"
5. 点击 "Install Now"

**验证安装**:
```cmd
python --version
```
应该显示 `Python 3.12.x`

---

### 步骤 2：克隆或下载项目

**方法 1：使用 Git（推荐）**
```cmd
cd C:\Projects
git clone <repository-url> FocusFlow
cd FocusFlow
```

**方法 2：下载 ZIP**
1. 从 GitHub 下载项目 ZIP 文件
2. 解压到 `C:\Projects\FocusFlow`

---

### 步骤 3：创建虚拟环境

```cmd
cd C:\Projects\FocusFlow
python -m venv venv
```

---

### 步骤 4：激活虚拟环境

**CMD**:
```cmd
venv\Scripts\activate.bat
```

**PowerShell**:
```powershell
venv\Scripts\Activate.ps1
```

激活后，命令行前缀应该显示 `(venv)`

---

### 步骤 5：安装依赖

```cmd
pip install -r requirements-windows.txt
```

**依赖包括**:
- customtkinter - 现代化 UI
- psutil - 系统监控
- pandas - 数据处理
- pywin32 - Windows API 支持
- matplotlib - 图表绘制

**验证安装**:
```cmd
pip list
```

---

### 步骤 6：首次启动

**方法 1：使用启动脚本（推荐）**
```cmd
python scripts\start.bat
```

**方法 2：手动启动**

1. 启动后台服务（新窗口）:
```cmd
start python service_daemon.py
```

2. 启动 GUI:
```cmd
python gui\dashboard_v2.py
```

---

## 🔧 常见问题

### Q1: "python" 不是内部或外部命令

**解决方案**:
1. 重新运行 Python 安装程序
2. 确保勾选 "Add Python to PATH"
3. 重启命令行窗口

### Q2: 虚拟环境激活失败

**CMD 错误**: `无法加载文件，因为在此系统上禁止运行脚本`

**PowerShell 解决方案**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Q3: pywin32 安装失败

**解决方案**:
```cmd
pip install --upgrade pip
pip install pywin32
python venv\Scripts\pywin32_postinstall.py -install
```

### Q4: 中文乱码

**解决方案**:
1. 确保系统区域设置支持中文
2. 在控制面板 → 区域 → 管理 → 更改系统区域设置
3. 勾选 "Beta 版：使用 Unicode UTF-8 提供全球语言支持"
4. 重启电脑

### Q5: 后台服务无法启动

**检查项**:
1. 虚拟环境是否已激活
2. 依赖是否已完全安装
3. 是否有杀毒软件阻止

**手动测试**:
```cmd
python service_daemon.py
```
查看错误信息

### Q6: GUI 界面显示异常

**解决方案**:
1. 更新显卡驱动
2. 确保安装了所有依赖
3. 尝试以管理员身份运行

---

## 🛡️ 权限设置

### 屏幕使用时间权限

Windows 版本**不需要**特殊权限即可运行。

### 开机自启（可选）

**方法 1：任务计划程序**
1. 打开"任务计划程序"
2. 创建基本任务
3. 名称：FocusFlow
4. 触发器：登录时
5. 操作：启动程序
6. 程序：`C:\Projects\FocusFlow\scripts\start.bat`
7. 起始位置：`C:\Projects\FocusFlow`

**方法 2：启动文件夹**
```cmd
shell:startup
```
创建 `start.bat` 的快捷方式

---

## 📊 数据位置

- **数据库**: `data\tracker.db`
- **配置文件**: 存储在数据库的 `system_config` 表
- **日志**: 终端输出

---

## 🔄 更新项目

```cmd
cd C:\Projects\FocusFlow
git pull
venv\Scripts\activate
pip install -r requirements-windows.txt
```

---

## 🧪 测试功能

### 测试应用检测
```cmd
python -c "from modules.app_detector import get_active_app_info; print(get_active_app_info())"
```

### 测试闲置检测
```cmd
python -c "import win32api; print(win32api.GetLastInputInfo())"
```

### 测试数据库
```cmd
python -c "from core.database import get_connection; conn = get_connection(); print(conn.execute('SELECT COUNT(*) FROM activity_log').fetchone())"
```

---

## 📞 获取帮助

如遇到其他问题：
1. 查看终端错误信息
2. 检查 `docs/` 目录下的文档
3. 运行测试脚本验证功能

---

## ✅ 验证清单

安装完成后，确认以下项目：

- [ ] Python 3.8+ 已安装
- [ ] 虚拟环境已创建并激活
- [ ] 所有依赖已安装
- [ ] 后台服务可以启动
- [ ] GUI 界面正常显示
- [ ] 系统托盘图标显示
- [ ] 应用检测正常工作
- [ ] 闲置检测正常工作

---

**最后更新**: 2026-03-14  
**版本**: v1.0  
**适用版本**: FocusFlow v2.0+
