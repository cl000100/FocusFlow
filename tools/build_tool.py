#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FocusFlow 打包工具 - GUI 版本
提供图形化界面，支持可视化打包流程
"""

import sys
import os
import subprocess
import shutil
import json
import time
from pathlib import Path
from datetime import datetime

debug_log_file = None

def debug_log(message):
    global debug_log_file
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {message}"
    print(log_message, flush=True)
    if debug_log_file:
        debug_log_file.write(log_message + '\n')
        debug_log_file.flush()

try:
    debug_log("=" * 60)
    debug_log("FocusFlow 打包工具启动")
    debug_log("=" * 60)
    debug_log(f"Python 版本: {sys.version}")
    debug_log(f"当前工作目录: {os.getcwd()}")
    debug_log(f"脚本路径: {__file__}")
    
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    debug_log_file = open(log_dir / 'build_tool_debug.log', 'w', encoding='utf-8')
    debug_log("调试日志文件已创建")
    
except Exception as e:
    print(f"初始化调试日志失败: {e}", flush=True)

try:
    debug_log("导入 PySide6 模块...")
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGroupBox, QRadioButton, QCheckBox, QPushButton, QProgressBar,
        QTextEdit, QLabel, QMessageBox
    )
    from PySide6.QtCore import QThread, Signal, Qt
    from PySide6.QtGui import QFont
    debug_log("PySide6 模块导入成功")
except Exception as e:
    debug_log(f"导入 PySide6 失败: {e}")
    import traceback
    debug_log(traceback.format_exc())
    raise

def exception_hook(exc_type, exc_value, exc_traceback):
    import traceback
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    debug_log(f"未捕获的异常:\n{error_msg}")
    
    if debug_log_file:
        debug_log_file.close()
    
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = exception_hook
debug_log("全局异常钩子已安装")


class BuildWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(bool, str)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        debug_log(f"BuildWorker.__init__() 配置: {config}")
    
    def run(self):
        debug_log("BuildWorker.run() 开始执行")
        try:
            debug_log("切换到项目根目录...")
            project_root = Path(__file__).parent.parent
            os.chdir(project_root)
            debug_log(f"当前工作目录: {os.getcwd()}")
            
            debug_log("准备调用 execute_build()...")
            debug_log(f"self 对象: {self}")
            debug_log(f"self.config: {self.config}")
            
            debug_log("开始执行打包...")
            success = self.execute_build()
            
            debug_log(f"打包执行完成，结果: {success}")
            self.finished_signal.emit(success, "打包完成" if success else "打包失败")
            
            debug_log("finished_signal 已发送")
        except Exception as e:
            import traceback
            error_msg = f"❌ 错误: {str(e)}\n\n详细错误:\n{traceback.format_exc()}"
            debug_log(error_msg)
            self.log_signal.emit(error_msg)
            self.finished_signal.emit(False, f"打包失败: {str(e)}")
    
    def execute_build(self):
        debug_log("execute_build() 方法开始执行")
        
        debug_log("发送日志信号: 标题")
        self.log_signal.emit("=" * 60)
        self.log_signal.emit("FocusFlow 打包工具 v1.0")
        self.log_signal.emit("=" * 60)
        self.log_signal.emit("")
        
        debug_log("发送日志信号: 检查环境")
        self.log_signal.emit("🔍 检查环境...")
        
        debug_log("检查必要文件...")
        required_files = ['service_daemon.py', 'launcher.pyw']
        missing_files = []
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)
                debug_log(f"缺少文件: {file}")
            else:
                debug_log(f"文件存在: {file}")
        
        if missing_files:
            debug_log(f"缺少必要文件: {', '.join(missing_files)}")
            self.log_signal.emit(f"❌ 缺少必要文件: {', '.join(missing_files)}")
            self.log_signal.emit(f"   当前工作目录: {os.getcwd()}")
            return False
        
        debug_log("环境检查通过")
        self.log_signal.emit("✅ 环境检查通过")
        self.log_signal.emit("")
        
        debug_log("计算总步骤数...")
        total_steps = self.calculate_total_steps()
        debug_log(f"总步骤数: {total_steps}")
        current_step = 0
        
        debug_log(f"打包模式: {self.config['build_mode']}")
        
        if self.config['build_mode'] == 'clean_only':
            debug_log("执行清理模式")
            return self.clean_only()
        
        if self.config['build_mode'] in ['full', 'build_only']:
            if self.config['build_mode'] == 'full':
                if not self.clean_old_files():
                    return False
                current_step += 1
                self.progress_signal.emit(int(current_step / total_steps * 100))
            
            if self.config.get('backup_data', False):
                if not self.backup_data():
                    return False
                current_step += 1
                self.progress_signal.emit(int(current_step / total_steps * 100))
            
            if not self.close_processes():
                return False
            current_step += 1
            self.progress_signal.emit(int(current_step / total_steps * 100))
            
            if not self.build_service_daemon():
                return False
            current_step += 1
            self.progress_signal.emit(int(current_step / total_steps * 100))
            
            if not self.build_gui():
                return False
            current_step += 1
            self.progress_signal.emit(int(current_step / total_steps * 100))
            
            if not self.create_release():
                return False
            current_step += 1
            self.progress_signal.emit(int(current_step / total_steps * 100))
            
            if self.config.get('clean_temp', False):
                if not self.clean_temp_files():
                    return False
                current_step += 1
                self.progress_signal.emit(int(current_step / total_steps * 100))
            
            if self.config.get('test_after_build', False):
                if not self.test_build():
                    return False
                current_step += 1
                self.progress_signal.emit(int(current_step / total_steps * 100))
        
        self.progress_signal.emit(100)
        return True
    
    def calculate_total_steps(self):
        steps = 0
        if self.config['build_mode'] == 'full':
            steps += 1
        if self.config.get('backup_data', False):
            steps += 1
        steps += 1
        steps += 1
        steps += 1
        steps += 1
        if self.config.get('clean_temp', False):
            steps += 1
        if self.config.get('test_after_build', False):
            steps += 1
        return steps
    
    def clean_only(self):
        self.log_signal.emit("🗑️  清理模式")
        if not self.clean_old_files():
            return False
        if not self.clean_temp_files():
            return False
        self.progress_signal.emit(100)
        return True
    
    def clean_old_files(self):
        self.log_signal.emit("🗑️  清理旧的打包产物...")
        try:
            if os.path.exists('build'):
                shutil.rmtree('build')
                self.log_signal.emit("   ✅ 已删除 build 目录")
            if os.path.exists('dist'):
                shutil.rmtree('dist')
                self.log_signal.emit("   ✅ 已删除 dist 目录")
            self.log_signal.emit("✅ 清理完成")
            self.log_signal.emit("")
            return True
        except Exception as e:
            self.log_signal.emit(f"❌ 清理失败: {str(e)}")
            return False
    
    def backup_data(self):
        self.log_signal.emit("💾 备份数据...")
        try:
            backup_dir = f"data/backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if os.path.exists('data'):
                if not os.path.exists('data/backups'):
                    os.makedirs('data/backups')
                    self.log_signal.emit(f"   📁 创建备份目录: data/backups")
                
                shutil.copytree('data', backup_dir, 
                              ignore=shutil.ignore_patterns('backups'))
                self.log_signal.emit(f"   ✅ 数据已备份到 {backup_dir}")
            
            self.log_signal.emit("✅ 备份完成")
            self.log_signal.emit("")
            return True
        except Exception as e:
            self.log_signal.emit(f"❌ 备份失败: {str(e)}")
            return False
    
    def close_processes(self):
        debug_log("close_processes() 方法开始执行")
        self.log_signal.emit("🔍 检查并关闭占用进程...")
        
        import psutil
        current_pid = os.getpid()
        debug_log(f"当前进程 PID: {current_pid}")
        
        try:
            processes_closed = False
            for proc_name in ['FocusFlow', 'service_daemon', 'python']:
                try:
                    debug_log(f"检查进程: {proc_name}.exe")
                    
                    found_processes = []
                    for proc in psutil.process_iter(['pid', 'name']):
                        if proc.info['name'].lower() == f"{proc_name.lower()}.exe":
                            if proc.info['pid'] != current_pid:
                                found_processes.append(proc.info['pid'])
                                debug_log(f"发现进程 {proc_name}.exe (PID: {proc.info['pid']})")
                            else:
                                debug_log(f"跳过当前进程 {proc_name}.exe (PID: {proc.info['pid']})")
                    
                    if found_processes:
                        for pid in found_processes:
                            debug_log(f"关闭进程 {proc_name}.exe (PID: {pid})")
                            proc = psutil.Process(pid)
                            proc.terminate()
                            try:
                                proc.wait(timeout=5)
                            except psutil.TimeoutExpired:
                                proc.kill()
                            
                            self.log_signal.emit(f"   ✅ 已关闭 {proc_name}.exe (PID: {pid})")
                            processes_closed = True
                    else:
                        debug_log(f"没有需要关闭的 {proc_name}.exe 进程")
                        
                except Exception as e:
                    debug_log(f"检查进程 {proc_name}.exe 时出错: {str(e)}")
            
            if not processes_closed:
                self.log_signal.emit("   ℹ️  没有需要关闭的进程")
            
            debug_log("等待1秒...")
            time.sleep(1)
            self.log_signal.emit("✅ 进程检查完成")
            self.log_signal.emit("")
            debug_log("close_processes() 方法执行完成")
            return True
        except Exception as e:
            import traceback
            error_msg = f"❌ 进程检查失败: {str(e)}"
            debug_log(f"{error_msg}\n{traceback.format_exc()}")
            self.log_signal.emit(error_msg)
            return False
    
    def build_service_daemon(self):
        self.log_signal.emit("📦 打包后台服务 service_daemon.exe...")
        try:
            console_mode = '--console' if self.config.get('console_mode', False) else '--noconsole'
            
            cmd = [
                'pyinstaller',
                '--collect-all', 'pywin32',
                '--collect-all', 'win32',
                'service_daemon.py',
                '--onefile',
                console_mode,
                '--name', 'service_daemon',
                '--noconfirm'
            ]
            
            self.log_signal.emit(f"   执行命令: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                self.log_signal.emit("   ✅ service_daemon.exe 打包成功")
                self.log_signal.emit("✅ 后台服务打包完成")
                self.log_signal.emit("")
                return True
            else:
                self.log_signal.emit(f"❌ 打包失败:")
                self.log_signal.emit(result.stderr)
                return False
        except subprocess.TimeoutExpired:
            self.log_signal.emit("❌ 打包超时（超过10分钟）")
            return False
        except Exception as e:
            self.log_signal.emit(f"❌ 打包失败: {str(e)}")
            return False
    
    def build_gui(self):
        self.log_signal.emit("📦 打包 GUI 应用 FocusFlow.exe...")
        try:
            cmd = [
                'pyinstaller',
                '--onefile',
                '--noconsole',
                '--name', 'FocusFlow',
                'launcher.pyw',
                '--hidden-import=PySide6',
                '--hidden-import=pandas'
            ]
            
            self.log_signal.emit(f"   执行命令: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                self.log_signal.emit("   ✅ FocusFlow.exe 打包成功")
                self.log_signal.emit("✅ GUI 应用打包完成")
                self.log_signal.emit("")
                return True
            else:
                self.log_signal.emit(f"❌ 打包失败:")
                self.log_signal.emit(result.stderr)
                return False
        except subprocess.TimeoutExpired:
            self.log_signal.emit("❌ 打包超时（超过10分钟）")
            return False
        except Exception as e:
            self.log_signal.emit(f"❌ 打包失败: {str(e)}")
            return False
    
    def create_release(self):
        self.log_signal.emit("📁 创建发布目录...")
        try:
            if not os.path.exists('Release'):
                os.makedirs('Release')
                self.log_signal.emit("   ✅ 创建 Release 目录")
            
            if os.path.exists('dist/service_daemon.exe'):
                shutil.copy('dist/service_daemon.exe', 'Release/')
                self.log_signal.emit("   ✅ 复制 service_daemon.exe")
            else:
                self.log_signal.emit("❌ 找不到 dist/service_daemon.exe")
                return False
            
            if os.path.exists('dist/FocusFlow.exe'):
                shutil.copy('dist/FocusFlow.exe', 'Release/')
                self.log_signal.emit("   ✅ 复制 FocusFlow.exe")
            else:
                self.log_signal.emit("❌ 找不到 dist/FocusFlow.exe")
                return False
            
            if os.path.exists('data'):
                if os.path.exists('Release/data'):
                    shutil.rmtree('Release/data')
                shutil.copytree('data', 'Release/data')
                self.log_signal.emit("   ✅ 复制 data 目录")
            
            self.log_signal.emit("✅ 发布目录创建完成")
            self.log_signal.emit("")
            return True
        except Exception as e:
            self.log_signal.emit(f"❌ 创建发布目录失败: {str(e)}")
            return False
    
    def clean_temp_files(self):
        self.log_signal.emit("🗑️  清理临时文件...")
        try:
            temp_files = [
                'service_daemon.spec',
                'FocusFlow.spec',
                'dependencies.txt'
            ]
            
            for file in temp_files:
                if os.path.exists(file):
                    os.remove(file)
                    self.log_signal.emit(f"   ✅ 已删除 {file}")
            
            if os.path.exists('build'):
                shutil.rmtree('build')
                self.log_signal.emit("   ✅ 已删除 build 目录")
            
            self.log_signal.emit("✅ 临时文件清理完成")
            self.log_signal.emit("")
            return True
        except Exception as e:
            self.log_signal.emit(f"❌ 清理临时文件失败: {str(e)}")
            return False
    
    def test_build(self):
        self.log_signal.emit("🧪 测试打包结果...")
        try:
            self.log_signal.emit("   ℹ️  测试功能需要手动验证")
            self.log_signal.emit("   建议测试项目:")
            self.log_signal.emit("   1. 双击 Release/service_daemon.exe 查看是否正常启动")
            self.log_signal.emit("   2. 双击 Release/FocusFlow.exe 查看 GUI 是否正常")
            self.log_signal.emit("   3. 检查系统托盘是否出现图标")
            self.log_signal.emit("   4. 创建项目并测试跟踪功能")
            self.log_signal.emit("✅ 测试提示完成")
            self.log_signal.emit("")
            return True
        except Exception as e:
            self.log_signal.emit(f"❌ 测试失败: {str(e)}")
            return False


class BuildToolGUI(QMainWindow):
    def __init__(self):
        debug_log("BuildToolGUI.__init__() 开始")
        super().__init__()
        debug_log("super().__init__() 完成")
        
        debug_log("加载配置文件...")
        self.config = self.load_config()
        debug_log(f"配置加载完成: {self.config}")
        
        debug_log("初始化 UI...")
        self.init_ui()
        debug_log("UI 初始化完成")
    
    def load_config(self):
        config_file = Path(__file__).parent / 'build_config.json'
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            'build_mode': 'full',
            'console_mode': False,
            'backup_data': True,
            'test_after_build': False,
            'generate_log': False,
            'clean_temp': False
        }
    
    def save_config(self):
        config_file = Path(__file__).parent / 'build_config.json'
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {str(e)}")
    
    def init_ui(self):
        debug_log("设置窗口标题和大小...")
        self.setWindowTitle("FocusFlow 打包工具 v1.0")
        self.setGeometry(100, 100, 700, 600)
        
        debug_log("设置样式表...")
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
                color: #333333;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #333333;
            }
            QRadioButton, QCheckBox {
                padding: 5px;
                color: #333333;
            }
            QRadioButton::indicator, QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QLabel {
                color: #333333;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QProgressBar {
                border: 2px solid #cccccc;
                border-radius: 5px;
                text-align: center;
                background-color: white;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
            QTextEdit {
                border: 2px solid #cccccc;
                border-radius: 5px;
                background-color: #2b2b2b;
                color: #00ff00;
                font-family: Consolas, Monaco, monospace;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        build_mode_group = QGroupBox("打包模式")
        build_mode_layout = QVBoxLayout()
        
        self.full_build_radio = QRadioButton("完整打包（推荐）")
        self.full_build_radio.setToolTip("清理旧文件 + 备份数据 + 打包 + 创建发布目录")
        self.build_only_radio = QRadioButton("仅打包（不清理）")
        self.build_only_radio.setToolTip("直接打包，不清理旧文件")
        self.clean_only_radio = QRadioButton("仅清理")
        self.clean_only_radio.setToolTip("只清理旧文件，不打包")
        
        if self.config['build_mode'] == 'full':
            self.full_build_radio.setChecked(True)
        elif self.config['build_mode'] == 'build_only':
            self.build_only_radio.setChecked(True)
        else:
            self.clean_only_radio.setChecked(True)
        
        self.full_build_radio.toggled.connect(lambda: self.update_config('build_mode', 'full'))
        self.build_only_radio.toggled.connect(lambda: self.update_config('build_mode', 'build_only'))
        self.clean_only_radio.toggled.connect(lambda: self.update_config('build_mode', 'clean_only'))
        
        build_mode_layout.addWidget(self.full_build_radio)
        build_mode_layout.addWidget(self.build_only_radio)
        build_mode_layout.addWidget(self.clean_only_radio)
        build_mode_group.setLayout(build_mode_layout)
        layout.addWidget(build_mode_group)
        
        console_mode_group = QGroupBox("窗口模式")
        console_mode_layout = QVBoxLayout()
        
        self.noconsole_radio = QRadioButton("无控制台窗口（发布用）")
        self.noconsole_radio.setToolTip("打包后的程序无控制台窗口，适合发布")
        self.console_radio = QRadioButton("带控制台窗口（调试用）")
        self.console_radio.setToolTip("打包后的程序带控制台窗口，方便调试")
        
        if self.config.get('console_mode', False):
            self.console_radio.setChecked(True)
        else:
            self.noconsole_radio.setChecked(True)
        
        self.noconsole_radio.toggled.connect(lambda checked: self.update_config('console_mode', not checked))
        
        console_mode_layout.addWidget(self.noconsole_radio)
        console_mode_layout.addWidget(self.console_radio)
        console_mode_group.setLayout(console_mode_layout)
        layout.addWidget(console_mode_group)
        
        options_group = QGroupBox("可选步骤")
        options_layout = QVBoxLayout()
        
        self.backup_checkbox = QCheckBox("备份数据")
        self.backup_checkbox.setToolTip("打包前备份 data 目录")
        self.backup_checkbox.setChecked(self.config.get('backup_data', True))
        self.backup_checkbox.toggled.connect(lambda checked: self.update_config('backup_data', checked))
        
        self.test_checkbox = QCheckBox("打包后测试")
        self.test_checkbox.setToolTip("打包完成后显示测试提示")
        self.test_checkbox.setChecked(self.config.get('test_after_build', False))
        self.test_checkbox.toggled.connect(lambda checked: self.update_config('test_after_build', checked))
        
        self.log_checkbox = QCheckBox("生成日志文件")
        self.log_checkbox.setToolTip("将打包日志保存到文件")
        self.log_checkbox.setChecked(self.config.get('generate_log', False))
        self.log_checkbox.toggled.connect(lambda checked: self.update_config('generate_log', checked))
        
        self.clean_checkbox = QCheckBox("清理临时文件")
        self.clean_checkbox.setToolTip("打包完成后删除临时文件（spec文件、build目录等）")
        self.clean_checkbox.setChecked(self.config.get('clean_temp', False))
        self.clean_checkbox.toggled.connect(lambda checked: self.update_config('clean_temp', checked))
        
        options_layout.addWidget(self.backup_checkbox)
        options_layout.addWidget(self.test_checkbox)
        options_layout.addWidget(self.log_checkbox)
        options_layout.addWidget(self.clean_checkbox)
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        button_layout = QHBoxLayout()
        
        self.build_button = QPushButton("开始打包")
        self.build_button.setMinimumHeight(40)
        self.build_button.clicked.connect(self.start_build)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setMinimumHeight(40)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c41709;
            }
        """)
        self.cancel_button.clicked.connect(self.close)
        
        button_layout.addWidget(self.build_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        progress_group = QGroupBox("打包进度")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumHeight(25)
        progress_layout.addWidget(self.progress_bar)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        log_group = QGroupBox("日志输出")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)
        font = QFont("Consolas", 9)
        self.log_text.setFont(font)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        central_widget.setLayout(layout)
    
    def update_config(self, key, value):
        self.config[key] = value
        self.save_config()
    
    def start_build(self):
        debug_log("start_build() 方法被调用")
        try:
            debug_log("禁用按钮...")
            self.build_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
            
            debug_log("重置进度条...")
            self.progress_bar.setValue(0)
            
            debug_log("清空日志...")
            self.log_text.clear()
            
            debug_log("创建 BuildWorker...")
            self.worker = BuildWorker(self.config)
            
            debug_log("连接信号...")
            self.worker.log_signal.connect(self.append_log, Qt.QueuedConnection)
            self.worker.progress_signal.connect(self.update_progress, Qt.QueuedConnection)
            self.worker.finished_signal.connect(self.build_finished, Qt.QueuedConnection)
            
            debug_log("启动工作线程...")
            self.worker.start()
            
            debug_log("工作线程已启动")
        except Exception as e:
            import traceback
            error_msg = f"启动打包失败:\n{str(e)}\n\n详细错误:\n{traceback.format_exc()}"
            debug_log(error_msg)
            QMessageBox.critical(
                self,
                "启动错误",
                error_msg,
                QMessageBox.Ok
            )
            self.build_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
    
    def append_log(self, message):
        debug_log(f"append_log() 被调用: {message[:50]}...")
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def update_progress(self, value):
        debug_log(f"update_progress() 被调用: {value}")
        self.progress_bar.setValue(value)
    
    def build_finished(self, success, message):
        debug_log(f"build_finished() 被调用: success={success}, message={message}")
        self.build_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        
        if success:
            QMessageBox.information(
                self,
                "打包完成",
                f"{message}\n\n发布文件位于 Release 目录",
                QMessageBox.Ok
            )
        else:
            QMessageBox.critical(
                self,
                "打包失败",
                message,
                QMessageBox.Ok
            )


def main():
    try:
        debug_log("main() 函数开始执行")
        
        project_root = Path(__file__).parent.parent
        debug_log(f"项目根目录: {project_root}")
        os.chdir(project_root)
        debug_log(f"已切换到项目根目录: {os.getcwd()}")
        
        debug_log("创建 QApplication...")
        app = QApplication(sys.argv)
        debug_log("QApplication 创建成功")
        
        debug_log("创建 BuildToolGUI 窗口...")
        window = BuildToolGUI()
        debug_log("BuildToolGUI 创建成功")
        
        debug_log("显示窗口...")
        window.show()
        debug_log("窗口已显示")
        
        debug_log("进入事件循环...")
        sys.exit(app.exec())
        
    except Exception as e:
        import traceback
        error_msg = f"程序启动失败:\n{str(e)}\n\n详细错误:\n{traceback.format_exc()}"
        debug_log(error_msg)
        
        try:
            QMessageBox.critical(
                None,
                "启动错误",
                error_msg,
                QMessageBox.Ok
            )
        except:
            pass
        
        sys.exit(1)
    finally:
        if debug_log_file:
            debug_log_file.close()


if __name__ == '__main__':
    debug_log("程序入口 __main__")
    main()
