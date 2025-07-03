from __future__ import absolute_import, print_function, unicode_literals
from optparse import OptionParser
import sys
import dbus
import dbus.service
import dbus.mainloop.glib
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal
try:
  from gi.repository import GObject
except ImportError:
  import gobject as GObject

BUS_NAME = 'org.bluez'
AGENT_INTERFACE = 'org.bluez.Agent1'
AGENT_PATH = "/test/agent"

bus = None
device_obj = None
dev_path = None

def ask(prompt):
	try:
		return raw_input(prompt)
	except:
		return input(prompt)

def set_trusted(path):
	props = dbus.Interface(bus.get_object("org.bluez", path),"org.freedesktop.DBus.Properties")
	props.Set("org.bluez.Device1", "Trusted", True)

def dev_connect(path):
	dev = dbus.Interface(bus.get_object("org.bluez", path),"org.bluez.Device1")
	dev.Connect()

class Rejected(dbus.DBusException):
	_dbus_error_name = "org.bluez.Error.Rejected"

class Agent(dbus.service.Object):
	exit_on_release = True

	def set_exit_on_release(self, exit_on_release):
		self.exit_on_release = exit_on_release

	@dbus.service.method(AGENT_INTERFACE,in_signature="", out_signature="")
	def Release(self):
		print("Release")
		if self.exit_on_release:
			mainloop.quit()

	@dbus.service.method(AGENT_INTERFACE,in_signature="os", out_signature="")
	def AuthorizeService(self, device, uuid):
		print("AuthorizeService (%s, %s)" % (device, uuid))
		authorize = ask("Authorize connection (yes/no): ")
		if (authorize == "yes"):
			return
		raise Rejected("Connection rejected by user")

	@dbus.service.method(AGENT_INTERFACE,in_signature="o", out_signature="s")
	def RequestPinCode(self, device):
		print("RequestPinCode (%s)" % (device))
		set_trusted(device)
		return ask("Enter PIN Code: ")

	@dbus.service.method(AGENT_INTERFACE,in_signature="o", out_signature="u")
	def RequestPasskey(self, device):
		print("RequestPasskey (%s)" % (device))
		set_trusted(device)
		passkey = ask("Enter passkey: ")
		return dbus.UInt32(passkey)


	@dbus.service.method(AGENT_INTERFACE,in_signature="ouq", out_signature="")
	def DisplayPasskey(self, device, passkey, entered):
		print("DisplayPasskey (%s, %06u entered %u)" %
						(device, passkey, entered))

	@dbus.service.method(AGENT_INTERFACE,in_signature="os", out_signature="")
	def DisplayPinCode(self, device, pincode):
		print("DisplayPinCode (%s, %s)" % (device, pincode))

	@dbus.service.method(AGENT_INTERFACE,in_signature="ou", out_signature="")
	def RequestConfirmation(self, device, passkey):
		print("RequestConfirmation (%s, %06d)" % (device, passkey))
		confirm = ask("Confirm passkey (yes/no): ")
		if (confirm == "yes"):
			set_trusted(device)
			return
		raise Rejected("Passkey doesn't match")

	@dbus.service.method(AGENT_INTERFACE,in_signature="ou", out_signature=" ")
	def RequestConfirmation(self, device, passkey):
		print("Request-Confirmation (%s,%06d)" % (device,passkey))
		confirm = ask("Confirm passkey (yes/no):")
		if (confirm == "yes"):
			set_trusted(device)
			return passkey
		raise Rejected("Passkey does not match")

	@dbus.service.method(AGENT_INTERFACE,in_signature="o", out_signature="")
	def RequestAuthorization(self, device):
		print("RequestAuthorization (%s)" % (device))
		auth = ask("Authorize? (yes/no): ")
		if (auth == "yes"):
			return
		raise Rejected("Pairing rejected")

	@dbus.service.method(AGENT_INTERFACE,in_signature="", out_signature="")
	def Cancel(self):
		print("Cancel")

def pair_reply():
	print("Device paired")
	set_trusted(dev_path)
	dev_connect(dev_path)
	mainloop.quit()

def pair_error(error):
	err_name = error.get_dbus_name()
	if err_name == "org.freedesktop.DBus.Error.NoReply" and device_obj:
		print("Timed out. Cancelling pairing")
		device_obj.CancelPairing()
	else:
		print("Creating device failed: %s" % (error))
	mainloop.quit()

if __name__ == '__main__':
	dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

	bus = dbus.SystemBus()

	capability = "DisplayYesNo"

	parser = OptionParser()
	parser.add_option("-i", "--adapter", action="store",
					type="string",
					dest="adapter_pattern",
					default=None)
	parser.add_option("-c", "--capability", action="store",
					type="string", dest="capability")
	parser.add_option("-t", "--timeout", action="store",
					type="int", dest="timeout",
					default=60000)
	(options, args) = parser.parse_args()
	if options.capability:
		capability  = options.capability

	path = "/test/agent"
	agent = Agent(bus, path)

	mainloop = GObject.MainLoop()

	obj = bus.get_object(BUS_NAME, "/org/bluez");
	manager = dbus.Interface(obj, "org.bluez.AgentManager1")
	manager.RegisterAgent(path, capability)

	print("Agent registered")

	if len(args) > 0 and args[0].startswith("hci"):
		options.adapter_pattern = args[0]
		del args[:1]

	if len(args) > 0:
		device = bluezutils.find_device(args[0],
						options.adapter_pattern)
		dev_path = device.object_path
		agent.set_exit_on_release(False)
		device.Pair(reply_handler=pair_reply, error_handler=pair_error,
								timeout=60000)
		device_obj = device
	else:
		manager.RequestDefaultAgent(path)
	mainloop.run()

#
# from __future__ import absolute_import, print_function, unicode_literals
# import dbus
# import dbus.service
# import dbus.mainloop.glib
# from gi.repository import GLib
#
# AGENT_INTERFACE = 'org.bluez.Agent1'
#
# class Rejected(dbus.DBusException):
#     _dbus_error_name = "org.bluez.Error.Rejected"
#
# class Agent(dbus.service.Object):
#     def __init__(self, bus, path, signal_callback=None):
#         super().__init__(bus, path)
#         self.signal_callback = signal_callback
#         self.bus = bus
#         self.exit_on_release = True
#         self._waiting_loop = None
#         self._rejected = False
#
#     @dbus.service.method(AGENT_INTERFACE, in_signature="ou", out_signature="")
#     def RequestConfirmation(self, device, passkey):
#         print(f"[Agent] RequestConfirmation ({device}, {passkey:06d})")
#         self._rejected = False
#         self._waiting_loop = GLib.MainLoop()
#
#         def respond(confirmed):
#             if confirmed:
#                 self.set_trusted(device)
#             else:
#                 self._rejected = True
#             if self._waiting_loop.is_running():
#                 self._waiting_loop.quit()
#
#         if self.signal_callback:
#             self.signal_callback(device, passkey, respond)
#
#         self._waiting_loop.run()
#
#         if self._rejected:
#             raise Rejected("Passkey doesn't match")
#
#     def set_trusted(self, path):
#         props = dbus.Interface(
#             self.bus.get_object("org.bluez", path),
#             "org.freedesktop.DBus.Properties"
#         )
#         props.Set("org.bluez.Device1", "Trusted", True)
#
#     @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
#     def Release(self):
#         print("[Agent] Released")
#         if self.exit_on_release and self._waiting_loop and self._waiting_loop.is_running():
#             self._waiting_loop.quit()
#
#

