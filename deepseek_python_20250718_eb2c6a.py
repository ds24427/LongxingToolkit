import sys
import os
import json
import requests
import pyperclip
from datetime import datetime
import time
import queue
import threading
import webbrowser
import platform
import getpass
import socket

# 尝试导入winreg (仅Windows需要)
try:
    import winreg
except ImportError:
    winreg = None

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QTextEdit, QLineEdit, QPushButton, QLabel, QComboBox, 
                            QListWidget, QMessageBox, QFileDialog, QTabWidget, 
                            QDialog, QGridLayout, QCheckBox, QSlider, QSplitter, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QColor

# 配置管理器
class ConfigManager:
    CONFIG_FILE = "config.json"
    DEFAULT_CONFIG = {
        "api_key": "",
        "language": "zh-CN",
        "theme": "light",
        "model": "deepseek-chat",
        "stream": True,
        "update_interval": 100,  # 毫秒
        "history": [],
        "current_session": [],
        "user": {
            "username": "",
            "login_type": "manual",  # manual/windows/longxing
            "last_login": ""
        }
    }

    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        config = self.DEFAULT_CONFIG.copy()
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    # 加载现有配置
                    loaded_config = json.load(f)
                    
                    # 合并默认配置和加载的配置
                    for key in self.DEFAULT_CONFIG:
                        if key in loaded_config:
                            # 如果是字典，合并字典内容
                            if isinstance(self.DEFAULT_CONFIG[key], dict) and isinstance(loaded_config[key], dict):
                                config[key] = {**self.DEFAULT_CONFIG[key], **loaded_config[key]}
                            else:
                                config[key] = loaded_config[key]
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                # 出错时使用默认配置
                config = self.DEFAULT_CONFIG.copy()
        return config

    def save_config(self):
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")

    def get(self, key):
        keys = key.split('.')
        current = self.config
        for k in keys:
            if k in current:
                current = current[k]
            else:
                return self.DEFAULT_CONFIG.get(key, None)
        return current

    def set(self, key, value):
        keys = key.split('.')
        current = self.config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
        self.save_config()
    
    def add_to_history(self, session):
        """将当前对话保存到历史记录"""
        if not session:
            return
            
        # 生成会话标题
        try:
            title = session[0]["content"][:30] + ("..." if len(session[0]["content"]) > 30 else "")
        except (IndexError, KeyError):
            # 如果获取标题失败，使用默认标题
            title = "无标题对话"
            
        # 添加到历史记录
        self.config["history"].insert(0, {
            "title": title,
            "timestamp": datetime.now().isoformat(),
            "messages": session.copy()
        })
        
        # 保持最多50条历史记录
        if len(self.config["history"]) > 50:
            self.config["history"] = self.config["history"][:50]
            
        self.save_config()
    
    def clear_current_session(self):
        """清空当前对话"""
        self.config["current_session"] = []
        self.save_config()
    
    def save_current_session(self, messages):
        """保存当前对话到会话历史"""
        self.config["current_session"] = messages
        self.save_config()
    
    def set_user_info(self, username, login_type):
        """设置用户信息"""
        if "user" not in self.config:
            self.config["user"] = self.DEFAULT_CONFIG["user"].copy()
            
        self.config["user"]["username"] = username
        self.config["user"]["login_type"] = login_type
        self.config["user"]["last_login"] = datetime.now().isoformat()
        self.save_config()
    
    def get_user_info(self):
        """获取用户信息"""
        # 确保用户信息存在
        if "user" not in self.config:
            self.config["user"] = self.DEFAULT_CONFIG["user"].copy()
            self.save_config()
            
        return self.config["user"]
    
    def logout(self):
        """用户注销"""
        if "user" in self.config:
            self.config["user"] = self.DEFAULT_CONFIG["user"].copy()
            self.save_config()

# 用户登录管理器
class UserManager:
    @staticmethod
    def get_windows_username():
        """获取Windows用户名"""
        try:
            return getpass.getuser()
        except:
            return ""
    
    @staticmethod
    def get_windows_fullname():
        """获取Windows用户全名（仅Windows）"""
        if platform.system() != "Windows" or winreg is None:
            return ""
        
        try:
            # 通过注册表获取用户全名
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
            )
            
            user_sid = os.getenv('USERPROFILE').split('\\')[-1]
            subkey = winreg.OpenKey(key, user_sid)
            fullname, _ = winreg.QueryValueEx(subkey, "ProfileImagePath")
            return fullname.split('\\')[-1]
        except:
            return UserManager.get_windows_username()
    
    @staticmethod
    def get_computer_name():
        """获取计算机名"""
        try:
            return socket.gethostname()
        except:
            return "Unknown"

# 多语言支持
class I18n:
    def __init__(self, lang_code):
        self.languages = {
            "zh-CN": {
                "title": "dsz的DeepSeek 对话助手",
                "send": "发送",
                "copy": "复制",
                "settings": "设置",
                "api_key": "API密钥",
                "language": "语言",
                "theme": "主题",
                "model": "模型",
                "stream": "流式响应",
                "update_interval": "更新间隔(ms)",
                "save": "保存",
                "cancel": "取消",
                "light": "明亮模式",
                "dark": "暗黑模式",
                "input_placeholder": "输入您的问题...",
                "clear": "清空对话",
                "no_api_key": "请先设置API密钥",
                "copy_success": "已复制到剪贴板",
                "settings_saved": "设置已保存",
                "error": "错误",
                "network_error": "网络错误，请检查连接",
                "history": "历史记录",
                "load_history": "加载历史",
                "delete_history": "删除历史",
                "new_chat": "新建对话",
                "session_title": "会话标题",
                "date": "日期",
                "no_history": "无历史记录",
                "stream_enabled": "启用流式响应",
                "typing": "正在输入...",
                "stop": "停止",
                "rate_limit": "API调用过于频繁，请稍后再试",
                "export": "导出对话",
                "export_success": "导出成功",
                "export_failed": "导出失败",
                "about": "关于",
                "bug_report": "Bug反馈",
                "file": "文件",
                "help": "帮助",
                "version": "版本",
                "copyright": "版权",
                "feedback": "提交反馈",
                "export_all": "导出所有历史",
                "login": "登录",
                "username": "用户名",
                "login_with_windows": "使用Windows账户登录",
                "login_with_longxing": "登录LongXing账号",
                "welcome": "欢迎",
                "user": "用户",
                "login_type": "登录方式",
                "last_login": "上次登录",
                "login_required": "请先登录",
                "longxing_login": "LongXing账号登录",
                "longxing_username": "LongXing账号",
                "longxing_password": "密码",
                "longxing_login_btn": "登录",
                "longxing_login_failed": "LongXing账号登录失败",
                "login_success": "登录成功",
                "logout": "注销",
                "default_title": "无标题对话",
                "bug_title": "Bug反馈",
                "bug_description": "请描述您遇到的问题:",
                "bug_steps": "重现步骤:",
                "bug_expected": "预期结果:",
                "bug_actual": "实际结果:",
                "bug_submit": "（仅供测试）提交反馈(请勿提交，可能导致程序崩溃。)",
                "bug_cancel": "取消",
                "bug_thanks": "感谢您的反馈！",
                "bug_submitted": "反馈已提交",
                "bug_submit_failed": "反馈提交失败"
            },
            "en-US": {
                "title": "DeepSeek Chat Assistant",
                "send": "Send",
                "copy": "Copy",
                "settings": "Settings",
                "api_key": "API Key",
                "language": "Language",
                "theme": "Theme",
                "model": "Model",
                "stream": "Stream Response",
                "update_interval": "Update Interval(ms)",
                "save": "Save",
                "cancel": "Cancel",
                "light": "Light Mode",
                "dark": "Dark Mode",
                "input_placeholder": "Type your question here...",
                "clear": "Clear Conversation",
                "no_api_key": "Please set API key first",
                "copy_success": "Copied to clipboard",
                "settings_saved": "Settings saved",
                "error": "Error",
                "network_error": "Network error, please check connection",
                "history": "History",
                "load_history": "Load History",
                "delete_history": "Delete History",
                "new_chat": "New Chat",
                "session_title": "Session Title",
                "date": "Date",
                "no_history": "No history available",
                "stream_enabled": "Enable Stream Response",
                "typing": "Typing...",
                "stop": "Stop",
                "rate_limit": "API rate limit exceeded, please try again later",
                "export": "Export Conversation",
                "export_success": "Export successful",
                "export_failed": "Export failed",
                "about": "About",
                "bug_report": "Bug Report",
                "file": "File",
                "help": "Help",
                "version": "Version",
                "copyright": "Copyright",
                "feedback": "Submit Feedback",
                "export_all": "Export All History",
                "login": "Login",
                "username": "Username",
                "login_with_windows": "Login with Windows Account",
                "login_with_longxing": "Login with LongXing Account",
                "welcome": "Welcome",
                "user": "User",
                "login_type": "Login Type",
                "last_login": "Last Login",
                "login_required": "Please login first",
                "longxing_login": "LongXing Account Login",
                "longxing_username": "LongXing Account",
                "longxing_password": "Password",
                "longxing_login_btn": "Login",
                "longxing_login_failed": "LongXing login failed",
                "login_success": "Login successful",
                "logout": "Logout",
                "default_title": "Untitled Conversation",
                "bug_title": "Bug Report",
                "bug_description": "Please describe the issue you encountered:",
                "bug_steps": "Steps to reproduce:",
                "bug_expected": "Expected result:",
                "bug_actual": "Actual result:",
                "bug_submit": "Submit Feedback",
                "bug_cancel": "Cancel",
                "bug_thanks": "Thank you for your feedback!",
                "bug_submitted": "Feedback submitted",
                "bug_submit_failed": "Failed to submit feedback"
            }
        }
        self.current_lang = lang_code
        self.translations = self.languages.get(lang_code, self.languages["en-US"])
    
    def set_language(self, lang_code):
        self.current_lang = lang_code
        self.translations = self.languages.get(lang_code, self.languages["en-US"])
    
    def t(self, key):
        return self.translations.get(key, key)

# DeepSeek API 客户端
class DeepSeekClient:
    API_URL = "https://api.deepseek.com/v1/chat/completions"
    MODELS = [
        "deepseek-chat", 
        "deepseek-coder"
    ]
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 最小请求间隔1秒
    
    def chat(self, messages, model="deepseek-chat", max_tokens=2048, stream=False):
        # 检查请求频率
        current_time = time.time()
        if current_time - self.last_request_time < self.min_request_interval:
            raise Exception("Rate limit exceeded")
        
        self.last_request_time = current_time
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        try:
            if stream:
                # 流式响应
                response = requests.post(
                    self.API_URL, 
                    headers=self.headers, 
                    json=payload,
                    stream=True
                )
                response.raise_for_status()
                
                # 返回响应生成器
                for chunk in self.process_stream(response):
                    yield chunk
            else:
                # 非流式响应
                response = requests.post(self.API_URL, headers=self.headers, json=payload)
                response.raise_for_status()
                data = response.json()
                yield data["choices"][0]["message"]["content"]
                
        except requests.exceptions.RequestException as e:
            raise ConnectionError("Network error") from e
        except (KeyError, IndexError) as e:
            raise ValueError("Invalid API response") from e
    
    def process_stream(self, response):
        """处理流式响应，提取消息内容"""
        for chunk in response.iter_lines():
            if chunk:
                decoded_chunk = chunk.decode('utf-8')
                if decoded_chunk.startswith("data:"):
                    data_str = decoded_chunk.replace("data: ", "", 1).strip()
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError as e:
                        print(f"JSON解析错误: {e}")

# API请求线程
class ApiRequestThread(QThread):
    response_received = pyqtSignal(str)
    request_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, client, messages, model, stream):
        super().__init__()
        self.client = client
        self.messages = messages
        self.model = model
        self.stream = stream
        self.stop_requested = False
    
    def run(self):
        try:
            if self.stream:
                for chunk in self.client.chat(self.messages, model=self.model, stream=True):
                    if self.stop_requested:
                        break
                    self.response_received.emit(chunk)
            else:
                for res in self.client.chat(self.messages, model=self.model, stream=False):
                    self.response_received.emit(res)
        except Exception as e:
            if "Rate limit exceeded" in str(e):
                error_msg = "API调用过于频繁，请稍后再试"
            else:
                error_msg = f"网络错误: {str(e)}"
            self.error_occurred.emit(error_msg)
        finally:
            self.request_finished.emit()
    
    def stop(self):
        self.stop_requested = True

# 登录窗口
class LoginWindow(QDialog):
    login_successful = pyqtSignal()
    
    def __init__(self, config_manager, i18n, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.i18n = i18n
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle(self.i18n.t("login"))
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # 欢迎标题
        title_label = QLabel(f"{self.i18n.t('welcome')} 使用DeepSeek 助手")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        layout.addSpacing(20)
        
        # 用户名输入
        username_label = QLabel(self.i18n.t("username"))
        layout.addWidget(username_label)
        
        self.username_input = QLineEdit()
        layout.addWidget(self.username_input)
        layout.addSpacing(10)
        
        # 登录按钮
        manual_login_btn = QPushButton(self.i18n.t("login"))
        manual_login_btn.clicked.connect(self.manual_login)
        layout.addWidget(manual_login_btn)
        layout.addSpacing(5)
        
        # Windows登录按钮（仅Windows平台显示）
        if platform.system() == "Windows" and winreg is not None:
            windows_login_btn = QPushButton(self.i18n.t("login_with_windows"))
            windows_login_btn.clicked.connect(self.windows_login)
            layout.addWidget(windows_login_btn)
            layout.addSpacing(5)
        
        # LongXing账号登录
        longxing_login_btn = QPushButton(self.i18n.t("login_with_longxing"))
        longxing_login_btn.clicked.connect(self.longxing_login)
        layout.addWidget(longxing_login_btn)
        
        layout.addStretch()
        
        # 底部版权信息
        copyright_label = QLabel("© 2019-2025 daishizhe /k 内部测试 py.win.build:250719.02")
        copyright_label.setFont(QFont("Arial", 8))
        copyright_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(copyright_label)
    
    def manual_login(self):
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, self.i18n.t("error"), self.i18n.t("login_required"))
            return
        
        self.config_manager.set_user_info(username, "manual")
        self.login_successful.emit()
        self.accept()
    
    def windows_login(self):
        username = UserManager.get_windows_fullname()
        if not username:
            username = UserManager.get_windows_username()
        
        if not username:
            QMessageBox.critical(self, self.i18n.t("error"), "无法获取Windows账户信息")
            return
        
        self.config_manager.set_user_info(username, "windows")
        self.login_successful.emit()
        self.accept()
    
    def longxing_login(self):
        # 创建LongXing账号登录窗口
        longxing_window = QDialog(self)
        longxing_window.setWindowTitle(self.i18n.t("longxing_login"))
        longxing_window.setFixedSize(350, 200)
        
        layout = QVBoxLayout(longxing_window)
        
        # LongXing账号输入
        username_label = QLabel(self.i18n.t("longxing_username"))
        layout.addWidget(username_label)
        
        self.longxing_username = QLineEdit()
        layout.addWidget(self.longxing_username)
        
        # 密码输入
        password_label = QLabel(self.i18n.t("longxing_password"))
        layout.addWidget(password_label)
        
        self.longxing_password = QLineEdit()
        self.longxing_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.longxing_password)
        
        # 登录按钮
        login_btn = QPushButton(self.i18n.t("longxing_login_btn"))
        login_btn.clicked.connect(lambda: self.do_longxing_login(longxing_window))
        layout.addWidget(login_btn)
        
        longxing_window.show()
    
    def do_longxing_login(self, window):
        username = self.longxing_username.text().strip()
        password = self.longxing_password.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, self.i18n.t("error"), self.i18n.t("login_required"))
            return
        
        # 模拟登录（实际应用中这里应该是API调用）
        # 这里只是演示，所以总是返回成功
        if username and password:
            self.config_manager.set_user_info(username, "longxing")
            QMessageBox.information(self, self.i18n.t("login_success"), f"{self.i18n.t('welcome')}, {username}!")
            self.login_successful.emit()
            window.accept()
            self.accept()
        else:
            QMessageBox.critical(self, self.i18n.t("error"), self.i18n.t("longxing_login_failed"))

# 设置窗口
class SettingsWindow(QDialog):
    settings_saved = pyqtSignal()
    
    def __init__(self, config_manager, i18n, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.i18n = i18n
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle(self.i18n.t("settings"))
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # API密钥
        api_key_label = QLabel(self.i18n.t("api_key"))
        layout.addWidget(api_key_label)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(self.config_manager.get("api_key"))
        layout.addWidget(self.api_key_input)
        
        # 语言选择
        language_label = QLabel(self.i18n.t("language"))
        layout.addWidget(language_label)
        
        self.language_combo = QComboBox()
        for lang in self.i18n.languages.keys():
            self.language_combo.addItem(lang)
        self.language_combo.setCurrentText(self.config_manager.get("language"))
        layout.addWidget(self.language_combo)
        
        # 主题选择
        theme_label = QLabel(self.i18n.t("theme"))
        layout.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.setCurrentText(self.config_manager.get("theme"))
        layout.addWidget(self.theme_combo)
        
        # 模型选择
        model_label = QLabel(self.i18n.t("model"))
        layout.addWidget(model_label)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(DeepSeekClient.MODELS)
        self.model_combo.setCurrentText(self.config_manager.get("model"))
        layout.addWidget(self.model_combo)
        
        # 流式响应
        self.stream_check = QCheckBox(self.i18n.t("stream_enabled"))
        self.stream_check.setChecked(self.config_manager.get("stream"))
        layout.addWidget(self.stream_check)
        
        # 更新间隔
        interval_label = QLabel(self.i18n.t("update_interval"))
        layout.addWidget(interval_label)
        
        interval_layout = QHBoxLayout()
        
        self.interval_slider = QSlider(Qt.Horizontal)
        self.interval_slider.setMinimum(50)
        self.interval_slider.setMaximum(500)
        self.interval_slider.setValue(self.config_manager.get("update_interval"))
        interval_layout.addWidget(self.interval_slider)
        
        self.interval_value = QLabel(str(self.config_manager.get("update_interval")))
        interval_layout.addWidget(self.interval_value)
        
        layout.addLayout(interval_layout)
        
        self.interval_slider.valueChanged.connect(lambda: self.interval_value.setText(str(self.interval_slider.value())))
        
        # 按钮
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton(self.i18n.t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton(self.i18n.t("save"))
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def save_settings(self):
        self.config_manager.set("api_key", self.api_key_input.text())
        self.config_manager.set("language", self.language_combo.currentText())
        self.config_manager.set("theme", self.theme_combo.currentText())
        self.config_manager.set("model", self.model_combo.currentText())
        self.config_manager.set("stream", self.stream_check.isChecked())
        self.config_manager.set("update_interval", self.interval_slider.value())
        
        self.settings_saved.emit()
        self.accept()

# 历史记录窗口
class HistoryWindow(QDialog):
    history_selected = pyqtSignal(list)
    
    def __init__(self, config_manager, i18n, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.i18n = i18n
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle(self.i18n.t("history"))
        self.setFixedSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # 历史记录列表
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)
        
        # 加载历史记录
        self.load_history_items()
        
        # 按钮
        button_layout = QHBoxLayout()
        
        load_btn = QPushButton(self.i18n.t("load_history"))
        load_btn.clicked.connect(self.load_history)
        button_layout.addWidget(load_btn)
        
        delete_btn = QPushButton(self.i18n.t("delete_history"))
        delete_btn.clicked.connect(self.delete_history)
        button_layout.addWidget(delete_btn)
        
        layout.addLayout(button_layout)
    
    def load_history_items(self):
        """加载历史记录项，增加错误处理"""
        self.history_list.clear()
        history = self.config_manager.get("history")
        
        if not history:
            self.history_list.addItem(self.i18n.t("no_history"))
            return
            
        for i, session in enumerate(history):
            try:
                # 尝试获取标题和时间戳
                title = session["title"]
                timestamp = session["timestamp"]
                
                # 转换时间戳为可读格式
                date_str = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M")
                
                # 添加到列表
                self.history_list.addItem(f"{title} - {date_str}")
            except (KeyError, ValueError, TypeError) as e:
                # 处理可能的错误
                print(f"加载历史记录时出错 (会话 {i}): {e}")
                
                # 使用默认标题和当前时间
                default_title = self.i18n.t("default_title")
                date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                # 添加带有默认标题的项
                self.history_list.addItem(f"{default_title} - {date_str}")
    
    def load_history(self):
        selected_items = self.history_list.selectedItems()
        if not selected_items:
            return
            
        index = self.history_list.row(selected_items[0])
        history = self.config_manager.get("history")
        
        if 0 <= index < len(history):
            self.history_selected.emit(history[index]["messages"])
            self.accept()
    
    def delete_history(self):
        selected_items = self.history_list.selectedItems()
        if not selected_items:
            return
            
        index = self.history_list.row(selected_items[0])
        history = self.config_manager.get("history")
        
        if 0 <= index < len(history):
            del history[index]
            self.config_manager.config["history"] = history
            self.config_manager.save_config()
            
            # 更新列表
            self.load_history_items()

# 关于窗口
class AboutWindow(QDialog):
    def __init__(self, i18n, version, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.version = version
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle(self.i18n.t("about"))
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel(f"{self.i18n.t('title')}")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        layout.addSpacing(20)
        
        # 版本
        version_label = QLabel(f"{self.i18n.t('version')}: {self.version}")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        # 版权
        copyright_label = QLabel(f"{self.i18n.t('copyright')}: © 2025 daishizhe")
        copyright_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(copyright_label)
        
        # 描述
        desc_label = QLabel("DeepSeek helper")
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)
        layout.addSpacing(20)
        
        # 反馈按钮
        feedback_btn = QPushButton(self.i18n.t("feedback"))
        feedback_btn.clicked.connect(self.report_bug)
       # feedback_btn.setAlignment(Qt.AlignCenter)
        layout.addWidget(feedback_btn)
    
    def report_bug(self):
        # 使用try-except捕获可能的异常
        try:
            webbrowser.open("https://space.bilibili.com/1940516519?spm_id_from=333.1007.0.0")
        except Exception as e:
            QMessageBox.warning(self, self.i18n.t("error"), f"无法打开反馈页面: {str(e)}")

# Bug反馈窗口 - 新添加的类
class BugReportWindow(QDialog):
    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle(self.i18n.t("bug_report"))
        self.setFixedSize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel(f"{self.i18n.t('bug_title')}")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        layout.addSpacing(20)
        
        # 描述输入
        desc_label = QLabel(self.i18n.t("bug_description"))
        layout.addWidget(desc_label)
        
        self.desc_text = QTextEdit()
        layout.addWidget(self.desc_text)
        layout.addSpacing(10)
        
        # 重现步骤
        steps_label = QLabel(self.i18n.t("bug_steps"))
        layout.addWidget(steps_label)
        
        self.steps_text = QTextEdit()
        layout.addWidget(self.steps_text)
        layout.addSpacing(10)
        
        # 预期结果
        expected_label = QLabel(self.i18n.t("bug_expected"))
        layout.addWidget(expected_label)
        
        self.expected_text = QTextEdit()
        layout.addWidget(self.expected_text)
        layout.addSpacing(10)
        
        # 实际结果
        actual_label = QLabel(self.i18n.t("bug_actual"))
        layout.addWidget(actual_label)
        
        self.actual_text = QTextEdit()
        layout.addWidget(self.actual_text)
        layout.addSpacing(20)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton(self.i18n.t("bug_cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        submit_btn = QPushButton(self.i18n.t("bug_submit"))
        submit_btn.clicked.connect(self.submit_feedback)
        button_layout.addWidget(submit_btn)
        
        layout.addLayout(button_layout)
    
    def submit_feedback(self):
        """提交反馈"""
        description = self.desc_text.toPlainText()
        steps = self.steps_text.toPlainText()
        expected = self.expected_text.toPlainText()
        actual = self.actual_text.toPlainText()
        
        if not description or not steps or not expected or not actual:
            QMessageBox.warning(self, self.i18n.t("error"), "请填写所有字段")
            return
            
        # 模拟提交反馈
        try:
            # 在实际应用中，这里应该发送反馈到服务器
            # 这里只是模拟成功
            print(f"提交反馈: {description}, {steps}, {expected}, {actual}")
            
            QMessageBox.information(self, self.i18n.t("bug_submitted"), self.i18n.t("bug_thanks"))
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, self.i18n.t("bug_submit_failed"), f"{self.i18n.t('bug_submit_failed')}: {str(e)}")

# 主应用
class DeepSeekApp(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.i18n = I18n(self.config_manager.get("language"))
        self.client = None
        self.streaming = False
        self.current_response = ""
        self.version = "dev.win.250719.02"
        
        # 检查用户是否已登录
        user_info = self.config_manager.get_user_info()
        if not user_info.get("username"):
            # 显示登录窗口
            self.login_window = LoginWindow(self.config_manager, self.i18n)
            self.login_window.login_successful.connect(self.on_login_success)
            self.login_window.exec_()
        else:
            # 直接初始化主界面
            self.initialize_main_app()
    
    def on_login_success(self):
        """登录成功后的回调"""
        # 关闭登录窗口并初始化主应用
        if hasattr(self, 'login_window'):
            self.login_window.close()
            delattr(self, 'login_window')
            
        self.initialize_main_app()
    
    def initialize_main_app(self):
        """初始化主应用程序"""
        # 如果有保存的API密钥，初始化客户端
        api_key = self.config_manager.get("api_key")
        if api_key:
            self.client = DeepSeekClient(api_key)
        
        # 加载当前会话
        self.messages = self.config_manager.get("current_session") or []
        
        self.setup_ui()
        self.apply_theme()
        self.update_user_info()
        
        # 如果当前会话有内容，显示历史
        self.display_history()
        
        # 显示欢迎消息
        user_info = self.config_manager.get_user_info()
        welcome_msg = f"{self.i18n.t('welcome')}, {user_info['username']}!"
        self.display_system_message(welcome_msg)
    
    def setup_ui(self):
        """设置用户界面"""
        user_info = self.config_manager.get_user_info()
        username = user_info.get("username", "未登录用户")
        self.setWindowTitle(f"{self.i18n.t('title')} - {username}")
        self.resize(1000, 700)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 用户信息栏
        user_info_frame = QFrame()
        user_info_frame.setFrameShape(QFrame.StyledPanel)
        user_info_layout = QHBoxLayout(user_info_frame)
        
        self.user_label = QLabel()
        self.login_type_label = QLabel()
        self.last_login_label = QLabel()
        
        # 添加注销按钮
        self.logout_button = QPushButton(self.i18n.t("logout"))
        self.logout_button.clicked.connect(self.logout)
        
        user_info_layout.addWidget(self.user_label)
        user_info_layout.addWidget(self.login_type_label)
        user_info_layout.addWidget(self.last_login_label)
        user_info_layout.addStretch()
        user_info_layout.addWidget(self.logout_button)
        
        main_layout.addWidget(user_info_frame)
        
        # 对话历史区域
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setAcceptRichText(True)
        main_layout.addWidget(self.history_text)
        
        # 输入区域
        input_layout = QHBoxLayout()
        
        self.input_entry = QLineEdit()
        self.input_entry.setPlaceholderText(self.i18n.t("input_placeholder"))
        self.input_entry.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_entry)
        
        # 按钮
        self.send_button = QPushButton(self.i18n.t("send"))
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)
        
        self.clear_button = QPushButton(self.i18n.t("clear"))
        self.clear_button.clicked.connect(self.clear_conversation)
        input_layout.addWidget(self.clear_button)
        
        self.copy_button = QPushButton(self.i18n.t("copy"))
        self.copy_button.clicked.connect(self.copy_conversation)
        input_layout.addWidget(self.copy_button)
        
        self.stop_button = QPushButton(self.i18n.t("stop"))
        self.stop_button.clicked.connect(self.stop_streaming)
        self.stop_button.setEnabled(False)
        input_layout.addWidget(self.stop_button)
        
        main_layout.addLayout(input_layout)
        
        # 创建菜单栏
        self.create_menu_bar()
    
    def create_menu_bar(self):
        """创建菜单栏"""
        # 文件菜单
        file_menu = self.menuBar().addMenu(self.i18n.t("file"))
        
        new_chat_action = file_menu.addAction(self.i18n.t("new_chat"))
        new_chat_action.triggered.connect(self.new_chat)
        
        history_action = file_menu.addAction(self.i18n.t("history"))
        history_action.triggered.connect(self.open_history)
        
        file_menu.addSeparator()
        
        export_action = file_menu.addAction(self.i18n.t("export"))
        export_action.triggered.connect(self.export_current_conversation)
        
        export_all_action = file_menu.addAction(self.i18n.t("export_all"))
        export_all_action.triggered.connect(self.export_all_history)
        
        # 添加注销菜单项
        logout_action = file_menu.addAction(self.i18n.t("logout"))
        logout_action.triggered.connect(self.logout)
        
        # 设置菜单
        settings_menu = self.menuBar().addMenu(self.i18n.t("settings"))
        
        settings_action = settings_menu.addAction(self.i18n.t("settings"))
        settings_action.triggered.connect(self.open_settings)
        
        # 帮助菜单
        help_menu = self.menuBar().addMenu(self.i18n.t("help"))
        
        # 添加关于菜单项
        about_action = help_menu.addAction(self.i18n.t("about"))
        about_action.triggered.connect(self.show_about)
        
        # 添加Bug反馈菜单项
        bug_report_action = help_menu.addAction(self.i18n.t("bug_report"))
        bug_report_action.triggered.connect(self.show_bug_report)
    
    def apply_theme(self):
        """应用主题设置"""
        theme = self.config_manager.get("theme")
        
        if theme == "dark":
            self.setStyleSheet("""
                QMainWindow, QDialog {
                    background-color: #2d2d2d;
                    color: #ffffff;
                }
                QTextEdit, QLineEdit {
                    background-color: #3a3a3a;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QPushButton {
                    background-color: #4a4a4a;
                    color: #ffffff;
                    border: 1px solid #666666;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #5a5a5a;
                }
                QMenuBar, QMenu {
                    background-color: #3a3a3a;
                    color: #ffffff;
                }
                QMenuBar::item:selected, QMenu::item:selected {
                    background-color: #5a5a5a;
                }
                QFrame {
                    border: 1px solid #555555;
                }
            """)
        else:
            self.setStyleSheet("")  # 恢复默认样式
    
    def update_user_info(self):
        """更新用户信息栏"""
        user_info = self.config_manager.get_user_info()
        
        username = user_info.get("username", "未登录")
        login_type = user_info.get("login_type", "未设置")
        
        last_login = ""
        if user_info.get("last_login"):
            try:
                last_login = datetime.fromisoformat(user_info["last_login"]).strftime("%Y-%m-%d %H:%M")
            except:
                last_login = "N/A"
        else:
            last_login = "N/A"
        
        self.user_label.setText(f"{self.i18n.t('user')}: {username}")
        self.login_type_label.setText(f"{self.i18n.t('login_type')}: {login_type}")
        self.last_login_label.setText(f"{self.i18n.t('last_login')}: {last_login}")
    
    def display_system_message(self, message):
        """显示系统消息"""
        self.history_text.append(f"\n[System] {message}")
        self.scroll_to_bottom()
    
    def display_message(self, sender, message, username=None):
        """显示消息"""
        if sender == "user":
            display_name = username or "You"
            self.history_text.append(f"\n\n{display_name}:")
            self.history_text.append(f"{message}")
        else:
            self.history_text.append(f"\n\nAI:")
            self.history_text.append(f"{message}")
        
        self.scroll_to_bottom()
    
    def scroll_to_bottom(self):
        """滚动到文本底部"""
        cursor = self.history_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.history_text.setTextCursor(cursor)
    
    def open_settings(self):
        """打开设置窗口"""
        settings_window = SettingsWindow(self.config_manager, self.i18n, self)
        settings_window.settings_saved.connect(self.on_settings_saved)
        settings_window.exec_()
    
    def on_settings_saved(self):
        """设置保存后的回调"""
        # 更新语言
        self.i18n.set_language(self.config_manager.get("language"))
        
        # 更新UI文本
        self.update_ui_texts()
        
        # 应用主题
        self.apply_theme()
        
        # 更新用户信息
        self.update_user_info()
        
        # 更新API客户端
        api_key = self.config_manager.get("api_key")
        if api_key:
            self.client = DeepSeekClient(api_key)
    
    def update_ui_texts(self):
        """更新UI文本"""
        user_info = self.config_manager.get_user_info()
        username = user_info.get("username", "未登录用户")
        self.setWindowTitle(f"{self.i18n.t('title')} - {username}")
        
        # 更新按钮文本
        self.send_button.setText(self.i18n.t("send"))
        self.clear_button.setText(self.i18n.t("clear"))
        self.copy_button.setText(self.i18n.t("copy"))
        self.stop_button.setText(self.i18n.t("stop"))
        self.logout_button.setText(self.i18n.t("logout"))
        
        # 更新输入框占位符
        self.input_entry.setPlaceholderText(self.i18n.t("input_placeholder"))
        
        # 更新菜单文本
        self.menuBar().actions()[0].setText(self.i18n.t("file"))
        self.menuBar().actions()[1].setText(self.i18n.t("settings"))
        self.menuBar().actions()[2].setText(self.i18n.t("help"))
        
        # 更新文件菜单
        file_menu = self.menuBar().actions()[0].menu()
        file_menu.actions()[0].setText(self.i18n.t("new_chat"))
        file_menu.actions()[1].setText(self.i18n.t("history"))
        file_menu.actions()[3].setText(self.i18n.t("export"))
        file_menu.actions()[4].setText(self.i18n.t("export_all"))
        file_menu.actions()[5].setText(self.i18n.t("logout"))  # 新增的注销菜单项
        
        # 更新设置菜单
        settings_menu = self.menuBar().actions()[1].menu()
        settings_menu.actions()[0].setText(self.i18n.t("settings"))
        
        # 更新帮助菜单
        help_menu = self.menuBar().actions()[2].menu()
        help_menu.actions()[0].setText(self.i18n.t("about"))
        help_menu.actions()[1].setText(self.i18n.t("bug_report"))
    
    def send_message(self):
        """发送消息"""
        user_input = self.input_entry.text().strip()
        if not user_input:
            return
        
        if not self.client:
            QMessageBox.critical(self, self.i18n.t("error"), self.i18n.t("no_api_key"))
            return
        
        # 清空输入框
        self.input_entry.clear()
        
        # 显示用户消息
        user_info = self.config_manager.get_user_info()
        self.display_message("user", user_input, user_info.get("username", "用户"))
        
        # 添加用户消息到会话
        self.messages.append({"role": "user", "content": user_input})
        
        # 保存当前会话
        self.config_manager.save_current_session(self.messages)
        
        # 开始流式响应
        self.streaming = True
        self.current_response = ""
        self.stop_button.setEnabled(True)
        self.send_button.setEnabled(False)
        
        # 显示"正在输入..."
        self.history_text.append(f"\n\nAI:")
        self.history_text.append(f"{self.i18n.t('typing')}")
        self.scroll_to_bottom()
        
        # 创建API请求线程
        self.api_thread = ApiRequestThread(
            self.client,
            self.messages,
            self.config_manager.get("model"),
            self.config_manager.get("stream")
        )
        self.api_thread.response_received.connect(self.update_response)
        self.api_thread.request_finished.connect(self.on_request_finished)
        self.api_thread.error_occurred.connect(self.on_api_error)
        self.api_thread.start()
    
    def update_response(self, response):
        """更新响应内容"""
        # 累积响应内容
        self.current_response += response
        
        # 删除"正在输入..."
        cursor = self.history_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
        if cursor.selectedText().strip() == self.i18n.t('typing'):
            cursor.removeSelectedText()
            
            # 插入增量内容
            self.history_text.setTextCursor(cursor)
            self.history_text.insertPlainText(response)
        else:
            # 如果没有找到"正在输入..."，直接在末尾追加
            self.history_text.moveCursor(QTextCursor.End)
            self.history_text.insertPlainText(response)
        
        self.scroll_to_bottom()
    
    def on_request_finished(self):
        """请求完成后的回调"""
        self.streaming = False
        self.stop_button.setEnabled(False)
        self.send_button.setEnabled(True)
        
        # 添加最终响应到消息列表
        if self.current_response:
            self.messages.append({"role": "assistant", "content": self.current_response})
            self.config_manager.save_current_session(self.messages)
    
    def on_api_error(self, error_msg):
        """API错误处理"""
        self.streaming = False
        self.stop_button.setEnabled(False)
        self.send_button.setEnabled(True)
        
        # 删除"正在输入..."
        cursor = self.history_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        self.history_text.setTextCursor(cursor)
        
        QMessageBox.critical(self, self.i18n.t("error"), error_msg)
    
    def stop_streaming(self):
        """停止流式响应"""
        if self.streaming and hasattr(self, 'api_thread'):
            self.api_thread.stop()
            self.streaming = False
            self.stop_button.setEnabled(False)
            self.send_button.setEnabled(True)
            
            # 添加已接收的响应到消息列表（如果有）
            if self.current_response:
                self.messages.append({"role": "assistant", "content": self.current_response})
                self.config_manager.save_current_session(self.messages)
    
    def display_history(self):
        """显示当前会话历史"""
        self.history_text.clear()
        
        user_info = self.config_manager.get_user_info()
        username = user_info.get("username", "用户")
        
        for msg in self.messages:
            if msg["role"] == "user":
                self.display_message("user", msg["content"], username)
            elif msg["role"] == "assistant":
                self.display_message("ai", msg["content"])
    
    def copy_conversation(self):
        """复制对话到剪贴板"""
        conversation = self.history_text.toPlainText()
        pyperclip.copy(conversation)
        QMessageBox.information(self, self.i18n.t("copy_success"), self.i18n.t("copy_success"))
    
    def clear_conversation(self):
        """清空对话"""
        self.messages = []
        self.config_manager.clear_current_session()
        self.history_text.clear()
    
    def new_chat(self):
        """新建对话"""
        self.clear_conversation()
    
    def open_history(self):
        """打开历史记录窗口"""
        history_window = HistoryWindow(self.config_manager, self.i18n, self)
        history_window.history_selected.connect(self.load_selected_history)
        history_window.exec_()
    
    def load_selected_history(self, messages):
        """加载选择的历史记录"""
        self.messages = messages
        self.config_manager.save_current_session(self.messages)
        self.display_history()
    
    def export_current_conversation(self):
        """导出当前对话"""
        if not self.messages:
            QMessageBox.information(self, self.i18n.t("info"), "没有对话内容可导出")
            return
            
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                self.i18n.t("export"),
                "",
                "JSON files (*.json);;Text files (*.txt);;All files (*.*)"
            )
            
            if not file_path:
                return
                
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.messages, f, ensure_ascii=False, indent=2)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for msg in self.messages:
                        role = msg["role"].upper()
                        content = msg["content"]
                        f.write(f"{role}:\n{content}\n\n")
            
            QMessageBox.information(self, self.i18n.t("export_success"), self.i18n.t("export_success"))
        except Exception as e:
            QMessageBox.critical(self, self.i18n.t("export_failed"), f"{self.i18n.t('export_failed')}: {str(e)}")
    
    def export_all_history(self):
        """导出所有历史记录"""
        history = self.config_manager.get("history")
        if not history and not self.messages:
            QMessageBox.information(self, self.i18n.t("info"), "没有历史记录可导出")
            return
            
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                self.i18n.t("export_all"),
                "",
                "JSON files (*.json)"
            )
            
            if not file_path:
                return
                
            all_data = {
                "current_session": self.messages,
                "history": history
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, self.i18n.t("export_success"), self.i18n.t("export_success"))
        except Exception as e:
            QMessageBox.critical(self, self.i18n.t("export_failed"), f"{self.i18n.t('export_failed')}: {str(e)}")
    
    def show_about(self):
        """显示关于窗口"""
        about_window = AboutWindow(self.i18n, self.version, self)
        about_window.exec_()
    
    def show_bug_report(self):
        """显示Bug反馈窗口"""
        bug_window = BugReportWindow(self.i18n, self)
        bug_window.exec_()
    
    def report_bug(self):
        """报告问题"""
        # 使用try-except捕获可能的异常
        try:
            webbrowser.open("https://github.com/your-repo/issues")
        except Exception as e:
            QMessageBox.warning(self, self.i18n.t("error"), f"无法打开反馈页面: {str(e)}")
    
    def logout(self):
        """用户注销"""
        reply = QMessageBox.question(
            self,
            self.i18n.t("logout"),
            f"{self.i18n.t('logout')}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 清除用户信息
            self.config_manager.logout()
            
            # 关闭当前窗口
            self.close()
            
            # 重新启动应用程序
            self.__init__()
            self.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DeepSeekApp()
    window.show()
    sys.exit(app.exec_())