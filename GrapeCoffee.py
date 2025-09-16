# -*- coding:utf-8 -*-
# Suzhou Jainkre Electronic Technologies Co.,Ltd. (c)2018-2025
import sys
import json
import random
import urllib
import re
from datetime import datetime
from hashlib import md5
from typing import List, Callable
import os
import tempfile
import httplib2
import requests
import win32clipboard as w
import win32con
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QGroupBox, QRadioButton, QButtonGroup, QMessageBox, QProgressBar, QTabWidget, QScrollArea, QSizePolicy, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QStyleFactory, QSystemTrayIcon, QMenu, QApplication
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor, QAction, QIcon
from config import icon_base64, wxpay_base64
import base64
from PySide6.QtGui import QPixmap, QIcon
from PySide6 import QtGui
_year = datetime.now().year
CONFIG_FILE = os.path.join(os.path.expanduser('~'), '.GrapeCoffee_config.json')

class JeikuClass(object):

    def gettime(self):
        tm = '%Y{y}%m{m}%d{d} %H{h}%M{m1}%S{s}'
        return datetime.now().strftime(tm).format(y='-', m='-', d='', h=':', m1=':', s='')
jclass = JeikuClass()

class Clipboard(object):

    def get(self):
        w.OpenClipboard()
        board_values = w.GetClipboardData(win32con.CF_UNICODETEXT)
        w.CloseClipboard()
        return board_values

    def set(self, a_string):
        w.OpenClipboard()
        w.EmptyClipboard()
        w.SetClipboardData(win32con.CF_UNICODETEXT, a_string)
        w.CloseClipboard()

class NoWheelComboBox(QComboBox):

    def __init__(self, parent=None):
        super().__init__(parent)

    def wheelEvent(self, event):
        event.ignore()

def check_single_instance_with_file(name):
    try:
        pid_file_path = os.path.join(tempfile.gettempdir(), f'{name}.pid')
        if os.path.exists(pid_file_path):
            with open(pid_file_path, 'r') as f:
                try:
                    pid = int(f.read().strip())
                except ValueError:
                    os.remove(pid_file_path)
                    with open(pid_file_path, 'w') as f:
                        f.write(str(os.getpid()))
                    return True
            if _is_process_running(pid):
                if _is_jianke_process(pid, name):
                    return False
                else:
                    os.remove(pid_file_path)
                    with open(pid_file_path, 'w') as f:
                        f.write(str(os.getpid()))
                    return True
            else:
                os.remove(pid_file_path)
                with open(pid_file_path, 'w') as f:
                    f.write(str(os.getpid()))
                return True
        else:
            with open(pid_file_path, 'w') as f:
                f.write(str(os.getpid()))
            return True
    except Exception as e:
        return True

def _is_process_running(pid):
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        try:
            if os.name == 'nt':
                import subprocess
                output = subprocess.check_output(f'tasklist /FI "PID eq {pid}"', shell=True, text=True)
                return str(pid) in output
            else:
                os.kill(pid, 0)
                return True
        except:
            return False

def _is_jianke_process(pid, name):
    try:
        import psutil
        process = psutil.Process(pid)
        process_name = process.name().lower()
        script_name = os.path.basename(sys.argv[0]).lower()
        return name.lower() in process_name or script_name in process_name
    except:
        return True

def show_single_instance_notification(QApplication, name, version):
    app_instance = QApplication.instance()
    if app_instance is None:
        app_instance = QApplication(sys.argv)
    tray_icon = QSystemTrayIcon()
    icon_bytes = base64.b64decode(icon_base64)
    pixmap = QtGui.QPixmap()
    pixmap.loadFromData(icon_bytes)
    tray_icon.setIcon(QtGui.QIcon(pixmap))
    if tray_icon.isSystemTrayAvailable():
        tray_icon.show()
        tray_icon.showMessage(f'{name} v{version}', '程序已经在运行中，请不要重复启动！', QSystemTrayIcon.Warning, 1500)
        QTimer.singleShot(2000, app_instance.quit)
        app_instance.exec_()
    else:
        print('程序已经在运行中，请不要重复启动！')

def translation_api(input_chinese_content, input_language, translation_language, appid, secretKey):
    translation_results = input_information = ''
    myurl = 'https://api.fanyi.baidu.com/api/trans/vip/translate'
    salt = random.randint(111111, 999999)
    sign = appid + input_chinese_content + str(salt) + secretKey
    m1 = md5()
    m1.update(sign.encode())
    sign = m1.hexdigest()
    myurl = myurl + '?q=' + urllib.parse.quote(input_chinese_content) + '&from=' + input_language + '&to=' + translation_language + '&appid=' + appid + '&salt=' + str(salt) + '&sign=' + sign
    try:
        cache = httplib2.Http('C:\\GrapeCoffee\\\\API_baidu\\\\cache')
        (_response, content) = cache.request(myurl)
        if _response.status == 200:
            _response = json.loads(content.decode('utf-8'))
            translation_results = _response['trans_result'][0]['dst']
            input_information = _response['trans_result'][0]['src']
        else:
            return (None, 'API服务状态出错')
    except httplib2.ServerNotFoundError:
        return (None, '服务器连接失败')
    translation = [translation_results, input_information]
    return translation

class ModelRefreshWorker(QThread):
    refresh_finished = Signal(list, str)

    def __init__(self, server_url, parent=None):
        super().__init__(parent)
        self.server_url = server_url

    def run(self):
        try:
            response = requests.get(f'{self.server_url}/api/tags', timeout=10)
            response.raise_for_status()
            models_data = response.json()
            model_names = [model['name'] for model in models_data.get('models', [])]
            self.refresh_finished.emit(model_names, '')
        except Exception as e:
            self.refresh_finished.emit([], str(e))

class UpdateCheckWorker(QThread):
    update_checked = Signal(dict, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.github_repo = 'JAINKRE/GrapeCoffee'

    def run(self):
        try:
            url = f'https://api.github.com/repos/{self.github_repo}/releases/latest'
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            release_data = response.json()
            update_info = {'version': release_data.get('tag_name', ''), 'download_url': '', 'release_notes': release_data.get('body', '')}
            assets = release_data.get('assets', [])
            for asset in assets:
                if asset.get('name', '') == 'GrapeCoffee-x64_Setup.exe':
                    update_info['download_url'] = asset.get('browser_download_url', '')
                    break
            self.update_checked.emit(update_info, '')
        except Exception as e:
            self.update_checked.emit({}, str(e))

class UpdateDownloadWorker(QThread):
    download_progress = Signal(int)
    download_finished = Signal(str, str)

    def __init__(self, download_url, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.is_cancelled = False

    def run(self):
        try:
            download_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            file_path = os.path.join(download_dir, 'GrapeCoffee-x64_Setup.exe')
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.is_cancelled:
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = int(downloaded_size / total_size * 100)
                            self.download_progress.emit(progress)
            self.download_finished.emit(file_path, '')
        except Exception as e:
            self.download_finished.emit('', str(e))

class OllamaAigc(object):

    def __init__(self, _send_chat_url, _model, _stream, _temperature, _prompt_template, _timeout=60):
        self.send_chat_url = _send_chat_url
        self.model = _model
        self.stream = _stream
        self.temperature = _temperature
        self.prompt_template = _prompt_template
        self.timeout = _timeout

    def send_chat_request(self, translate_word):
        prompt = self.prompt_template.format(translate_word=translate_word)
        messages = [{'role': 'user', 'content': prompt}]
        payload = {'model': self.model, 'messages': messages, 'stream': self.stream, 'temperature': self.temperature}
        try:
            response = requests.post(self.send_chat_url, json=payload, timeout=self.timeout, stream=self.stream)
            if self.stream:
                return response
            else:
                response.raise_for_status()
                chat_response = response.json()
                return chat_response
        except requests.exceptions.RequestException as e:
            return None

class Convert(object):

    def case_01(self, words):
        if not words:
            return ''
        camel_case = '_' + words[0].lower()
        for word in words[1:]:
            camel_case += word.capitalize()
        return camel_case

    def case_02(self, words):
        if not words:
            return ''
        special_method = '__' + '__'.join(words).lower() + '__'
        return special_method

    def case_03(self, words):
        if not words:
            return ''
        camel_case = words[0].lower()
        for word in words[1:]:
            camel_case += word.capitalize()
        return camel_case

    def case_04(self, words):
        if not words:
            return ''
        pascal_case = ''.join((word.capitalize() for word in words))
        return pascal_case

    def case_05(self, words):
        if not words:
            return ''
        snake_case = '_'.join((word.lower() for word in words))
        return snake_case

    def case_06(self, words):
        if not words:
            return ''
        type_prefix = 'str'
        variable_name = ''.join((word.capitalize() for word in words))
        return f'{type_prefix}{variable_name}'

    def case_07(self, words):
        if not words:
            return ''
        kebab_case = '-'.join((word.lower() for word in words))
        return kebab_case

    def case_08(self, words):
        if not words:
            return ''
        constants_case = '_'.join((word.upper() for word in words))
        return constants_case

    def convert_warr(self, _warr, naming_func):
        return naming_func(_warr)

class TranslationWorker(QThread):
    translation_finished = Signal(str, str, str)
    progress_updated = Signal(int)
    stream_chunk_received = Signal(str)

    def __init__(self, mode, input_text, ollama_config=None, api_config=None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.input_text = input_text
        self.ollama_config = ollama_config or {}
        self.api_config = api_config or {}
        self.is_cancelled = False

    def run(self):
        try:
            self.progress_updated.emit(20)
            if self.mode == 'API翻译':
                InputLanguage = 'auto'
                TranslationLanguage = 'en'
                appid = self.api_config.get('appid', '')
                secretKey = self.api_config.get('secretKey', '')
                (TranslationResults, InputInformation) = translation_api(self.input_text, InputLanguage, TranslationLanguage, appid, secretKey)
                if TranslationResults is None:
                    self.translation_finished.emit('', InputInformation, '')
                    return
                result = TranslationResults
                raw_response = ''
            else:
                ollama_server = self.ollama_config.get('server')
                model = self.ollama_config.get('model')
                stream = self.ollama_config.get('stream', False)
                temperature = self.ollama_config.get('temperature')
                prompt_template = self.ollama_config.get('prompt_template')
                timeout = self.ollama_config.get('timeout', 600)
                send_chat_url = f'{ollama_server}/api/chat'
                response = OllamaAigc(send_chat_url, model, stream, temperature, prompt_template, timeout).send_chat_request(self.input_text)
                if response is None:
                    self.translation_finished.emit('', 'Ollama接口调用失败，请检查服务器地址和模型是否正确', '')
                    return
                if stream:
                    full_response = ''
                    for line in response.iter_lines():
                        if self.is_cancelled:
                            return
                        if line:
                            try:
                                decoded_line = line.decode('utf-8')
                                if decoded_line.startswith('data: '):
                                    json_str = decoded_line[6:]
                                    if json_str.strip() == '[DONE]':
                                        break
                                    try:
                                        data = json.loads(json_str)
                                        if 'message' in data and 'content' in data['message']:
                                            chunk = data['message']['content']
                                            full_response += chunk
                                            self.stream_chunk_received.emit(chunk)
                                    except json.JSONDecodeError:
                                        pass
                                else:
                                    try:
                                        data = json.loads(decoded_line)
                                        if 'message' in data and 'content' in data['message']:
                                            chunk = data['message']['content']
                                            full_response += chunk
                                            self.stream_chunk_received.emit(chunk)
                                    except json.JSONDecodeError:
                                        pass
                            except UnicodeDecodeError:
                                pass
                    result = full_response.replace('_', ' ')
                    raw_response = full_response
                else:
                    response.raise_for_status()
                    data = response.json()
                    result = data['message']['content'].replace('_', ' ')
                    raw_response = data['message']['content']
            self.progress_updated.emit(100)
            self.translation_finished.emit(result, '', raw_response)
        except Exception as e:
            self.translation_finished.emit('', str(e), '')

class NamingResultWidget(QWidget):

    def __init__(self, index: int, title: str, result: str, copy_callback: Callable, parent=None):
        super().__init__(parent)
        self.result = result
        self.index = index
        self.copy_callback = copy_callback
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        index_label = QLabel(f'{index + 1}.')
        index_label.setStyleSheet('font-weight: bold; color: #3498db;')
        index_label.setFixedWidth(20)
        layout.addWidget(index_label)
        title_label = QLabel(title)
        title_label.setStyleSheet('font-weight: bold;')
        layout.addWidget(title_label, 1)
        result_label = QLabel(result)
        result_label.setStyleSheet('font-family: Consolas;')
        result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(result_label, 2)
        copy_btn = QPushButton('复制')
        copy_btn.setFixedWidth(60)
        copy_btn.clicked.connect(self.copy_result)
        layout.addWidget(copy_btn)

    def copy_result(self):
        self.copy_callback(self.result)

class MainUI(QMainWindow):

    def __init__(self):
        super().__init__()
        if not check_single_instance_with_file(name):
            show_single_instance_notification(QApplication, name, version)
            QApplication.quit()
            sys.exit(0)
        self.translation_worker = None
        self.model_refresh_worker = None
        self.update_check_worker = None
        self.update_download_worker = None
        self.shortcuts = []
        self.naming_results = []
        self.config = self.load_config()
        self.init_ui()
        self.tray_icon = None
        self.init_tray_icon()
        QTimer.singleShot(100, self.auto_refresh_models)
        self.init_shortcuts()
        if self.config.get('auto_update', True):
            QTimer.singleShot(2000, self.check_for_updates)

    def init_ui(self):
        self.setWindowTitle(f'{name} v{version}')
        self.setGeometry(100, 100, 580, 700)
        self.setMinimumSize(580, 550)
        try:
            image_data = base64.b64decode(icon_base64)
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            icon = QIcon(pixmap)
            self.setWindowIcon(icon)
        except Exception as e:
            print(f'设置窗口图标失败: {e}')
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        translation_tab = self.create_translation_tab()
        tab_widget.addTab(translation_tab, '变量名翻译')
        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, '设置')
        self.statusBar().showMessage('就绪')
        if self.config.get('always_on_top', False):
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()

    def init_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.windowIcon())
        tray_menu = QMenu()
        self.toggle_window_action = QAction('查看项目/帮助', self)
        self.toggle_window_action.triggered.connect(self.open_github_page)
        tray_menu.addAction(self.toggle_window_action)
        self.toggle_window_action = QAction('显示/隐藏窗口', self)
        self.toggle_window_action.triggered.connect(self.toggle_window_visibility)
        tray_menu.addAction(self.toggle_window_action)
        tray_menu.addSeparator()
        quit_action = QAction('退出', self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def toggle_window_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_window_visibility()

    def quit_application(self):
        if self.translation_worker and self.translation_worker.isRunning():
            self.translation_worker.is_cancelled = True
            self.translation_worker.quit()
            self.translation_worker.wait()
        if self.model_refresh_worker and self.model_refresh_worker.isRunning():
            self.model_refresh_worker.quit()
            self.model_refresh_worker.wait()
        if self.update_check_worker and self.update_check_worker.isRunning():
            self.update_check_worker.quit()
            self.update_check_worker.wait()
        if self.update_download_worker and self.update_download_worker.isRunning():
            self.update_download_worker.is_cancelled = True
            self.update_download_worker.quit()
            self.update_download_worker.wait()
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()

    def change_theme(self, theme_name):
        if theme_name:
            QApplication.setStyle(QStyleFactory.create(theme_name))
            self.config['theme'] = theme_name

    def create_translation_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        input_group = QGroupBox('输入变量名')
        input_layout = QVBoxLayout(input_group)
        input_row_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText('请输入中文变量名，如：葡萄咖啡')
        self.input_edit.returnPressed.connect(self.start_translation)
        input_row_layout.addWidget(self.input_edit)
        auto_copy_layout = QHBoxLayout()
        auto_copy_layout.addWidget(QLabel('翻译后自动复制:'))
        self.auto_copy_combo = QComboBox()
        self.auto_copy_combo.addItem('不自动复制', -1)
        self.auto_copy_combo.addItem('1.私有成员', 0)
        self.auto_copy_combo.addItem('2.特殊方法', 1)
        self.auto_copy_combo.addItem('3.驼峰命名法', 2)
        self.auto_copy_combo.addItem('4.帕斯卡命名法', 3)
        self.auto_copy_combo.addItem('5.蛇形命名法', 4)
        self.auto_copy_combo.addItem('6.匈牙利命名法', 5)
        self.auto_copy_combo.addItem('7.烤肉串命名法', 6)
        self.auto_copy_combo.addItem('8.常量命名法', 7)
        auto_copy_index = self.config.get('auto_copy_index', -1)
        if auto_copy_index >= -1 and auto_copy_index <= 7:
            self.auto_copy_combo.setCurrentIndex(auto_copy_index + 1)
        auto_copy_layout.addWidget(self.auto_copy_combo)
        input_row_layout.addLayout(auto_copy_layout)
        input_layout.addLayout(input_row_layout)
        mode_group = QGroupBox('翻译模式')
        mode_layout = QHBoxLayout(mode_group)
        self.api_radio = QRadioButton('API翻译')
        self.model_radio = QRadioButton('大模型翻译')
        if self.config.get('default_mode', '大模型翻译') == '大模型翻译':
            self.model_radio.setChecked(True)
        else:
            self.api_radio.setChecked(True)
        mode_group_box = QButtonGroup()
        mode_group_box.addButton(self.api_radio, 1)
        mode_group_box.addButton(self.model_radio, 2)
        mode_layout.addWidget(self.api_radio)
        mode_layout.addWidget(self.model_radio)
        mode_layout.addStretch()
        model_layout = QHBoxLayout()
        model_layout.addStretch()
        model_layout.addWidget(QLabel('模型名称:'))
        self.translation_model_combo = QComboBox()
        models = self.config.get('ollama_models', [''])
        self.translation_model_combo.addItems(models)
        current_model = self.config.get('ollama_model', '')
        if current_model in models:
            self.translation_model_combo.setCurrentText(current_model)
        else:
            self.translation_model_combo.setEditText(current_model)
        self.translation_model_combo.setMinimumWidth(200)
        model_layout.addWidget(self.translation_model_combo)
        mode_layout.addLayout(model_layout)
        self.translation_model_combo.currentTextChanged.connect(self.sync_model_combo)
        prefix_suffix_group = QGroupBox('变量前缀和后缀')
        prefix_suffix_layout = QHBoxLayout(prefix_suffix_group)
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText('设置变量名前缀（可选）')
        prefix_suffix_layout.addWidget(QLabel('前缀:'))
        prefix_suffix_layout.addWidget(self.prefix_edit)
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText('设置变量名后缀（可选）')
        prefix_suffix_layout.addWidget(QLabel('后缀:'))
        prefix_suffix_layout.addWidget(self.suffix_edit)
        button_layout = QHBoxLayout()
        self.translate_btn = QPushButton('开始翻译')
        self.translate_btn.clicked.connect(self.start_translation)
        self.translate_btn.setFixedHeight(40)
        self.cancel_btn = QPushButton('取消')
        self.cancel_btn.clicked.connect(self.cancel_translation)
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.translate_btn)
        button_layout.addWidget(self.cancel_btn)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(15)
        result_group = QGroupBox('翻译结果')
        result_layout = QVBoxLayout(result_group)
        result_layout.setContentsMargins(0, 0, 0, 0)
        self.result_tab_widget = QTabWidget()
        self.result_tab_widget.setTabPosition(QTabWidget.South)
        self.standard_result_widget = QWidget()
        standard_layout = QVBoxLayout(self.standard_result_widget)
        standard_layout.setContentsMargins(5, 5, 5, 5)
        self.result_area = QScrollArea()
        self.result_area.setWidgetResizable(True)
        self.result_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_area.setStyleSheet('\n            QScrollArea {\n                border: 1px solid #bdc3c7;\n                border-radius: 4px;\n            }\n        ')
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setSpacing(5)
        self.result_layout.addStretch()
        self.result_area.setWidget(self.result_container)
        standard_layout.addWidget(self.result_area)
        self.raw_output_widget = QWidget()
        raw_layout = QVBoxLayout(self.raw_output_widget)
        raw_layout.setContentsMargins(5, 5, 5, 5)
        self.raw_output_text = QTextEdit()
        self.raw_output_text.setReadOnly(True)
        self.raw_output_text.setStyleSheet('\n            QTextEdit {\n                border: 1px solid #bdc3c7;\n                border-radius: 4px;\n                font-family: Consolas;\n            }\n        ')
        raw_layout.addWidget(self.raw_output_text)
        self.result_tab_widget.addTab(self.standard_result_widget, '标准结果')
        self.result_tab_widget.addTab(self.raw_output_widget, '大模型原始输出')
        result_layout.addWidget(self.result_tab_widget)
        result_layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(input_group)
        layout.addWidget(mode_group)
        layout.addWidget(prefix_suffix_group)
        layout.addLayout(button_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(result_group)
        layout.setStretchFactor(result_group, 1)
        layout.addStretch()
        return tab

    def sync_model_combo(self, text):
        if hasattr(self, 'model_combo'):
            self.model_combo.blockSignals(True)
            self.model_combo.setEditText(text)
            self.model_combo.blockSignals(False)

    def create_settings_tab(self):
        tab = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet('\n            QScrollArea {\n                border: none;\n                background: transparent;\n            }\n            QScrollArea > QWidget > QWidget {\n                background: transparent;\n            }\n        ')
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(15)
        ollama_group = QGroupBox('Ollama大模型设置')
        ollama_layout = QVBoxLayout(ollama_group)
        server_layout = QHBoxLayout()
        server_layout.addWidget(QLabel('模型地址:'))
        self.server_edit = QLineEdit(self.config.get('ollama_server'))
        server_layout.addWidget(self.server_edit)
        ollama_layout.addLayout(server_layout)
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel('模型名称:'))
        self.model_combo = QComboBox()
        self.model_combo.setPlaceholderText('请选择或输入模型名称')
        models = self.config.get('ollama_models')
        self.model_combo.addItems(models)
        current_model = self.config.get('ollama_model')
        if current_model in models:
            self.model_combo.setCurrentText(current_model)
        else:
            self.model_combo.setEditText(current_model)
        self.refresh_btn = QPushButton('刷新模型列表')
        self.refresh_btn.clicked.connect(self.refresh_models)
        self.refresh_btn.setFixedWidth(100)
        model_layout.addWidget(self.model_combo, 1)
        model_layout.addWidget(self.refresh_btn)
        ollama_layout.addLayout(model_layout)
        params_layout = QHBoxLayout()
        temp_layout = QHBoxLayout()
        temp_label = QLabel('温度参数:')
        self.temp_edit = QLineEdit(str(self.config.get('ollama_temperature', 0.0)))
        self.temp_edit.setFixedWidth(100)
        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.temp_edit)
        params_layout.addLayout(temp_layout)
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel('请求超时(秒):')
        self.timeout_edit = QLineEdit(str(self.config.get('ollama_timeout', 60)))
        self.timeout_edit.setFixedWidth(100)
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(self.timeout_edit)
        params_layout.addLayout(timeout_layout)
        stream_layout = QHBoxLayout()
        stream_layout.addWidget(QLabel('流式输出:'))
        self.stream_checkbox = QCheckBox('启用')
        self.stream_checkbox.setChecked(self.config.get('ollama_stream', True))
        stream_layout.addWidget(self.stream_checkbox)
        params_layout.addLayout(stream_layout)
        params_layout.addStretch()
        ollama_layout.addLayout(params_layout)
        prompt_layout = QVBoxLayout()
        prompt_label = QLabel('提示词模板:')
        prompt_layout.addWidget(prompt_label)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.prompt_edit.setStyleSheet('\n            QTextEdit {\n                border: 1px solid #bdc3c7;\n                border-radius: 4px;\n                font-family: Consolas;\n            }\n        ')
        self.prompt_edit.setMinimumHeight(150)
        prompt_template = self.config.get('ollama_prompt_template', 'You are a professional software variable name assistant integrated into the program as part of an API. Your task is to accurately translate the provided Chinese variable name: `{translate_word}` into the corresponding English variable name. The translated variable name should be in lowercase with words separated by spaces. Ensure that the output contains only lowercase letters and spaces, with no other characters or symbols. Output only the translated result, without any additional content.')
        self.prompt_edit.setPlainText(prompt_template)
        prompt_layout.addWidget(self.prompt_edit)
        prompt_note = QLabel('提示：提示词必须包含 `{translate_word}` 以传递输入变量名给大模型')
        prompt_note.setStyleSheet('color: #999999; font-size: 12px;')
        prompt_layout.addWidget(prompt_note)
        ollama_layout.addLayout(prompt_layout)
        api_group = QGroupBox('百度翻译 API设置')
        api_layout = QHBoxLayout(api_group)
        appid_layout = QHBoxLayout()
        appid_layout.addWidget(QLabel('AppID'))
        self.appid_edit = QLineEdit(self.config.get('baidu_appid', ''))
        appid_layout.addWidget(self.appid_edit)
        api_layout.addLayout(appid_layout)
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel('SecretKey'))
        self.key_edit = QLineEdit(self.config.get('baidu_secretKey', ''))
        key_layout.addWidget(self.key_edit)
        api_layout.addLayout(key_layout)
        theme_group = QGroupBox('主题设置')
        theme_layout = QVBoxLayout(theme_group)
        theme_layout.addWidget(QLabel('请下拉选择主题:'))
        self.theme_combo = NoWheelComboBox()
        available_styles = QStyleFactory.keys()
        self.theme_combo.addItems(available_styles)
        current_theme = self.config.get('theme', QApplication.style().objectName())
        if current_theme in available_styles:
            self.theme_combo.setCurrentText(current_theme)
        else:
            self.theme_combo.setCurrentText(available_styles[0] if available_styles else '')
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        theme_layout.addWidget(self.theme_combo)
        theme_note = QLabel('主题将自动跟随系统颜色实现亮暗切换（如果支持），保存后重启生效🙂')
        theme_note.setStyleSheet('color: #999999; font-size: 12px;')
        theme_layout.addWidget(theme_note)
        window_group = QGroupBox('窗口设置')
        window_layout = QVBoxLayout(window_group)
        self.always_on_top_checkbox = QCheckBox('窗口置顶')
        self.always_on_top_checkbox.setChecked(self.config.get('always_on_top', False))
        self.always_on_top_checkbox.toggled.connect(self.toggle_always_on_top)
        window_layout.addWidget(self.always_on_top_checkbox)
        self.minimize_to_tray_checkbox = QCheckBox('关闭时最小化到托盘')
        self.minimize_to_tray_checkbox.setChecked(self.config.get('minimize_to_tray', True))
        window_layout.addWidget(self.minimize_to_tray_checkbox)
        tray_note = QLabel('启用后，点击关闭按钮将隐藏到系统托盘而不是退出程序')
        tray_note.setStyleSheet('color: #999999; font-size: 12px;')
        window_layout.addWidget(tray_note)
        update_group = QGroupBox('更新设置')
        update_layout = QHBoxLayout(update_group)
        update_layout.addWidget(QLabel('自动更新:'))
        self.auto_update_checkbox = QCheckBox()
        self.auto_update_checkbox.setChecked(self.config.get('auto_update', True))
        update_layout.addWidget(self.auto_update_checkbox)
        self.check_update_btn = QPushButton('检查更新')
        self.check_update_btn.clicked.connect(self.check_for_updates)
        update_layout.addWidget(self.check_update_btn)
        update_layout.addStretch()
        about_group = QGroupBox('关于')
        about_layout = QVBoxLayout(about_group)
        about_text = QLabel(f'\n        <p><b>{name} v{version}</b></p>\n        <p>智能变量名翻译工具，支持多种命名规范，可帮助开发者快速生成符合规范的变量名。</p>\n        <p>支持翻译API和Ollama大模型两种翻译方式，提供丰富的自定义选项。</p>\n        <p>© 2025-{_year} 保留所有权</p>\n        <div></div>\n        ')
        about_text.setWordWrap(True)
        about_layout.addWidget(about_text)
        button_layout = QHBoxLayout()
        self.view_project_btn = QPushButton('查看项目')
        self.view_project_btn.clicked.connect(self.open_github_page)
        self.view_project_btn.setFixedWidth(100)
        button_layout.addWidget(self.view_project_btn)
        self.donate_btn = QPushButton('赞赏支持')
        self.donate_btn.clicked.connect(self.show_donate_dialog)
        self.donate_btn.setFixedWidth(100)
        button_layout.addWidget(self.donate_btn)
        self.view_project_btn = QPushButton('建议反馈')
        self.view_project_btn.clicked.connect(self.open_github_issue_page)
        self.view_project_btn.setFixedWidth(100)
        button_layout.addWidget(self.view_project_btn)
        about_layout.addLayout(button_layout)
        shortcut_group = QGroupBox('快捷键设置')
        shortcut_layout = QVBoxLayout(shortcut_group)
        self.enable_shortcuts_checkbox = QCheckBox('启用快捷键 (仅应用内生效)')
        self.enable_shortcuts_checkbox.setChecked(self.config.get('enable_shortcuts', True))
        shortcut_layout.addWidget(self.enable_shortcuts_checkbox)
        shortcut_note = QLabel('使用 Ctrl+s 保存设置')
        shortcut_layout.addWidget(shortcut_note)
        shortcut_note = QLabel('使用 Ctrl+Alt+数字键 复制对应序号的变量名:')
        shortcut_layout.addWidget(shortcut_note)
        self.shortcut_table = QTableWidget(8, 2)
        self.shortcut_table.setMinimumHeight(200)
        self.shortcut_table.setHorizontalHeaderLabels(['快捷键', '变量命名规则'])
        self.shortcut_table.verticalHeader().setVisible(False)
        self.shortcut_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.shortcut_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        shortcut_names = ['Ctrl+Alt+1', 'Ctrl+Alt+2', 'Ctrl+Alt+3', 'Ctrl+Alt+4', 'Ctrl+Alt+5', 'Ctrl+Alt+6', 'Ctrl+Alt+7', 'Ctrl+Alt+8']
        naming_rules = ['私有成员', '特殊方法', '驼峰命名法 (camelCase)', '帕斯卡命名法 (PascalCase)', '蛇形命名法 (snake_case)', '匈牙利命名法', '烤肉串命名法 (kebab-case)', '常量命名法 (CONSTANT_CASE)']
        for i in range(8):
            self.shortcut_table.setItem(i, 0, QTableWidgetItem(shortcut_names[i]))
            self.shortcut_table.setItem(i, 1, QTableWidgetItem(naming_rules[i]))
        shortcut_layout.addWidget(self.shortcut_table)
        button_layout = QHBoxLayout()
        restore_btn = QPushButton('恢复默认')
        restore_btn.clicked.connect(self.restore_default_settings)
        restore_btn.setFixedHeight(25)
        save_btn = QPushButton('保存设置')
        save_btn.clicked.connect(self.save_settings)
        save_btn.setFixedHeight(25)
        button_layout.addWidget(restore_btn)
        button_layout.addWidget(save_btn)
        layout.addWidget(ollama_group)
        layout.addWidget(api_group)
        layout.addWidget(shortcut_group)
        layout.addWidget(theme_group)
        layout.addWidget(window_group)
        layout.addWidget(update_group)
        layout.addWidget(about_group)
        layout.addLayout(button_layout)
        layout.addStretch()
        scroll_area.setWidget(content_widget)
        main_layout = QVBoxLayout(tab)
        main_layout.addWidget(scroll_area)
        self.model_combo.currentTextChanged.connect(self.sync_translation_model_combo)
        return tab

    def show_donate_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('赞赏支持')
        dialog.setFixedSize(380, 450)
        layout = QVBoxLayout(dialog)
        title_label = QLabel('赞赏支持')
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet('font-size: 16px; font-weight: bold; margin: 10px;')
        layout.addWidget(title_label)
        description_label = QLabel('项目本身是开源免费无偿的\n如果对您有帮助，欢迎赞赏支持！')
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignCenter)
        description_label.setStyleSheet('margin: 10px;')
        layout.addWidget(description_label)
        qr_layout = QHBoxLayout()
        wx_layout = QVBoxLayout()
        wx_label = QLabel('微信支付')
        wx_label.setAlignment(Qt.AlignCenter)
        try:
            wx_image_data = base64.b64decode(wxpay_base64)
            wx_pixmap = QPixmap()
            wx_pixmap.loadFromData(wx_image_data)
            wx_pixmap = wx_pixmap.scaled(350, 350, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            wx_image_label = QLabel()
            wx_image_label.setPixmap(wx_pixmap)
            wx_image_label.setAlignment(Qt.AlignCenter)
            wx_layout.addWidget(wx_image_label)
        except Exception as e:
            wx_image_label = QLabel('无法加载微信二维码')
            wx_image_label.setAlignment(Qt.AlignCenter)
            wx_layout.addWidget(wx_image_label)
        wx_layout.addWidget(wx_label)
        qr_layout.addLayout(wx_layout)
        layout.addLayout(qr_layout)
        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        dialog.exec()

    def sync_translation_model_combo(self, text):
        if hasattr(self, 'translation_model_combo'):
            self.translation_model_combo.blockSignals(True)
            self.translation_model_combo.setEditText(text)
            self.translation_model_combo.blockSignals(False)

    def open_github_page(self):
        import webbrowser
        try:
            webbrowser.open('https://github.com/JAINKRE/GrapeCoffee')
            self.statusBar().showMessage('正在打开项目页面...')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'无法打开浏览器: {str(e)}')

    def open_github_issue_page(self):
        import webbrowser
        try:
            webbrowser.open('https://github.com/JAINKRE/GrapeCoffee/issues')
            self.statusBar().showMessage('正在打开项目issue页面...')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'无法打开浏览器: {str(e)}')

    def toggle_always_on_top(self, checked):
        if checked:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.show()

    def init_shortcuts(self):
        for shortcut in self.shortcuts:
            shortcut.setEnabled(False)
        self.shortcuts.clear()
        for i in range(1, 9):
            shortcut = QShortcut(QKeySequence(f'Ctrl+Alt+{i}'), self)
            shortcut.activated.connect(lambda idx=i: self.copy_result_by_index(idx - 1))
            self.shortcuts.append(shortcut)
        save_shortcut = QShortcut(QKeySequence('Ctrl+S'), self)
        save_shortcut.activated.connect(self.save_settings)
        self.shortcuts.append(save_shortcut)

    def copy_result_by_index(self, index):
        if not self.config.get('enable_shortcuts', True):
            return
        if 0 <= index < len(self.naming_results):
            try:
                Clipboard().set(self.naming_results[index])
                self.statusBar().showMessage(f"已复制 '{self.naming_results[index]}' 到剪贴板")
            except Exception as e:
                QMessageBox.critical(self, '复制失败', f'复制到剪贴板失败: {str(e)}')
        else:
            self.statusBar().showMessage('无效的快捷键索引')

    def auto_refresh_models(self):
        if self.model_radio.isChecked():
            server_url = self.server_edit.text().strip()
            if server_url:
                self.model_refresh_worker = ModelRefreshWorker(server_url)
                self.model_refresh_worker.refresh_finished.connect(self.on_auto_model_refresh_finished)
                self.model_refresh_worker.start()

    def on_auto_model_refresh_finished(self, model_names, error):
        if error:
            QMessageBox.critical(self, '刷新失败', f'自动获取模型列表时出错: {error}')
        else:
            current_text = self.model_combo.currentText()
            self.model_combo.clear()
            self.model_combo.addItems(model_names)
            if hasattr(self, 'translation_model_combo'):
                self.translation_model_combo.clear()
                self.translation_model_combo.addItems(model_names)
            if current_text in model_names:
                self.model_combo.setCurrentText(current_text)
                if hasattr(self, 'translation_model_combo'):
                    self.translation_model_combo.setCurrentText(current_text)
            elif model_names:
                self.model_combo.setCurrentIndex(0)
                if hasattr(self, 'translation_model_combo'):
                    self.translation_model_combo.setCurrentIndex(0)
            self.statusBar().showMessage(f'自动刷新模型列表成功，共 {len(model_names)} 个模型')

    def refresh_models(self):
        server_url = self.server_edit.text().strip()
        if not server_url:
            QMessageBox.warning(self, '服务器地址错误', '请先输入Ollama服务器地址')
            return
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText('刷新中...')
        self.statusBar().showMessage('正在获取模型列表...')
        self.model_refresh_worker = ModelRefreshWorker(server_url)
        self.model_refresh_worker.refresh_finished.connect(self.on_model_refresh_finished)
        self.model_refresh_worker.start()

    def on_model_refresh_finished(self, model_names, error):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText('刷新模型列表')
        if error:
            self.model_combo.clear()
            if hasattr(self, 'translation_model_combo'):
                self.translation_model_combo.clear()
            QMessageBox.critical(self, '刷新失败', f'获取模型列表时出错: {error}')
            self.statusBar().showMessage('获取模型列表失败')
        else:
            current_text = self.model_combo.currentText()
            self.model_combo.clear()
            self.model_combo.addItems(model_names)
            if hasattr(self, 'translation_model_combo'):
                self.translation_model_combo.clear()
                self.translation_model_combo.addItems(model_names)
            if current_text in model_names:
                self.model_combo.setCurrentText(current_text)
                if hasattr(self, 'translation_model_combo'):
                    self.translation_model_combo.setCurrentText(current_text)
            elif model_names:
                self.model_combo.setCurrentIndex(0)
                if hasattr(self, 'translation_model_combo'):
                    self.translation_model_combo.setCurrentIndex(0)
            QMessageBox.information(self, '刷新成功', f'成功获取到 {len(model_names)} 个模型')
            self.statusBar().showMessage(f'模型列表更新成功，共 {len(model_names)} 个模型')

    def check_for_updates(self):
        self.check_update_btn.setEnabled(False)
        self.check_update_btn.setText('检查中...')
        self.statusBar().showMessage('正在检查更新...')
        self.update_check_worker = UpdateCheckWorker()
        self.update_check_worker.update_checked.connect(self.on_update_checked)
        self.update_check_worker.start()

    def on_update_checked(self, update_info, error):
        self.check_update_btn.setEnabled(True)
        self.check_update_btn.setText('立即检查更新')
        if error:
            self.statusBar().showMessage('检查更新完成')
            return
        if not update_info or not update_info.get('version'):
            QMessageBox.information(self, '检查更新', '无法获取版本信息')
            self.statusBar().showMessage('检查更新完成')
            return
        latest_version = update_info['version']
        current_version = f'v{version}'
        if latest_version > current_version:
            reply = QMessageBox.information(self, '发现新版本', f'发现新版本 {latest_version}，当前版本 {current_version}\n\n是否下载更新？', QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                if not update_info.get('download_url'):
                    QMessageBox.critical(self, '下载失败', '未找到下载链接')
                    return
                self.download_update(update_info['download_url'])
        else:
            self.statusBar().showMessage('已是最新版本')

    def download_update(self, download_url):
        self.download_progress_dialog = QDialog(self)
        self.download_progress_dialog.setWindowTitle('下载更新')
        self.download_progress_dialog.setFixedSize(200, 100)
        self.download_progress_dialog.setModal(True)
        layout = QVBoxLayout(self.download_progress_dialog)
        label = QLabel('正在下载更新...')
        layout.addWidget(label)
        self.download_progress_bar = QProgressBar()
        self.download_progress_bar.setRange(0, 100)
        layout.addWidget(self.download_progress_bar)
        cancel_btn = QPushButton('取消')
        layout.addWidget(cancel_btn)
        cancel_btn.clicked.connect(self.cancel_download)
        cancel_btn.clicked.connect(self.download_progress_dialog.close)
        self.download_progress_dialog.show()
        self.update_download_worker = UpdateDownloadWorker(download_url)
        self.update_download_worker.download_progress.connect(self.on_download_progress)
        self.update_download_worker.download_finished.connect(self.on_download_finished)
        self.update_download_worker.start()

    def on_download_progress(self, progress):
        if hasattr(self, 'download_progress_bar'):
            self.download_progress_bar.setValue(progress)

    def on_download_finished(self, file_path, error):
        if hasattr(self, 'download_progress_dialog'):
            self.download_progress_dialog.close()
        if error:
            QMessageBox.critical(self, '下载失败', f'下载更新时出错: {error}')
            self.statusBar().showMessage('下载更新失败')
            return
        try:
            os.startfile(file_path)
            self.close()
        except Exception as e:
            QMessageBox.critical(self, '安装失败', f'启动安装程序时出错: {str(e)}')

    def cancel_download(self):
        if self.update_download_worker and self.update_download_worker.isRunning():
            self.update_download_worker.is_cancelled = True
            self.statusBar().showMessage('已取消下载')

    def start_translation(self):
        input_text = self.input_edit.text().strip()
        if not input_text:
            QMessageBox.warning(self, '输入错误', '请输入变量名')
            return
        mode = 'API翻译' if self.api_radio.isChecked() else '大模型翻译'
        if mode == '大模型翻译':
            server_url = self.server_edit.text().strip()
            model_name = self.translation_model_combo.currentText().strip()
            if not server_url:
                QMessageBox.warning(self, '配置错误', '请在设置中配置Ollama服务器地址')
                return
            if not model_name:
                QMessageBox.warning(self, '配置错误', '请选择或输入模型名称')
                return
        self.translate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage('正在翻译...')
        self.clear_results()
        self.raw_output_text.clear()
        ollama_config = {'server': self.server_edit.text().strip(), 'model': self.translation_model_combo.currentText().strip(), 'temperature': float(self.temp_edit.text().strip() or '0.0'), 'timeout': int(self.timeout_edit.text().strip() or '60'), 'stream': self.stream_checkbox.isChecked(), 'prompt_template': self.prompt_edit.toPlainText()}
        api_config = {'appid': self.appid_edit.text().strip(), 'secretKey': self.key_edit.text().strip()}
        self.translation_worker = TranslationWorker(mode, input_text, ollama_config, api_config)
        self.translation_worker.translation_finished.connect(self.on_translation_finished)
        self.translation_worker.progress_updated.connect(self.progress_bar.setValue)
        self.translation_worker.stream_chunk_received.connect(self.on_stream_chunk_received)
        self.translation_worker.start()

    def on_stream_chunk_received(self, chunk):
        self.raw_output_text.insertPlainText(chunk)
        cursor = self.raw_output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.raw_output_text.setTextCursor(cursor)
        self.raw_output_text.ensureCursorVisible()

    def cancel_translation(self):
        if self.translation_worker and self.translation_worker.isRunning():
            self.translation_worker.is_cancelled = True
            self.translation_worker.quit()
            self.translation_worker.wait()
            self.reset_ui_state()

    def on_translation_finished(self, result: str, error: str, raw_response: str):
        self.reset_ui_state()
        if error:
            QMessageBox.critical(self, '翻译失败', error)
            self.statusBar().showMessage('翻译失败')
            return
        if not result:
            QMessageBox.warning(self, '翻译失败', '未获得翻译结果')
            self.statusBar().showMessage('翻译失败')
            return
        if raw_response and (not self.stream_checkbox.isChecked()):
            self.raw_output_text.setPlainText(raw_response)
        elif not self.stream_checkbox.isChecked():
            self.raw_output_text.setPlainText('此功能仅在大模型翻译模式下可用')
        cleaned_result = re.sub('\\<think\\>.*?\\<\\/think\\>', '', result, flags=re.DOTALL)
        words = [word.lower() for word in cleaned_result.split() if word]
        self.display_results(words)
        self.statusBar().showMessage('翻译完成')
        auto_copy_index = self.auto_copy_combo.currentIndex() - 1
        if auto_copy_index >= 0 and auto_copy_index < len(self.naming_results):
            try:
                Clipboard().set(self.naming_results[auto_copy_index])
                self.statusBar().showMessage(f"已自动复制 '{self.naming_results[auto_copy_index]}' 到剪贴板")
            except Exception as e:
                QMessageBox.critical(self, '复制失败', f'自动复制到剪贴板失败: {str(e)}')

    def reset_ui_state(self):
        self.translate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)

    def clear_results(self):
        while self.result_layout.count() > 1:
            item = self.result_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.naming_results.clear()

    def display_results(self, words: List[str]):
        self.naming_results.clear()
        prefix = self.prefix_edit.text().strip()
        suffix = self.suffix_edit.text().strip()
        converter = Convert()
        naming_rules = [('私有成员', converter.case_01), ('特殊方法', converter.case_02), ('驼峰命名法', converter.case_03), ('帕斯卡命名法', converter.case_04), ('蛇形命名法', converter.case_05), ('匈牙利命名法', converter.case_06), ('烤肉串命名法', converter.case_07), ('常量命名法', converter.case_08)]
        for (i, (title, func)) in enumerate(naming_rules):
            result = converter.convert_warr(words, func)
            if prefix:
                if title in ['私有成员', '特殊方法']:
                    result = prefix + result
                else:
                    result = prefix + '' + result
            if suffix:
                if title in ['私有成员', '特殊方法']:
                    result = result + suffix
                else:
                    result = result + '' + suffix
            self.add_result_widget(i, title, result)
            self.naming_results.append(result)

    def add_result_widget(self, index: int, title: str, result: str):
        widget = NamingResultWidget(index, title, result, self.copy_to_clipboard)
        self.result_layout.insertWidget(self.result_layout.count() - 1, widget)

    def copy_to_clipboard(self, text: str):
        try:
            Clipboard().set(text)
            self.statusBar().showMessage(f"已复制 '{text}' 到剪贴板")
        except Exception as e:
            QMessageBox.critical(self, '复制失败', f'复制到剪贴板失败: {str(e)}')

    def restore_default_settings(self):
        reply = QMessageBox.question(self, '确认恢复', '确定要恢复所有默认设置吗？', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.config = self.get_default_config()
            self.server_edit.setText(self.config['ollama_server'])
            self.model_combo.clear()
            models = self.config['ollama_models']
            self.model_combo.addItems(models)
            current_model = self.config['ollama_model']
            if current_model in models:
                self.model_combo.setCurrentText(current_model)
            if hasattr(self, 'translation_model_combo'):
                self.translation_model_combo.clear()
                self.translation_model_combo.addItems(models)
                if current_model in models:
                    self.translation_model_combo.setCurrentText(current_model)
            self.temp_edit.setText(str(self.config['ollama_temperature']))
            self.timeout_edit.setText(str(self.config['ollama_timeout']))
            self.stream_checkbox.setChecked(self.config['ollama_stream'])
            self.prompt_edit.setPlainText(self.config['ollama_prompt_template'])
            self.appid_edit.setText(self.config['baidu_appid'])
            self.key_edit.setText(self.config['baidu_secretKey'])
            self.always_on_top_checkbox.setChecked(self.config['always_on_top'])
            self.minimize_to_tray_checkbox.setChecked(self.config['minimize_to_tray'])
            self.enable_shortcuts_checkbox.setChecked(self.config['enable_shortcuts'])
            self.auto_update_checkbox.setChecked(self.config['auto_update'])
            auto_copy_index = self.config.get('auto_copy_index', -1)
            if auto_copy_index >= -1 and auto_copy_index <= 7:
                self.auto_copy_combo.setCurrentIndex(auto_copy_index + 1)
            self.toggle_always_on_top(self.config['always_on_top'])
            QMessageBox.information(self, '恢复默认', '已恢复默认设置')
            self.statusBar().showMessage('已恢复默认设置')

    def save_settings(self):
        self.config['default_mode'] = '大模型翻译' if self.model_radio.isChecked() else 'API翻译'
        self.config['ollama_server'] = self.server_edit.text().strip()
        if hasattr(self, 'translation_model_combo'):
            self.config['ollama_model'] = self.translation_model_combo.currentText().strip()
        else:
            self.config['ollama_model'] = self.model_combo.currentText().strip()
        self.config['ollama_temperature'] = float(self.temp_edit.text().strip() or '0.0')
        self.config['ollama_timeout'] = int(self.timeout_edit.text().strip() or '60')
        self.config['ollama_stream'] = self.stream_checkbox.isChecked()
        self.config['ollama_prompt_template'] = self.prompt_edit.toPlainText()
        self.config['baidu_appid'] = self.appid_edit.text().strip()
        self.config['baidu_secretKey'] = self.key_edit.text().strip()
        self.config['always_on_top'] = self.always_on_top_checkbox.isChecked()
        self.config['minimize_to_tray'] = self.minimize_to_tray_checkbox.isChecked()
        self.config['enable_shortcuts'] = self.enable_shortcuts_checkbox.isChecked()
        self.config['auto_update'] = self.auto_update_checkbox.isChecked()
        self.config['auto_copy_index'] = self.auto_copy_combo.currentIndex() - 1
        models = []
        for i in range(self.model_combo.count()):
            models.append(self.model_combo.itemText(i))
        self.config['ollama_models'] = models
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            QMessageBox.information(self, '设置保存', '设置已保存')
            self.statusBar().showMessage('设置已保存')
        except Exception as e:
            QMessageBox.critical(self, '保存失败', f'保存配置失败: {str(e)}')

    def get_default_config(self):
        return {'default_mode': '大模型翻译', 'ollama_server': '', 'ollama_model': '', 'ollama_temperature': 0.0, 'ollama_timeout': 60, 'ollama_stream': True, 'ollama_prompt_template': 'You are a professional software variable name assistant integrated into the program as part of an API. Your task is to accurately translate the provided Chinese variable name: `{translate_word}` into the corresponding English variable name. The translated variable name should be in lowercase with words separated by spaces. Ensure that the output contains only lowercase letters and spaces, with no other characters or symbols. Output only the translated result, without any additional content.', 'ollama_models': [''], 'baidu_appid': '', 'baidu_secretKey': '', 'always_on_top': False, 'enable_shortcuts': True, 'minimize_to_tray': True, 'auto_update': True, 'auto_copy_index': -1}

    def load_config(self):
        default_config = self.get_default_config()
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    default_config.update(config)
            return default_config
        except Exception as e:
            print(f'加载配置失败: {e}')
            return default_config

    def closeEvent(self, event):
        if self.config.get('minimize_to_tray', True) and self.tray_icon:
            self.hide()
            event.ignore()
        else:
            if self.translation_worker and self.translation_worker.isRunning():
                self.translation_worker.is_cancelled = True
                self.translation_worker.quit()
                self.translation_worker.wait()
            if self.model_refresh_worker and self.model_refresh_worker.isRunning():
                self.model_refresh_worker.quit()
                self.model_refresh_worker.wait()
            if self.update_check_worker and self.update_check_worker.isRunning():
                self.update_check_worker.quit()
                self.update_check_worker.wait()
            if self.update_download_worker and self.update_download_worker.isRunning():
                self.update_download_worker.is_cancelled = True
                self.update_download_worker.quit()
                self.update_download_worker.wait()
            if self.tray_icon:
                self.tray_icon.hide()
            event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainUI()
    saved_theme = window.config.get('theme')
    if saved_theme and saved_theme in QStyleFactory.keys():
        app.setStyle(QStyleFactory.create(saved_theme))
    window.show()
    sys.exit(app.exec())
if __name__ == '__main__':
    name = 'GrapeCoffee 智能变量名助手'
    version = '2.1.4'
    main()