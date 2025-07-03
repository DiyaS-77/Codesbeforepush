import dbus
import subprocess
from test_automation.UI.Backend_lib.Linux.daemons import BluezServices


dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

class A2DPManager:
    def __init__(self,interface=None):
        self.interface = interface
        self.bus = dbus.SystemBus()
        self.bluez_services=BluezServices(interface=self.interface)
        self.stream_process = None
        self.device_sink = None



    def start_streaming(self, device_address, audio_file):
        """Start A2DP streaming with the provided audio file path."""
        print(f"Starting A2DP streaming to {device_address} with file: {audio_file}")
        # Check if the device address corresponds to a valid device
        device_path = self.bluez_services.find_device_path(device_address)
        if not device_path:
            print(f"Device path not found for address {device_address}")
            return False

        # Get the PulseAudio sink for this device (make sure the correct sink is set)
        self.device_sink =self.get_sink_for_device(device_address)
        if not self.device_sink:
            print("No PulseAudio sink found for the selected Bluetooth device.")
            return False

        #conversion of .mp3 to wav format
        if audio_file.endswith(".mp3"):
            wav_file="/tmp/temp_audio.wav"
            if not self.convert_mp3_to_wav(audio_file,wav_file):
                return False
            audio_file=wav_file

        try:
            # Run aplay and redirect to the selected Bluetooth sink

            self.stream_process = subprocess.Popen(
                ["aplay", "-D", "pulse", audio_file],
                env={**subprocess.os.environ, "PULSE_SINK": self.device_sink}
            )

            print(f"Streaming audio to {device_address}")
            return True
        except Exception as e:
            print(f"Error while starting streaming: {e}")
            return False

    def convert_mp3_to_wav(self,audio_path,wav_path):
        try:
            subprocess.run(['ffmpeg','-y','-i',audio_path,wav_path],check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Conversion failed[mp3 to wav]: {e}")
            return False

    def stop_streaming(self):
        """Stop the A2DP streaming process."""
        print("Stopping A2DP streaming...")
        if self.stream_process:
            try:
                self.stream_process.terminate()
                self.stream_process.wait()
                self.stream_process = None
                print("Streaming stopped successfully.")
                return True
            except Exception as e:
                print(f"Error while stopping streaming: {e}")
                return False
        else:
            print("No active streaming process.")
            return False


    def _get_media_control_interface(self, address):
        """Finds the MediaControl1 interface associated with a specific Bluetooth device."""
        try:
            om = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
            objects = om.GetManagedObjects()
            formatted_addr = address.replace(":", "_").upper()

            print("Searching for MediaControl1 interface...")
            for path, interfaces in objects.items():
                if "org.bluez.MediaControl1" in interfaces:
                    if formatted_addr in path:
                        print(f"Found MediaControl1 interface at: {path}")
                        media_control = dbus.Interface(
                            self.bus.get_object("org.bluez", path),
                            "org.bluez.MediaControl1"
                        )
                        return media_control
            print(f"No MediaControl1 interface found for device: {address}")
        except Exception as e:
            print(f"Failed to get MediaControl1 interface: {e}")
        return None

    def play(self, address):
        "Function for media control action play"
        try:
            control = self._get_media_control_interface(address)
            if control:
                control.Play()
                print(f"Sent Play to {address}")
        except Exception as e:
            print(f"Failed to play: {e}")

    def pause(self, address):
        "Function for media control action pause"
        try:
            control = self._get_media_control_interface(address)
            if control:
                control.Pause()
                print(f"Sent Pause to {address}")
        except Exception as e:
            print(f"Failed to pause: {e}")


    def next(self, address):
        "Function for media control action next"
        try:
            control = self._get_media_control_interface(address)
            if control:
                control.Next()
                print(f"Sent Next to {address}")
        except Exception as e:
            print(f"Failed to send Next: {e}")

    def previous(self, address):
        "Function for media control action previous"
        try:
            control = self._get_media_control_interface(address)
            if control:
                control.Previous()
                print(f"Sent Previous to {address}")
        except Exception as e:
            print(f"Failed to send Previous: {e}")

    def rewind(self, address):
        "Function for media control action rewind"
        try:
            control = self._get_media_control_interface(address)
            if control:
                control.Rewind()
                print(f"Sent Rewind to {address}")
        except Exception as e:
            print(f"Failed to send Rewind: {e}")

    def get_connected_a2dp_sink_devices(self):
        "Function to get connected a2dp sink devices"
        self.bluez_services.refresh_device_list()
        return {
            addr: dev["Name"]
            for addr, dev in self.bluez_services.devices.items()
            #for addr, dev in self.devices.items()
            if dev["Connected"] and any("110b" in uuid.lower() for uuid in dev["UUIDs"])  # A2DP Sink UUID
        }

    def get_connected_a2dp_source_devices(self):
        "Function to get connected a2dp source devices"
        self.bluez_services.refresh_device_list()
        return {
            addr: dev["Name"]
            for addr, dev in self.bluez_services.devices.items()
            #for addr, dev in self.devices.items()
            if dev["Connected"] and any("110a" in uuid.lower() for uuid in dev["UUIDs"])  # A2DP Source UUID
        }


    def set_device_address(self, address):
        """Set the current device for streaming and media control."""
        self.device_address = address
        self.device_path = self.bluez_services.find_device_path(address)
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

