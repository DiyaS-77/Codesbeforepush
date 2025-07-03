
from PyQt6.QtCore import QDateTime, QTimer
from PyQt6.QtGui import QTextCursor
from pyatspi import interface

#from test_automation.UI.utils import check_command_running
#from test_automation.UI.utils import kill_process
from test_automation.UI.utils import run
from test_automation.UI.logger import Logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from test_automation.UI.UI_lib.controller_lib import Controller
from PyQt6.QtCore import QThread
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTextEdit

import logging
import os
import re
import subprocess
import time


class LogWatcher(FileSystemEventHandler):
    def __init__(self, log_file, text_browser):
        self.log_file = log_file
        self.text_browser = text_browser
        self.last_position = 0

    def on_modified(self, event):
        """Constantly modifying the logs using the LogWatcher class"""
        if event.src_path == self.log_file:
            with open(self.log_file, 'r') as f:
                f.seek(self.last_position)
                content = f.read()
                self.text_browser.append(content)
                self.last_position = f.tell()


class HcidumpLogReader(QThread):
    log_updated = pyqtSignal(str)

    def __init__(self, logfile_path, parent=None):
        super().__init__(parent)
        self.logfile_path = logfile_path
        self._running = True
        self.last_position = 0


    def run(self):
        while self._running:
            with open(self.logfile_path, 'r') as f:
            #with open(self.logfile_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(self.last_position)
                new_logs = f.read()
                if new_logs:
                    self.log_updated.emit(new_logs)
                self.last_position = f.tell()
            time.sleep(1)

    def stop(self):
        self._running = False



# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
def run_command(log_path, command, log_file=None):
    """Function for the run command"""
    output = subprocess.run(command, shell=True, capture_output=True, text=True)
    logging.info(f"Command: {command}\nOutput: {output.stdout}")
    return output

class BluezLogger:
    def __init__(self, log_path):
        super().__init__()

        self.bluetoothd_log_reader = None
        self.bluetoothd_process = None
        self.pulseaudio_log_reader = None
        self.pulseaudio_process = None
        self.interface = None
        self.hci_log_reader = None
        self.bluetoothd_started = False
        self.pulseaudio_started = False
        self.pulseaudio_log_name = None
        self.pulseaudio_file_position = None
        self.pulseaudio_logfile_fd = None
        self.bluetoothd_file_position = None
        self.bluetoothd_logfile_fd = None
        self.bluetoothd_log_name = None
        self.bd_address = None
        self.controllers_list = {}
        self.handles = None
        self.log = Logger("UI")
        self.hcidump_process = None
        self.controller=Controller(self.log)
        self.log_path = log_path
        self.logfile_fd = None
        self.file_position = None
        self.hcidump_log_name = None
        self.bluetoothd_scrollbar_dragged_down = False
        self.pulseaudio_scrollbar_dragged_down = False
        self.hcidump_scrollbar_dragged_down = False


    def start_dbus_service(self):
        """Starts the D-Bus service."""
        print("Starting D-Bus service...")
        dbus_command = "/usr/local/bluez/dbus-1.12.20/bin/dbus-daemon --system --nopidfile"
        self.dbus_process = subprocess.Popen(dbus_command, shell=True)
        time.sleep(1)
        print("D-Bus service started successfully.")

    def start_bluetoothd_logs(self, log_text_browser=None):
        self.bluetoothd_log_name = os.path.join(self.log_path, "bluetoothd.log")

        subprocess.run("pkill -f bluetoothd", shell=True)
        time.sleep(1)

        bluetoothd_command = '/usr/local/bluez/bluez-tools/libexec/bluetooth/bluetoothd -nd --compat'
        print(f"[INFO] Starting bluetoothd logs...{bluetoothd_command}")
        self.bluetoothd_process = subprocess.Popen(
            bluetoothd_command.split(),
            stdout=open(self.bluetoothd_log_name, 'a+'),
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )
        time.sleep(1)

        self.bluetoothd_logfile_fd = open(self.bluetoothd_log_name, 'r')
        self.bluetoothd_file_position = self.bluetoothd_logfile_fd.tell()

        if log_text_browser is not None:
            self.bluetoothd_log_reader = HcidumpLogReader(self.bluetoothd_log_name)
            self.bluetoothd_log_reader.log_updated.connect(log_text_browser.append)
            self.bluetoothd_log_reader.start()

        print(f"[INFO] Bluetoothd logs started: {self.bluetoothd_log_name}")
        return True

    def start_pulseaudio_logs(self, log_text_browser=None):
        self.pulseaudio_log_name = os.path.join(self.log_path, "pulseaudio.log")

        # PREVENT OLD PROCESSES
        subprocess.run("pkill -f pulseaudio", shell=True)
        time.sleep(1)

        pulseaudio_command = '/usr/local/bluez/pulseaudio-13.0_for_bluez-5.65/bin/pulseaudio -vvv'
        print(f"[INFO] Starting pulseaudio logs...{pulseaudio_command}")
        self.pulseaudio_process = subprocess.Popen(
            pulseaudio_command.split(),
            stdout=open(self.pulseaudio_log_name, 'a+'),
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )
        time.sleep(1)

        self.pulseaudio_logfile_fd = open(self.pulseaudio_log_name, 'r')
        self.pulseaudio_file_position = self.pulseaudio_logfile_fd.tell()

        if log_text_browser is not None:
            self.pulseaudio_log_reader = HcidumpLogReader(self.pulseaudio_log_name)
            self.pulseaudio_log_reader.log_updated.connect(log_text_browser.append)
            self.pulseaudio_log_reader.start()

        print(f"[INFO] Pulseaudio logs started: {self.pulseaudio_log_name}")
        return True

    def stop_bluetoothd_logs(self):
        """Stop bluetoothd log reader and process."""
        print("[INFO] Stopping bluetoothd logs...")

        if hasattr(self, 'bluetoothd_log_reader') and self.bluetoothd_log_reader:
            self.bluetoothd_log_reader.stop()
            self.bluetoothd_log_reader = None

        if self.bluetoothd_logfile_fd:
            self.bluetoothd_logfile_fd.close()
            self.bluetoothd_logfile_fd = None

        if hasattr(self, 'bluetoothd_process') and self.bluetoothd_process:
            try:
                self.bluetoothd_process.terminate()
                self.bluetoothd_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.bluetoothd_process.kill()
                self.bluetoothd_process.wait()
            self.bluetoothd_process = None



    def stop_pulseaudio_logs(self):
        """Stop pulseaudio log reader and process."""
        print("[INFO] Stopping pulseaudio logs...")

        if hasattr(self, 'pulseaudio_log_reader') and self.pulseaudio_log_reader:
            self.pulseaudio_log_reader.stop()
            self.pulseaudio_log_reader = None

        if self.pulseaudio_logfile_fd:
            self.pulseaudio_logfile_fd.close()
            self.pulseaudio_logfile_fd = None

        if hasattr(self, 'pulseaudio_process') and self.pulseaudio_process:
            try:
                self.pulseaudio_process.terminate()
                self.pulseaudio_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.pulseaudio_process.kill()
                self.pulseaudio_process.wait()
            self.pulseaudio_process = None


    def get_controller_details(self,interface=None):
        """ Fetching all the relevant controller details """
        self.interface = interface
        details = {}
        run_command(self.log_path, f'hciconfig -a {self.interface} up')
        result = run_command(self.log_path, f'hciconfig -a {self.interface}')
        for line in result.stdout.split('\n'):
            line = line.strip()
            if match := re.match('BD Address: (.*) ACL(.*)', line):
                details['BD_ADDR'] = match[1]
            elif match := re.match('Link policy: (.*)', line):
                details['Link policy'] = match[1]
            elif match := re.match('Link mode: (.*)', line):
                details['Link mode'] = match[1]
            elif match := re.match('Name: (.*)', line):
                details['Name'] = match[1]
            elif match := re.match('Class: (.*)', line):
                details['Class'] = match[1]
            elif match := re.match('HCI Version: (.*) .+', line):
                details['HCI Version'] = match[1]
            elif match := re.match('LMP Version: (.*) .+', line):
                details['LMP Version'] = match[1]
            elif match := re.match('Manufacturer: (.*)', line):
                details['Manufacturer'] = match[1]
        self.name = details.get('Name')
        self.bd_address = details.get('BD_ADDR')
        self.link_policy = details.get('Link policy')
        self.lmp_version = details.get('LMP Version')
        self.link_mode = details.get('Link mode')
        self.hci_version = details.get('HCI Version')
        self.manufacturer = details.get('Manufacturer')
        return details

    def stop_pulseaudio_logs(self):
        """Stops the pulseaudio logs."""
        print("Pulse audio logs has been stopped")
        if self.pulseaudio_logfile_fd:
            self.pulseaudio_logfile_fd.close()
            self.pulseaudio_logfile_fd = None
        pulseaudio_process = subprocess.Popen(['pgrep', 'pulseaudio'], stdout=subprocess.PIPE)
        pulseaudio_pid = pulseaudio_process.communicate()[0].decode('utf-8').strip()
        if pulseaudio_pid:
            subprocess.run(['kill', pulseaudio_pid])

    def stop_bluetoothd_logs(self):
        """Stops the bluetoothd logs."""
        print("Bluetoothd logs has been stopped")
        if self.bluetoothd_logfile_fd:
            self.bluetoothd_logfile_fd.close()
            self.bluetoothd_logfile_fd = None
        bluetoothd_process = subprocess.Popen(['pgrep', 'bluetoothd'], stdout=subprocess.PIPE)
        bluetoothd_pid = bluetoothd_process.communicate()[0].decode('utf-8').strip()
        if bluetoothd_pid:
            subprocess.run(['kill', bluetoothd_pid])

    def start_dump_logs(self, interface, log_text_browser=None):
        """Start hcidump logs for given interface and optionally stream to QTextBrowser"""
        try:
            # Interface must be passed explicitly
            if not interface:
                print("[ERROR] Interface is not provided for hcidump")
                return False

            #self.interface = interface
            print(f'interface used for dump {interface}')
            # Bring interface UP
            bring_up_cmd = f"hciconfig {interface} up"
            subprocess.run(bring_up_cmd.split(), capture_output=True)
            time.sleep(1)

            # Define log file path per session
            self.hcidump_log_name = os.path.join(self.log_path, f"{interface}_hcidump.log")

            # Start the hcidump subprocess
            hcidump_command = f"/usr/local/bluez/bluez-tools/bin/hcidump -i {interface} -Xt"
            #hcidump_command = '/usr/local/bluez/bluez-tools/bin/hcidump -i {} -Xt'.format(self.interface)
            print(f"[INFO] Starting hcidump: {hcidump_command}")

            self.hcidump_process = subprocess.Popen(
                hcidump_command.split(),
                stdout=open(self.hcidump_log_name, 'a+'),
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )

            time.sleep(1)

            self.logfile_fd = open(self.hcidump_log_name, 'r')
            self.file_position = self.logfile_fd.tell()
            #self.file_position=0
            #self.file_position=0
            if log_text_browser is not None:
                self.hci_log_reader = HcidumpLogReader(self.hcidump_log_name)
                self.hci_log_reader.log_updated.connect(log_text_browser.append)
                self.hci_log_reader.start()

            print(f"[INFO] hcidump process started: {self.hcidump_log_name}")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to start hcidump: {e}")
            return False

    def stop_dump_logs(self):
        """Stops the hcidump logs."""
        print("[INFO] Stopping HCI dump logs")

        if hasattr(self, 'hci_log_reader') and self.hci_log_reader:
            self.hci_log_reader.stop()
            self.hci_log_reader = None

        if self.logfile_fd:
            self.logfile_fd.close()
            self.logfile_fd = None

        if hasattr(self, 'hcidump_process') and self.hcidump_process:
            try:
                self.hcidump_process.terminate()
                self.hcidump_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.hcidump_process.kill()
                self.hcidump_process.wait()
            self.hcidump_process = None

        if self.interface:
            try:
                result = subprocess.run(['pgrep', '-f', f'hcidump.*{self.interface}'], capture_output=True, text=True)
                if result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        subprocess.run(['kill', '-TERM', pid])
                    time.sleep(1)
                    for pid in pids:
                        subprocess.run(['kill', '-KILL', pid])
            except Exception as e:
                print(f"[ERROR] Error killing hcidump: {e}")

        print("[INFO] HCI dump logs stopped successfully")



