import importlib.util
import importlib.machinery
import os
import sys
import types
import time

# Helper to load module from path so we can inject fake sys.modules first
def load_module_from_path(module_name, path):
    loader = importlib.machinery.SourceFileLoader(module_name, path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class FakeKey:
    def __init__(self, number):
        self.number = number
    def set_led(self, *args, **kwargs):
        pass
    def led_off(self):
        pass


class FakeKeypad:
    def __init__(self):
        self.keys = [FakeKey(i) for i in range(16)]
        self._press = {}
        self._release = {}
    def on_press(self, key, handler):
        self._press[key.number] = handler
    def on_release(self, key, handler):
        self._release[key.number] = handler
    def update(self):
        pass


class FakeConsole:
    def __init__(self, initial=None):
        self._buf = list(initial or [])
        self.output_buffer = ""
    @property
    def in_waiting(self):
        return 1 if self._buf else 0
    def readline(self):
        return self._buf.pop(0) if self._buf else b''
    def write(self, data):
        # Store output for testing
        if isinstance(data, bytes):
            self.output_buffer += data.decode('utf-8')
        else:
            self.output_buffer += str(data)
    def get_output(self):
        """Get output and clear buffer - compatible with MockUSBCDC"""
        output = self.output_buffer
        self.output_buffer = ""
        return output
    def add_input(self, text):
        """Add input text - compatible with MockUSBCDC"""
        if isinstance(text, str):
            text = text.encode('utf-8')
        if text not in self._buf:
            self._buf.append(text)


def setup_fake_modules(buf=None):
    # Insert fake modules that the firmware expects
    # Only override if not already set up by other tests
    if 'usb_hid' not in sys.modules or not hasattr(sys.modules['usb_hid'], 'devices'):
        sys.modules['usb_hid'] = types.SimpleNamespace(devices=[])
    
    # Create console but ensure compatibility with other tests
    fake_console = FakeConsole(buf)
    if 'usb_cdc' not in sys.modules:
        sys.modules['usb_cdc'] = types.SimpleNamespace(console=fake_console)
    else:
        # Update existing console but preserve its interface
        sys.modules['usb_cdc'].console = fake_console
    
    if 'rgbkeypad' not in sys.modules:
        sys.modules['rgbkeypad'] = types.SimpleNamespace(RgbKeypad=FakeKeypad)
    
    # minimal keyboard objects - only set if not already present
    if 'adafruit_hid.keyboard' not in sys.modules:
        sys.modules['adafruit_hid.keyboard'] = types.SimpleNamespace(Keyboard=lambda devices: types.SimpleNamespace(release_all=lambda: None))
    if 'adafruit_hid.keyboard_layout_us' not in sys.modules:
        sys.modules['adafruit_hid.keyboard_layout_us'] = types.SimpleNamespace(KeyboardLayoutUS=lambda k: None)
    # Provide a simple Keycode object; firmware only inspects dir() which can be empty
    if 'adafruit_hid.keycode' not in sys.modules:
        sys.modules['adafruit_hid.keycode'] = types.SimpleNamespace(Keycode=types.SimpleNamespace())
    if 'board' not in sys.modules:
        sys.modules['board'] = types.SimpleNamespace()


def test_hello_loads_basic_config_and_clears():
    # prepare fakes and load module
    setup_fake_modules(buf=[b'HELLO:1.2.1\n'])
    path = os.path.join(os.getcwd(), 'src', 'pi_pico', 'code.py')
    pico = load_module_from_path('pico_code', path)

    # Prevent parse_json from opening files; return minimal config
    def fake_parse(self, filename):
        return {"applications": {"_otherwise": {}}, "folders": {}, "urls": {}, "settings": {}}
    pico.KeyController.parse_json = fake_parse

    kc = pico.KeyController()

    # Simulate reading HELLO from serial and processing it
    val = kc.read_serial_line()
    assert val == 'HELLO:1.2.1'
    kc.process_serial_str(val)

    # After HELLO the keypad should be loaded (unloaded False) and last_heartbeat updated
    assert kc.unloaded is False
    assert abs(time.time() - kc.last_heartbeat) < 2.0
    # basic config (empty dict in this test) should be set
    assert isinstance(kc.current_config, dict)


def test_bye_clears_and_unloads():
    setup_fake_modules(buf=[])
    path = os.path.join(os.getcwd(), 'src', 'pi_pico', 'code.py')
    pico = load_module_from_path('pico_code2', path)
    def fake_parse(self, filename):
        return {"applications": {"_otherwise": {}}, "folders": {}, "urls": {}, "settings": {}}
    pico.KeyController.parse_json = fake_parse

    kc = pico.KeyController()
    kc.process_serial_str('BYE')

    assert kc.unloaded is True
    # current_config should be cleared
    assert kc.current_config == {}


def test_hb_updates_last_heartbeat_and_unload_keypad():
    setup_fake_modules(buf=[b'HB\n'])
    path = os.path.join(os.getcwd(), 'src', 'pi_pico', 'code.py')
    pico = load_module_from_path('pico_code3', path)
    def fake_parse(self, filename):
        return {"applications": {"_otherwise": {}}, "folders": {}, "urls": {}, "settings": {}}
    pico.KeyController.parse_json = fake_parse

    kc = pico.KeyController()
    # ensure last_heartbeat is in the past
    kc.last_heartbeat = 0
    val = kc.read_serial_line()
    assert val == 'HB'
    kc.process_serial_str(val)
    assert kc.last_heartbeat > 0

    # Test unload_keypad directly
    kc.unloaded = False
    kc.current_config = {'some': 'config'}
    kc.unload_keypad()
    assert kc.unloaded is True
    assert kc.current_config == {}
