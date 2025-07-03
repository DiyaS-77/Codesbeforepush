from PyQt6.QtWidgets import (QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QTextEdit,
                             QScrollArea, QWidget, QListWidget, QComboBox, QTreeWidget, QTreeWidgetItem, QGridLayout)
from PyQt6.QtCore import Qt, QFileSystemWatcher

from test_automation.UI import style_sheet as ss
from test_automation.UI.Backend_lib.Linux import hci_commands as hci

class TestControllerUI(QWidget):
    def __init__(self, controller, log, bluez_logger,back_callback):
        super().__init__()
        self.controller = controller
        self.log = log
        #elf.log_path=log_path
        self.back_callback=back_callback
        self.bluez_logger = bluez_logger
        self.scroll = None
        self.content_layout = None
        self.content_widget = None
        self.handle = None
        self.ocf = None
        self.ogf = None
        self.command_input_layout = None
        self.commands_list_tree_widget = None
        self.empty_list = None
        self.logs_layout = None
        self.dump_log_output = None
        self.file_watcher = None
        self.controller_ui()

    def controller_ui(self):

        main_layout = QGridLayout()
        main_layout.setColumnStretch(0, 1)
        main_layout.setColumnStretch(1, 1)
        main_layout.setColumnStretch(2, 1)

        vertical_layout = QGridLayout()

        self.commands_list_tree_widget = QTreeWidget()
        self.commands_list_tree_widget.setHeaderLabels(["HCI Commands"])
        self.commands_list_tree_widget.setStyleSheet(ss.cmd_list_widget_style_sheet)

        items = []
        for item in list(hci.hci_commands.keys()):
            _item = QTreeWidgetItem([item])
            for value in list(getattr(hci, item.lower().replace(' ', '_')).keys()):
                child = QTreeWidgetItem([value])
                _item.addChild(child)
            items.append(_item)

        self.commands_list_tree_widget.insertTopLevelItems(0, items)
        self.commands_list_tree_widget.clicked.connect(self.run_hci_cmd)

        vertical_layout.addWidget(self.commands_list_tree_widget, 0, 0)
        vertical_layout.setRowStretch(0, 1)
        vertical_layout.setRowStretch(1, 1)
        main_layout.addLayout(vertical_layout, 0, 0)

        self.command_input_layout = QVBoxLayout()
        self.empty_list = QListWidget()
        self.empty_list.setStyleSheet("background: transparent; border: 2px solid black;")
        self.command_input_layout.addWidget(self.empty_list)
        main_layout.addLayout(self.command_input_layout, 0, 1)

        self.logs_layout = QVBoxLayout()
        logs_label = QLabel("DUMP LOGS")
        logs_label.setStyleSheet("border: 2px solid black; color: black; font-size:18px; font-weight: bold;")
        logs_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.logs_layout.addWidget(logs_label)

        self.dump_log_output = QTextEdit()
        self.dump_log_output.setMaximumWidth(700)
        self.dump_log_output.setReadOnly(True)


        self.bluez_logger.start_dump_logs(interface=self.controller.interface, log_text_browser=self.dump_log_output)
        self.bluez_logger.logfile_fd.seek(0)
        content = self.bluez_logger.logfile_fd.read()
        self.bluez_logger.file_position = self.bluez_logger.logfile_fd.tell()
        #self.bluez_logger.file_position = 0
        self.dump_log_output.append(content)
        self.logs_layout.addWidget(self.dump_log_output)

        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.addPath(self.bluez_logger.hcidump_log_name)
        self.file_watcher.fileChanged.connect(self.update_log)
        '''
        self.dump_log_output.setStyleSheet("""
                QTextEdit {
                background: transparent;
                color: black;
                border: 2px solid black;
                }
              """  )
        '''
        self.dump_log_output.setStyleSheet("background: transparent;color: black;border: 2px solid black;")

        main_layout.addLayout(self.logs_layout, 0, 2)

        back_button = QPushButton("Back")
        back_button.setStyleSheet("font-size: 16px; padding: 6px;")
        back_button.clicked.connect(self.back_callback)

        button_layout = QHBoxLayout()
        button_layout.addWidget(back_button)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        main_layout.addLayout(button_layout, 1, 0)
        #main_layout.addLayout(button_layout,11,0,1,1)
        self.setLayout(main_layout)

    def update_log(self):
        self.bluez_logger.logfile_fd.seek(self.bluez_logger.file_position)
        #self.bluez_logger.logfile_fd.seek(0)

        content = self.bluez_logger.logfile_fd.read()
        self.bluez_logger.file_position = self.bluez_logger.logfile_fd.tell()
        #self.bluez_logger.file_position = 0
        self.dump_log_output.append(content)

    def run_hci_cmd(self, text_selected):
        """ Updates the ocf and ogf selected from hci commands list. """
        if text_selected.parent().data():
            self.ocf = text_selected.parent().data()
            self.ogf = text_selected.data()
        else:
            self.ocf = text_selected.data()
            return
        if not self.scroll:
            self.scroll = QScrollArea()
            self.scroll.setWidgetResizable(True)
        if self.content_layout:
            if self.content_layout.count() > 0:
                while self.content_layout.count():
                    item = self.content_layout.itemAt(0).widget()
                    self.content_layout.removeWidget(item)
                    if item is not None:
                        item.deleteLater()
                self.content_widget.hide()
        self.empty_list.hide()

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        parameters = getattr(hci, self.ocf.lower().replace(' ', '_'))[self.ogf][1]
        index = 0
        for parameter in parameters:
            key = list(parameter.keys())[0]
            default_val = list(parameter.values())[0]
            label = QLabel(key)
            label.setStyleSheet("color: black; font-size:12px;")
            label.setMaximumHeight(30)
            label.setText(key)
            if 'Connection_Handle' in key:
                setattr(self, key, QComboBox())
                combo_box_widget = getattr(self, key)
                combo_box_widget.setPlaceholderText("Connection Handles")
                combo_box_widget.addItems(list(self.controller.get_connection_handles().keys()))
                combo_box_widget.currentTextChanged.connect(self.current_text_changed)
                combo_box_widget.setMaximumHeight(30)
            else:
                setattr(self, key, QTextEdit(default_val))
                getattr(self, key).setMaximumHeight(30)
                if hasattr(self, f"{self.ogf}_values"):
                    if getattr(self, f"{self.ogf}_values"):
                        getattr(self, key).setText(getattr(self, f"{self.ogf}_values")[index])
                        index += 1
            self.content_layout.addWidget(label)
            self.content_layout.addWidget(getattr(self, key))
            self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        if len(parameters) < 1:
            text_edit_widget = QTextEdit("No parameters")
            text_edit_widget.setMaximumHeight(30)
            text_edit_widget.setReadOnly(True)
            self.content_layout.addWidget(text_edit_widget)
            self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        execute_btn = QPushButton("Execute")
        execute_btn.setStyleSheet(
            "font-size: 18px; "
            "color: white; "
            "background: transparent; "
            "padding: 10px;")
        execute_btn.clicked.connect(self.execute_hci_cmd)
        self.content_layout.addWidget(execute_btn)
        if len(parameters) >= 1:
            reset_btn = QPushButton("Reset to default")
            reset_btn.setStyleSheet(
                "font-size: 18px; "
                "color: white; "
                "background: transparent; "
                "padding: 10px;")
            reset_btn.clicked.connect(self.reset_default_params)
            self.content_layout.addWidget(reset_btn)
        self.scroll.setWidget(self.content_widget)
        self.command_input_layout.addWidget(self.scroll)

    def current_text_changed(self, text):
        """ Stores the handle selected for executing the hci command. """
        self.handle = text
    def execute_hci_cmd(self):
        parameters = []
        self.controller.get_connection_handles()
        for parameter in getattr(hci, self.ocf.lower().replace(' ', '_'))[self.ogf][1]:
            _param = list(parameter.keys())[0]
            if isinstance(getattr(self, _param), QComboBox):
                parameters.append(self.controller.handles[self.handle])
                self.handle = None
                continue
            if getattr(self, _param).toPlainText() == 'None':
                break
            parameters.append(getattr(self, _param).toPlainText())
        setattr(self, f"{self.ogf}_values", parameters)
        self.log.debug(f"{self.ocf=} {self.ogf=} {parameters=}")
        self.controller.run_hci_cmd(self.ocf, self.ogf, parameters)

    def reset_default_params(self):
        parameters = getattr(hci, self.ocf.lower().replace(' ', '_'))[self.ogf][1]
        for parameter in parameters:
            key = list(parameter.keys())[0]
            default_val = list(parameter.values())[0]
            getattr(self, key).setText(default_val)

