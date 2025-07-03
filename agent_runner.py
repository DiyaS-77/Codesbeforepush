import dbus
import dbus.mainloop.glib
from gi.repository import GLib
import threading
from threading import Thread
from test_automation.UI.Backend_lib.Linux.agent import Agent


class AgentRunner:
    def __init__(self, capability="NoInputNoOutput", agent_path="/test/agent"):
        self.capability = capability
        self.agent_path = agent_path
        self.mainloop = None
        self.bus = None
        self.agent = None

    def start(self):

        # Setup D-Bus main loop
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()

        # Create and register your existing Agent
        self.agent = Agent(self.bus, self.agent_path)
        self.mainloop = GLib.MainLoop()

        # Register the agent with BlueZ
        manager = dbus.Interface(self.bus.get_object("org.bluez", "/org/bluez"),"org.bluez.AgentManager1")
        manager.RegisterAgent(self.agent_path, self.capability)
        manager.RequestDefaultAgent(self.agent_path)
        print(f"[Agent] Registered with capability: {self.capability}")

        # Run the GLib main loop in a background thread
        thread = Thread(target=self.mainloop.run, daemon=True)
        thread.start()

    def stop(self):
        if self.mainloop.is_running():
            self.mainloop.quit()


#
# from PyQt6.QtCore import QObject, pyqtSignal, QEventLoop
# import dbus
# import dbus.mainloop.glib
# from threading import Thread
# from gi.repository import GLib
# from BT_UI.agent import Agent
#
# class AgentRunner(QObject):
#     confirmation_requested = pyqtSignal(str, int)
#
#     def __init__(self, capability="DisplayYesNo", agent_path="/test/agent"):
#         super().__init__()
#         self.capability = capability
#         self.agent_path = agent_path
#         self.mainloop = None
#         self.bus = None
#         self.agent = None
#         self._event_loop = None
#         self._confirmation_result = None
#
#     def start(self):
#         dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
#         self.bus = dbus.SystemBus()
#
#         def handle_request(device, passkey, respond_func):
#             self._confirmation_result = None
#             self._event_loop = QEventLoop()
#
#             self.confirmation_requested.emit(device, passkey)
#
#             self._event_loop.exec()
#
#             respond_func(self._confirmation_result or False)
#
#         self.agent = Agent(self.bus, self.agent_path, signal_callback=handle_request)
#
#         manager = dbus.Interface(
#             self.bus.get_object("org.bluez", "/org/bluez"),
#             "org.bluez.AgentManager1"
#         )
#         manager.RegisterAgent(self.agent_path, self.capability)
#         manager.RequestDefaultAgent(self.agent_path)
#         print(f"[AgentRunner] Agent registered with capability: {self.capability}")
#
#         self.mainloop = GLib.MainLoop()
#         thread = Thread(target=self.mainloop.run, daemon=True)
#         thread.start()
#
#     def respond_to_confirmation(self, confirmed: bool):
#         self._confirmation_result = confirmed
#         if self._event_loop and self._event_loop.isRunning():
#             self._event_loop.quit()
#
#
#     def stop(self):
#         if self.mainloop and self.mainloop.is_running():
#             self.mainloop.quit()

