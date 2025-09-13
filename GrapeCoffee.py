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
import httplib2
import requests
import win32clipboard as w
import win32con
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QGroupBox, QRadioButton, QButtonGroup, QMessageBox, QProgressBar, QTabWidget, QScrollArea, QSizePolicy, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut
import base64
from PySide6.QtGui import QPixmap, QIcon
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
        _response, content = cache.request(myurl)
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

def get_ollama_models(server_url):
    try:
        response = requests.get(f'{server_url}/api/tags', timeout=10)
        response.raise_for_status()
        models_data = response.json()
        model_names = [model['name'] for model in models_data.get('models', [])]
        return model_names
    except Exception as e:
        print(f'获取模型列表失败: {e}')
        return []

class OllamaAigc(object):

    def __init__(self, _send_chat_url, _model, _stream, _temperature, _prompt_template):
        self.send_chat_url = _send_chat_url
        self.model = _model
        self.stream = _stream
        self.temperature = _temperature
        self.prompt_template = _prompt_template

    def send_chat_request(self, translate_word):
        prompt = self.prompt_template.format(translate_word=translate_word)
        messages = [{'role': 'user', 'content': prompt}]
        payload = {'model': self.model, 'messages': messages, 'stream': self.stream, 'temperature': self.temperature}
        try:
            _response = requests.post(self.send_chat_url, json=payload, timeout=60)
            _response.raise_for_status()
            chat_response = _response.json()
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
                TranslationResults, InputInformation = translation_api(self.input_text, InputLanguage, TranslationLanguage, appid, secretKey)
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
                send_chat_url = f'{ollama_server}/api/chat'
                response = OllamaAigc(send_chat_url, model, stream, temperature, prompt_template).send_chat_request(self.input_text)
                if response is None:
                    self.translation_finished.emit('', 'Ollama接口调用失败，请检查服务器地址和模型是否正确', '')
                    return
                result = response['message']['content'].replace('_', ' ')
                raw_response = response['message']['content']
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

class VariableNameTranslatorUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.translation_worker = None
        self.model_refresh_worker = None
        self.shortcuts = []
        self.naming_results = []
        self.config = self.load_config()
        self.init_ui()
        QTimer.singleShot(100, self.auto_refresh_models)
        self.init_shortcuts()

    def init_ui(self):
        self.setWindowTitle(f'{name}')
        self.setGeometry(100, 100, 650, 800)
        self.setMinimumSize(600, 800)
        self.set_window_icon()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        title_label = QLabel(f'{name}')
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        translation_tab = self.create_translation_tab()
        tab_widget.addTab(translation_tab, '变量名翻译')
        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, '设置')
        self.statusBar().showMessage('就绪')
        version_label = QLabel(f'<a href="https://github.com/JAINKRE/GrapeCoffee" style="text-decoration: none; color: #7f8c8d;">© 2018-{_year} {name} v{version}</a>')
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet('font-size:12px')
        version_label.setOpenExternalLinks(True)
        main_layout.addWidget(version_label)
        if self.config.get('always_on_top', False):
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()

    def set_window_icon(self):
        icon_base64 = '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'
        try:
            image_data = base64.b64decode(icon_base64)
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            icon = QIcon(pixmap)
            self.setWindowIcon(icon)
        except Exception as e:
            print(f'设置窗口图标失败: {e}')

    def create_translation_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        input_group = QGroupBox('输入变量名')
        input_layout = QVBoxLayout(input_group)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText('请输入中文变量名，如：用户信息')
        self.input_edit.returnPressed.connect(self.start_translation)
        input_layout.addWidget(self.input_edit)
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
        self.current_model_label = QLabel()
        mode_layout.addWidget(self.current_model_label)
        self.model_radio.toggled.connect(self.update_current_model_label)
        prefix_group = QGroupBox('变量前缀')
        prefix_layout = QHBoxLayout(prefix_group)
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText('设置变量名前缀（可选）')
        prefix_layout.addWidget(self.prefix_edit)
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
        layout.addWidget(prefix_group)
        layout.addLayout(button_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(result_group)
        layout.setStretchFactor(result_group, 1)
        layout.addStretch()
        return tab

    def create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
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
        self.model_combo.setEditable(True)
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
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel('温度参数:'))
        self.temp_edit = QLineEdit(str(self.config.get('ollama_temperature', 0.0)))
        self.temp_edit.setFixedWidth(100)
        temp_layout.addWidget(self.temp_edit)
        temp_layout.addStretch()
        ollama_layout.addLayout(temp_layout)
        prompt_layout = QVBoxLayout()
        prompt_label = QLabel('提示词模板:')
        prompt_layout.addWidget(prompt_label)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(150)
        self.prompt_edit.setStyleSheet('\n            QTextEdit {\n                border: 1px solid #bdc3c7;\n                border-radius: 4px;\n                font-family: Consolas;\n            }\n        ')
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
        window_group = QGroupBox('窗口设置')
        window_layout = QVBoxLayout(window_group)
        self.always_on_top_checkbox = QCheckBox('窗口置顶')
        self.always_on_top_checkbox.setChecked(self.config.get('always_on_top', False))
        self.always_on_top_checkbox.toggled.connect(self.toggle_always_on_top)
        window_layout.addWidget(self.always_on_top_checkbox)
        shortcut_group = QGroupBox('快捷键设置')
        shortcut_layout = QVBoxLayout(shortcut_group)
        self.enable_shortcuts_checkbox = QCheckBox('启用快捷键 (Ctrl+Alt+数字键)')
        self.enable_shortcuts_checkbox.setChecked(self.config.get('enable_shortcuts', True))
        shortcut_layout.addWidget(self.enable_shortcuts_checkbox)
        shortcut_note = QLabel('使用 Ctrl+Alt+数字键 复制对应序号的变量名:')
        shortcut_layout.addWidget(shortcut_note)
        self.shortcut_table = QTableWidget(8, 2)
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
        layout.addWidget(window_group)
        layout.addWidget(shortcut_group)
        layout.addStretch()
        layout.addLayout(button_layout)
        self.update_current_model_label()
        self.model_combo.currentTextChanged.connect(self.update_current_model_label)
        return tab

    def update_current_model_label(self):
        if hasattr(self, 'model_combo') and self.model_radio.isChecked():
            current_model = self.model_combo.currentText()
            if current_model:
                self.current_model_label.setText(f'当前模型: {current_model}')
            else:
                self.current_model_label.setText('当前模型: 未选择')
        elif hasattr(self, 'model_combo'):
            self.current_model_label.setText('')

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
            if current_text in model_names:
                self.model_combo.setCurrentText(current_text)
            elif model_names:
                self.model_combo.setCurrentIndex(0)
            self.update_current_model_label()
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
            QMessageBox.critical(self, '刷新失败', f'获取模型列表时出错: {error}')
            self.statusBar().showMessage('获取模型列表失败')
        else:
            current_text = self.model_combo.currentText()
            self.model_combo.clear()
            self.model_combo.addItems(model_names)
            if current_text in model_names:
                self.model_combo.setCurrentText(current_text)
            elif model_names:
                self.model_combo.setCurrentIndex(0)
            self.update_current_model_label()
            QMessageBox.information(self, '刷新成功', f'成功获取到 {len(model_names)} 个模型')
            self.statusBar().showMessage(f'模型列表更新成功，共 {len(model_names)} 个模型')

    def start_translation(self):
        input_text = self.input_edit.text().strip()
        if not input_text:
            QMessageBox.warning(self, '输入错误', '请输入变量名')
            return
        mode = 'API翻译' if self.api_radio.isChecked() else '大模型翻译'
        if mode == '大模型翻译':
            server_url = self.server_edit.text().strip()
            model_name = self.model_combo.currentText().strip()
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
        ollama_config = {'server': self.server_edit.text().strip(), 'model': self.model_combo.currentText().strip(), 'temperature': float(self.temp_edit.text().strip() or '0.0'), 'stream': False, 'prompt_template': self.prompt_edit.toPlainText()}
        api_config = {'appid': self.appid_edit.text().strip(), 'secretKey': self.key_edit.text().strip()}
        self.translation_worker = TranslationWorker(mode, input_text, ollama_config, api_config)
        self.translation_worker.translation_finished.connect(self.on_translation_finished)
        self.translation_worker.progress_updated.connect(self.progress_bar.setValue)
        self.translation_worker.start()

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
        if raw_response:
            self.raw_output_text.setPlainText(raw_response)
        else:
            self.raw_output_text.setPlainText('此功能仅在大模型翻译模式下可用')
        cleaned_result = re.sub('\\<think\\>.*?\\<\\/think\\>', '', result, flags=re.DOTALL)
        words = [word.lower() for word in cleaned_result.split() if word]
        self.display_results(words)
        self.statusBar().showMessage('翻译完成')

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
        converter = Convert()
        naming_rules = [('私有成员', converter.case_01), ('特殊方法', converter.case_02), ('驼峰命名法', converter.case_03), ('帕斯卡命名法', converter.case_04), ('蛇形命名法', converter.case_05), ('匈牙利命名法', converter.case_06), ('烤肉串命名法', converter.case_07), ('常量命名法', converter.case_08)]
        for i, (title, func) in enumerate(naming_rules):
            result = converter.convert_warr(words, func)
            if prefix:
                if title in ['私有成员', '特殊方法']:
                    result = prefix.lower() + result
                else:
                    result = prefix.lower() + '_' + result
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
            self.temp_edit.setText(str(self.config['ollama_temperature']))
            self.prompt_edit.setPlainText(self.config['ollama_prompt_template'])
            self.appid_edit.setText(self.config['baidu_appid'])
            self.key_edit.setText(self.config['baidu_secretKey'])
            self.always_on_top_checkbox.setChecked(self.config['always_on_top'])
            self.enable_shortcuts_checkbox.setChecked(self.config['enable_shortcuts'])
            self.toggle_always_on_top(self.config['always_on_top'])
            self.update_current_model_label()
            QMessageBox.information(self, '恢复默认', '已恢复默认设置')
            self.statusBar().showMessage('已恢复默认设置')

    def save_settings(self):
        self.config['default_mode'] = '大模型翻译' if self.model_radio.isChecked() else 'API翻译'
        self.config['ollama_server'] = self.server_edit.text().strip()
        self.config['ollama_model'] = self.model_combo.currentText().strip()
        self.config['ollama_temperature'] = float(self.temp_edit.text().strip() or '0.0')
        self.config['ollama_prompt_template'] = self.prompt_edit.toPlainText()
        self.config['baidu_appid'] = self.appid_edit.text().strip()
        self.config['baidu_secretKey'] = self.key_edit.text().strip()
        self.config['always_on_top'] = self.always_on_top_checkbox.isChecked()
        self.config['enable_shortcuts'] = self.enable_shortcuts_checkbox.isChecked()
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
        return {'default_mode': '大模型翻译', 'ollama_server': '', 'ollama_model': '', 'ollama_temperature': 0.0, 'ollama_prompt_template': 'You are a professional software variable name assistant integrated into the program as part of an API. Your task is to accurately translate the provided Chinese variable name: `{translate_word}` into the corresponding English variable name. The translated variable name should be in lowercase with words separated by spaces. Ensure that the output contains only lowercase letters and spaces, with no other characters or symbols. Output only the translated result, without any additional content.', 'ollama_models': [''], 'baidu_appid': '', 'baidu_secretKey': '', 'always_on_top': False, 'enable_shortcuts': True}

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
        if self.translation_worker and self.translation_worker.isRunning():
            self.translation_worker.is_cancelled = True
            self.translation_worker.quit()
            self.translation_worker.wait()
        if self.model_refresh_worker and self.model_refresh_worker.isRunning():
            self.model_refresh_worker.quit()
            self.model_refresh_worker.wait()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = VariableNameTranslatorUI()
    window.show()
    sys.exit(app.exec())
if __name__ == '__main__':
    name = 'GrapeCoffee 智能变量名助手'
    version = '2.1.2'
    main()