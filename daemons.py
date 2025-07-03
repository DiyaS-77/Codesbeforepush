

import dbus
import dbus.service
import dbus.mainloop.glib
import os
import subprocess
import time
from gi.repository import GObject
import mimetypes
from dbus.mainloop.glib import DBusGMainLoop


dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

class BluezServices:
    def __init__(self,interface=None):
        self.interface = interface
        self.bus = dbus.SystemBus()
        self.object_manager_proxy=self.bus.get_object('org.bluez','/')
        self.object_manager=dbus.Interface(self.object_manager_proxy,'org.freedesktop.DBus.ObjectManager')
        self.adapter_path = f'/org/bluez/{self.interface}'
        self.adapter_proxy = self.bus.get_object('org.bluez',self.adapter_path)
        self.adapter = dbus.Interface(self.adapter_proxy, 'org.bluez.Adapter1')
        self.stream_process = None
        self.device_path = None
        self.device_address = None
        self.device_sink = None
        self.devices = {}
        self.last_session_path = None
        self.opp_process = None

    def start_discovery(self):
        """Function to start discovery"""
        self.adapter.StartDiscovery()

    def stop_discovery(self):
        """Function to stop discovery"""
        self.adapter.StopDiscovery()

    def inquiry(self,timeout):
        """Function for inquiry with inquiry timeout being mentioned"""
        self.start_discovery()
        time.sleep(timeout)
        self.stop_discovery()
        devices = []
        bus = dbus.SystemBus()
        om = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = om.GetManagedObjects()
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                devices.append(path)
        for device_path in devices:
            device = dbus.Interface(bus.get_object("org.bluez", device_path), dbus_interface="org.bluez.Device1")
            device_props = dbus.Interface(bus.get_object("org.bluez", device_path),dbus_interface="org.freedesktop.DBus.Properties")
            device_address = device_props.Get("org.bluez.Device1", "Address")
            print("Device Address")
            print(device_address)
            print("Device Name")
            device_name = device_props.Get("org.bluez.Device1", "Alias")
            print(device_name)

    def pair(self, address):
        """Function for pairing of the device"""

        device_path = self.find_device_path(address)
        if device_path:
            try:
                device = dbus.Interface(
                    self.bus.get_object("org.bluez", device_path),
                    dbus_interface="org.bluez.Device1"
                )
                print(f"Initiating pairing with {device_path}")
                device.Pair()

                # Wait up to 10 seconds for the user to confirm and BlueZ to mark as paired
                props = dbus.Interface(
                    self.bus.get_object("org.bluez", device_path),
                    "org.freedesktop.DBus.Properties"
                )

                import time
                for _ in range(20):  # 20 * 0.5s = 10 seconds max
                    paired = props.Get("org.bluez.Device1", "Paired")
                    if paired:
                        print("Pairing is successful")
                        return True
                    time.sleep(20)

                print("Pairing attempted but not confirmed")
                return False

            except dbus.exceptions.DBusException as e:
                print(f"Pairing failed: {e.get_dbus_message()}")
                return False
            except Exception as e:
                print(f"Unexpected error during pairing: {e}")
                return False
        else:
            print("Device path not found for pairing")
            return False


    def br_edr_connect(self, address):
        """Function for BR/EDR connection"""
        device_path = self.find_device_path(address)
        if device_path:
            try:
                device = dbus.Interface(self.bus.get_object("org.bluez", device_path),dbus_interface="org.bluez.Device1")
                device.Connect()
                # Check if connected
                props = dbus.Interface(self.bus.get_object("org.bluez", device_path), "org.freedesktop.DBus.Properties")
                connected = props.Get("org.bluez.Device1", "Connected")
                if connected:
                    print("Connection is successful")
                    return True
                else:
                    print("Connection attempted but not confirmed")
                    return False
            except Exception as e:
                print(f"Connection failed: {e}")
                return False
        else:
            print("Device path not found for connection")
            return False

    def le_connect(self, address):
        """Function for LE connection"""
        device_path = self.find_device_path(address)
        if device_path:
            try:
                device = dbus.Interface(self.bus.get_object("org.bluez", device_path),dbus_interface="org.bluez.Device1")
                device.ConnectProfile('0000110e-0000-1000-8000-00805f9b34fb')  # HID profile
            except Exception as e:
                print("LE Connection has failed")

    def set_discoverable_on(self):
        """Sets the Bluetooth device to be discoverable."""
        print("Setting Bluetooth device to be discoverable...")
        command = f"hciconfig {self.interface} piscan"
        subprocess.run(command, shell = True)
        print("Bluetooth device is now discoverable.")

    def set_discoverable_off(self):
        """Sets the Bluetooth device to be non-discoverable."""
        print("Setting Bluetooth device to be non-discoverable...")
        command = f"hciconfig {self.interface} noscan"
        subprocess.run(command, shell = True)
        print("Bluetooth device is now non-discoverable.")

    def is_device_paired(self, device_address):
        "Function to check whether the device is paired "
        device_path = self.find_device_path(device_address)
        if not device_path:
            return False
        bus = dbus.SystemBus()
        props = dbus.Interface(bus.get_object("org.bluez", device_path),"org.freedesktop.DBus.Properties")
        try:
            return props.Get("org.bluez.Device1", "Paired")
        except dbus.exceptions.DBusException:
            return False

    def is_device_connected(self, device_address):
        "Function to check whether the device is connected or not"
        device_path = self.find_device_path(device_address)
        if not device_path:
            return False
        bus = dbus.SystemBus()
        props = dbus.Interface(bus.get_object("org.bluez", device_path),"org.freedesktop.DBus.Properties")
        try:
            return props.Get("org.bluez.Device1", "Connected")
        except dbus.exceptions.DBusException:
            return False

    def set_device_address(self, address):
        """Set the current device for streaming and media control."""
        self.device_address = address
        self.device_path = self.find_device_path(address)
        self.device_sink = self.get_sink_for_device(address)

    def get_sink_for_device(self,address):
        """Get the PulseAudio sink for the Bluetooth device."""
        try:
            sinks_output = subprocess.check_output(["pactl", "list", "short", "sinks"], text=True)
            address_formatted = address.replace(":", "_").lower()
            for line in sinks_output.splitlines():
                if address_formatted in line.lower():
                    sink_name = line.split()[1]
                    return sink_name
        except Exception as e:
            print(f"Error getting sink for device: {e}")
        return None

    def _get_device_path(self):
        if not self.device_address:
            raise Exception("Device address not set")
        formatted_address = self.device_address.replace(":", "_")
        return f"/org/bluez/{self.interface}/dev_{formatted_address}"


    def find_device_path(self, address):
        """Find the device path by Bluetooth address."""
        # This function assumes you're using Bluez
        om = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = om.GetManagedObjects()
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                props = interfaces["org.bluez.Device1"]
                if props.get("Address") == address:
                    return path
        return None

    def refresh_device_list(self):
        """Refresh internal list of Bluetooth devices from BlueZ."""
        self.devices.clear()
        om = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = om.GetManagedObjects()
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                props = interfaces["org.bluez.Device1"]
                address = props.get("Address")
                name = props.get("Name", "Unknown")
                uuids = props.get("UUIDs", [])
                connected = props.get("Connected", False)
                if address:
                    self.devices[address] = {
                        "Name": name,
                        "UUIDs": uuids,
                        "Connected": connected,
                    }

    def get_connected_devices(self):
        "Function to find the connected devices so that it can be used in device selection as part of A2DP window"
        connected = {}
        bus = dbus.SystemBus()
        om = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = om.GetManagedObjects()
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                props = interfaces["org.bluez.Device1"]
                if props.get("Connected", False):
                    address = props.get("Address")
                    name = props.get("Name", "Unknown")
                    connected[address] = name
        return connected

