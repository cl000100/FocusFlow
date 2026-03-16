#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FocusFlow 打包工具 - 命令行版本
提供命令行界面，支持自动化打包流程
"""

import sys
import os
import subprocess
import shutil
import json
import time
import argparse
from pathlib import Path
from datetime import datetime


class BuildToolCLI:
    def __init__(self, args):
        self.args = args
        self.config = self.load_config()
        self.update_config_from_args()
        self.log_file = None
        
        if self.config.get('generate_log', False):
            self.init_log_file()
    
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
    
    def update_config_from_args(self):
        if self.args.clean:
            self.config['build_mode'] = 'clean_only'
        elif self.args.no_clean:
            self.config['build_mode'] = 'build_only'
        
        if self.args.console:
            self.config['console_mode'] = True
        
        if self.args.no_backup:
            self.config['backup_data'] = False
        
        if self.args.test:
            self.config['test_after_build'] = True
        
        if self.args.log:
            self.config['generate_log'] = True
        
        if self.args.clean_temp:
            self.config['clean_temp'] = True
    
    def init_log_file(self):
        log_dir = Path(__file__).parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"build_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.log_file = open(log_file, 'w', encoding='utf-8')
    
    def log(self, message):
        print(message)
        if self.log_file:
            self.log_file.write(message + '\n')
            self.log_file.flush()
    
    def run(self):
        try:
            success = self.execute_build()
            if success:
                self.log("\n" + "=" * 60)
                self.log("✅ 打包完成！")
                self.log("=" * 60)
                return 0
            else:
                self.log("\n" + "=" * 60)
                self.log("❌ 打包失败！")
                self.log("=" * 60)
                return 1
        except KeyboardInterrupt:
            self.log("\n❌ 用户取消打包")
            return 1
        except Exception as e:
            self.log(f"\n❌ 错误: {str(e)}")
            return 1
        finally:
            if self.log_file:
                self.log_file.close()
    
    def execute_build(self):
        self.log("=" * 60)
        self.log("FocusFlow 打包工具 v1.0 - 命令行版本")
        self.log("=" * 60)
        self.log("")
        
        if self.config['build_mode'] == 'clean_only':
            return self.clean_only()
        
        if self.config['build_mode'] in ['full', 'build_only']:
            if self.config['build_mode'] == 'full':
                if not self.clean_old_files():
                    return False
            
            if self.config.get('backup_data', False):
                if not self.backup_data():
                    return False
            
            if not self.close_processes():
                return False
            
            if not self.build_service_daemon():
                return False
            
            if not self.build_gui():
                return False
            
            if not self.create_release():
                return False
            
            if self.config.get('clean_temp', False):
                if not self.clean_temp_files():
                    return False
            
            if self.config.get('test_after_build', False):
                if not self.test_build():
                    return False
        
        return True
    
    def clean_only(self):
        self.log("🗑️  清理模式")
        if not self.clean_old_files():
            return False
        if not self.clean_temp_files():
            return False
        return True
    
    def clean_old_files(self):
        self.log("🗑️  清理旧的打包产物...")
        try:
            if os.path.exists('build'):
                shutil.rmtree('build')
                self.log("   ✅ 已删除 build 目录")
            if os.path.exists('dist'):
                shutil.rmtree('dist')
                self.log("   ✅ 已删除 dist 目录")
            self.log("✅ 清理完成")
            self.log("")
            return True
        except Exception as e:
            self.log(f"❌ 清理失败: {str(e)}")
            return False
    
    def backup_data(self):
        self.log("💾 备份数据...")
        try:
            backup_dir = f"data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if os.path.exists('data'):
                shutil.copytree('data', backup_dir)
                self.log(f"   ✅ 数据已备份到 {backup_dir}")
            self.log("✅ 备份完成")
            self.log("")
            return True
        except Exception as e:
            self.log(f"❌ 备份失败: {str(e)}")
            return False
    
    def close_processes(self):
        self.log("🔍 检查并关闭占用进程...")
        try:
            processes_closed = False
            for proc_name in ['FocusFlow', 'service_daemon', 'python']:
                try:
                    result = subprocess.run(
                        ['tasklist', '/FI', f'IMAGENAME eq {proc_name}.exe'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if proc_name in result.stdout:
                        subprocess.run(
                            ['taskkill', '/F', '/IM', f'{proc_name}.exe'],
                            capture_output=True,
                            timeout=10
                        )
                        self.log(f"   ✅ 已关闭 {proc_name}.exe")
                        processes_closed = True
                except:
                    pass
            
            if not processes_closed:
                self.log("   ℹ️  没有需要关闭的进程")
            
            time.sleep(1)
            self.log("✅ 进程检查完成")
            self.log("")
            return True
        except Exception as e:
            self.log(f"❌ 进程检查失败: {str(e)}")
            return False
    
    def build_service_daemon(self):
        self.log("📦 打包后台服务 service_daemon.exe...")
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
            
            self.log(f"   执行命令: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                self.log("   ✅ service_daemon.exe 打包成功")
                self.log("✅ 后台服务打包完成")
                self.log("")
                return True
            else:
                self.log(f"❌ 打包失败:")
                self.log(result.stderr)
                return False
        except subprocess.TimeoutExpired:
            self.log("❌ 打包超时（超过10分钟）")
            return False
        except Exception as e:
            self.log(f"❌ 打包失败: {str(e)}")
            return False
    
    def build_gui(self):
        self.log("📦 打包 GUI 应用 FocusFlow.exe...")
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
            
            self.log(f"   执行命令: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                self.log("   ✅ FocusFlow.exe 打包成功")
                self.log("✅ GUI 应用打包完成")
                self.log("")
                return True
            else:
                self.log(f"❌ 打包失败:")
                self.log(result.stderr)
                return False
        except subprocess.TimeoutExpired:
            self.log("❌ 打包超时（超过10分钟）")
            return False
        except Exception as e:
            self.log(f"❌ 打包失败: {str(e)}")
            return False
    
    def create_release(self):
        self.log("📁 创建发布目录...")
        try:
            if not os.path.exists('Release'):
                os.makedirs('Release')
                self.log("   ✅ 创建 Release 目录")
            
            if os.path.exists('dist/service_daemon.exe'):
                shutil.copy('dist/service_daemon.exe', 'Release/')
                self.log("   ✅ 复制 service_daemon.exe")
            else:
                self.log("❌ 找不到 dist/service_daemon.exe")
                return False
            
            if os.path.exists('dist/FocusFlow.exe'):
                shutil.copy('dist/FocusFlow.exe', 'Release/')
                self.log("   ✅ 复制 FocusFlow.exe")
            else:
                self.log("❌ 找不到 dist/FocusFlow.exe")
                return False
            
            if os.path.exists('data'):
                if os.path.exists('Release/data'):
                    shutil.rmtree('Release/data')
                shutil.copytree('data', 'Release/data')
                self.log("   ✅ 复制 data 目录")
            
            self.log("✅ 发布目录创建完成")
            self.log("")
            return True
        except Exception as e:
            self.log(f"❌ 创建发布目录失败: {str(e)}")
            return False
    
    def clean_temp_files(self):
        self.log("🗑️  清理临时文件...")
        try:
            temp_files = [
                'service_daemon.spec',
                'FocusFlow.spec',
                'dependencies.txt'
            ]
            
            for file in temp_files:
                if os.path.exists(file):
                    os.remove(file)
                    self.log(f"   ✅ 已删除 {file}")
            
            if os.path.exists('build'):
                shutil.rmtree('build')
                self.log("   ✅ 已删除 build 目录")
            
            self.log("✅ 临时文件清理完成")
            self.log("")
            return True
        except Exception as e:
            self.log(f"❌ 清理临时文件失败: {str(e)}")
            return False
    
    def test_build(self):
        self.log("🧪 测试打包结果...")
        try:
            self.log("   ℹ️  测试功能需要手动验证")
            self.log("   建议测试项目:")
            self.log("   1. 双击 Release/service_daemon.exe 查看是否正常启动")
            self.log("   2. 双击 Release/FocusFlow.exe 查看 GUI 是否正常")
            self.log("   3. 检查系统托盘是否出现图标")
            self.log("   4. 创建项目并测试跟踪功能")
            self.log("✅ 测试提示完成")
            self.log("")
            return True
        except Exception as e:
            self.log(f"❌ 测试失败: {str(e)}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='FocusFlow 打包工具 - 命令行版本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python build_cli.py                    # 完整打包流程（默认）
  python build_cli.py --console          # 打包带控制台窗口的版本（调试用）
  python build_cli.py --clean            # 只清理不打包
  python build_cli.py --no-clean         # 只打包不清理
  python build_cli.py --no-backup        # 跳过备份步骤
  python build_cli.py --test             # 打包并测试
  python build_cli.py --log              # 生成日志文件
  python build_cli.py --clean-temp       # 清理临时文件
  python build_cli.py --console --test   # 组合使用多个选项
        """
    )
    
    parser.add_argument(
        '--clean',
        action='store_true',
        help='只清理旧文件，不打包'
    )
    
    parser.add_argument(
        '--no-clean',
        action='store_true',
        help='只打包，不清理旧文件'
    )
    
    parser.add_argument(
        '--console',
        action='store_true',
        help='打包带控制台窗口的版本（调试用）'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='跳过数据备份步骤'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='打包后运行测试'
    )
    
    parser.add_argument(
        '--log',
        action='store_true',
        help='生成日志文件'
    )
    
    parser.add_argument(
        '--clean-temp',
        action='store_true',
        help='打包完成后清理临时文件'
    )
    
    args = parser.parse_args()
    
    tool = BuildToolCLI(args)
    return tool.run()


if __name__ == '__main__':
    sys.exit(main())
