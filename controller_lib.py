import re
import time

from test_automation.UI.Backend_lib.Linux import hci_commands as hci
from test_automation.UI.utils import run
from test_automation.UI.utils import check_command_running
from test_automation.UI.utils import kill_process
# from utils import run
# from utils import check_command_running
# from utils import kill_process


class Controller:
    def __init__(self,log):
        self.pulseaudio_log_name = None
        self.pulseaudio_file_position = None
        self.pulseaudio_logfile_fd = None
        self.bluetoothd_file_position = None
        self.bluetoothd_logfile_fd = None
        self.bluetoothd_log_name = None
        self.bd_address = None
        self.controllers_list = {}
        self.handles = None
        self.log = log
        self.interface = None
        #self.logfile_path = '/tmp/hcidump_logs/'
        self.logfile_fd = None
        self.file_position = None
        self.hcidump_log_name = None
        self.hci_dump_started=False
        self.log_path= None


    def get_controllers_connected(self):
        """Returns the controllers list connected to host.

        Returns:
            returns list of controllers connected.
        """
        result = run(self.log, 'hciconfig -a | grep -B 2 \"BD A\"')
        result = result.stdout.split("--")
        if result[0]:
            for res in result:
                res = res.strip("\n").replace('\n', '')
                if match := re.match('(.*):	Type:.+BD Address: (.*)  ACL(.*)', res):
                    self.controllers_list[match[2]] = match[1]
        self.log.info("Controllers {} found on host".format(self.controllers_list))
        return self.controllers_list

    def get_controller_interface_details(self):
        """ Returns the controllers interface and bus details. """
        self.interface = self.controllers_list[self.bd_address]
        result = run(self.log,f"hciconfig -a {self.interface} | grep Bus")
        return f"Interface: {self.interface} \t Bus: {result.stdout.split('Bus:')[1].strip()}"

    def get_controller_details(self):
        """ Returns the details of the controller selected. """
        run(self.log, f"hciconfig -a {self.interface} up")
        #print(f'INterface selected--------------{self.interface}')
        result = run(self.log,f"hciconfig -a {self.interface}")
        details = ""
        result = result.stdout.split('\n')
        for line in result:
            line = line.strip()
            if match := re.match('BD Address: (.*)  ACL(.*)', line):
                details = '\n'.join([details, f"BD_ADDR: {match[1]}"])
            if match := re.match('Link policy: (.*)', line):
                details = '\n'.join([details, f"Link policy: {match[1]}"])
            if match := re.match('Link mode: (.*)', line):
                details = '\n'.join([details, f"Link mode: {match[1]}"])
            if match := re.match('Name: (.*)', line):
                details = '\n'.join([details, f"Name: {match[1]}"])
            if match := re.match('Class: (.*)', line):
                details = '\n'.join([details, f"Class: {match[1]}"])
            if match := re.match('HCI Version: (.*)  .+', line):
                details = '\n'.join([details, f"HCI Version: {match[1]}"])
            if match := re.match('LMP Version: (.*)  .+', line):
                details = '\n'.join([details, f"LMP Version: {match[1]}"])
            if match := re.match('Manufacturer: (.*)', line):
                details = '\n'.join([details, f"Manufacturer: {match[1]}"])
        return details

    def convert_mac_little_endian(self, address):
        """ Converts BD_Address to little endian.
;
        Args:
            address - Remote device address

        Returns:
            converted BD_Address.
        """
        addr = address.split(':')
        addr.reverse()
        return ' '.join(addr)

    def convert_to_little_endian(self, num, num_of_octets):
        """ Prepare the formatted hci command packet

        Args:
            num - Number to be converted.
            num_of_octets - Total octets in num.

        Returns:
            converted number.
        """
        data = None
        if isinstance(num, str) and '0x' in num:
            data = num.replace("0x", "")
        elif isinstance(num, str) and '0x' not in num:
            data = int(num)
            data = str(hex(data)).replace("0x", "")
        elif isinstance(num, int):
            data = str(hex(num)).replace("0x", "")
        while True:
            if len(data) == (num_of_octets * 2):
                break
            data = "0" + data
        out = [(data[i:i + 2]) for i in range(0, len(data), 2)]
        out.reverse()
        return ' '.join(out)

    def run_hci_cmd(self, ogf, command, parameters=None):
        """ Executes the hci command and returns the result

        Args:
            ogf: Opcode Group Field value
            command: hci command to be executed
            parameters: parameters for the command to be executed

        Returns:
            returns the result of the command executed.
        """

        _ogf = ogf.lower().replace(' ', '_')
        _ocf_info = getattr(hci, _ogf)[command]
        hci_command = 'hcitool -i {} cmd {} {}'.format(self.interface, hci.hci_commands[ogf], _ocf_info[0])
        for index in range(len(parameters)):
            param_len = list(_ocf_info[1][index].values())[1] if len(
                _ocf_info[1][index].values()) > 1 else None
            if param_len:
                parameter = self.convert_to_little_endian(parameters[index],
                                                          param_len)
            else:
                parameter = parameters[index].replace('0x', '')
            hci_command = ' '.join([hci_command, parameter])
        self.log.info(f"Executing command: {hci_command}")
        return run(self.log,hci_command)

    def get_connection_handles(self):
        """ Returns the connection handles dictionary. """
        hcitool_con_cmd = f"hcitool -i {self.interface} con"
        self.handles = {}
        result = run(self.log, hcitool_con_cmd)
        results = result.stdout.split('\n')
        for line in results:
            if 'handle' in line:
                handle = (line.strip().split('state')[0]).replace('< ', '').strip()
                self.handles[handle] = hex(int(handle.split(' ')[-1]))
        return self.handles
