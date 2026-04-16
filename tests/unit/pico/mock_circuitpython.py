# Mock CircuitPython modules for testing Pi Pico code
from unittest.mock import Mock, MagicMock
from typing import List, Dict, Any
import time


class MockKey:
    """Mock RgbKeypad key"""
    def __init__(self, number: int):
        self.number = number
        self.led_color = (0, 0, 0)
        
    def set_led(self, r: int, g: int, b: int) -> None:
        self.led_color = (r, g, b)
        
    def led_off(self) -> None:
        self.led_color = (0, 0, 0)


class MockRgbKeypad:
    """Mock RgbKeypad class"""
    def __init__(self):
        self.keys = [MockKey(i) for i in range(16)]
        self.press_handlers = {}
        self.release_handlers = {}
        
    def on_press(self, key: MockKey, handler):
        self.press_handlers[key.number] = handler
        
    def on_release(self, key: MockKey, handler):
        self.release_handlers[key.number] = handler
        
    def update(self):
        pass
        
    def simulate_key_press(self, key_num: int):
        """Test helper to simulate key press"""
        if key_num in self.press_handlers:
            self.press_handlers[key_num](self.keys[key_num])
            
    def simulate_key_release(self, key_num: int):
        """Test helper to simulate key release"""
        if key_num in self.release_handlers:
            self.release_handlers[key_num](self.keys[key_num])


class MockKeycode:
    """Mock Keycode constants"""
    A = 4
    B = 5
    C = 6
    D = 7
    E = 8
    F = 9
    G = 10
    H = 11
    I = 12
    J = 13
    K = 14
    L = 15
    M = 16
    N = 17
    O = 18
    P = 19
    Q = 20
    R = 21
    S = 22
    T = 23
    U = 24
    V = 25
    W = 26
    X = 27
    Y = 28
    Z = 29
    COMMAND = 227
    GUI = 227
    CONTROL = 224
    SHIFT = 225
    ALT = 226
    SPACE = 44
    ENTER = 40
    TAB = 43
    
    # Add missing keycodes that might be referenced
    LEFT_ARROW = 80
    RIGHT_ARROW = 79
    UP_ARROW = 82
    DOWN_ARROW = 81
    DELETE = 42
    BACKSPACE = 42
    
    @classmethod
    def __dir__(cls):
        """Return all attributes for dir() calls"""
        return ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', 'COMMAND', 'GUI', 'CONTROL', 'SHIFT', 'ALT', 'SPACE', 'ENTER', 'TAB', 'LEFT_ARROW', 'RIGHT_ARROW', 'UP_ARROW', 'DOWN_ARROW', 'DELETE', 'BACKSPACE']


class MockKeyboard:
    """Mock Keyboard HID"""
    def __init__(self, devices):
        self.pressed_keys = []
        
    def press(self, *keycodes):
        for keycode in keycodes:
            if keycode not in self.pressed_keys:
                self.pressed_keys.append(keycode)
                
    def release_all(self):
        self.pressed_keys = []


class MockKeyboardLayoutUS:
    """Mock US keyboard layout"""
    def __init__(self, keyboard):
        self.keyboard = keyboard
        self.typed_chars = []

    def write(self, char):
        self.typed_chars.append(char)


class MockUSBCDC:
    """Mock USB CDC console"""
    def __init__(self):
        self.input_buffer = ""
        self.output_buffer = ""
        
    @property
    def in_waiting(self):
        return len(self.input_buffer)
        
    def readline(self):
        if '\n' in self.input_buffer:
            line, self.input_buffer = self.input_buffer.split('\n', 1)
            return (line + '\n').encode('utf-8')
        return b''
        
    def write(self, data: bytes):
        self.output_buffer += data.decode('utf-8')
        
    def add_input(self, text: str):
        """Test helper to add input"""
        self.input_buffer += text
        
    def get_output(self) -> str:
        """Test helper to get output"""
        output = self.output_buffer
        self.output_buffer = ""
        return output


# Mock modules that need to be available before importing code.py
import sys
from unittest.mock import MagicMock

# Mock the hardware modules
sys.modules['usb_hid'] = MagicMock()
sys.modules['usb_hid'].devices = []

# Create a USB CDC module with our specific mock console
usb_cdc_module = MagicMock()
usb_cdc_module.console = MockUSBCDC()
sys.modules['usb_cdc'] = usb_cdc_module

sys.modules['rgbkeypad'] = MagicMock()
sys.modules['rgbkeypad'].RgbKeypad = MockRgbKeypad

sys.modules['adafruit_hid'] = MagicMock()
sys.modules['adafruit_hid.keyboard'] = MagicMock()
sys.modules['adafruit_hid.keyboard'].Keyboard = MockKeyboard

sys.modules['adafruit_hid.keyboard_layout_us'] = MagicMock()
sys.modules['adafruit_hid.keyboard_layout_us'].KeyboardLayoutUS = MockKeyboardLayoutUS

# Create the keycode module with proper dir() support
keycode_module = MagicMock()
keycode_module.Keycode = MockKeycode
sys.modules['adafruit_hid.keycode'] = keycode_module

sys.modules['board'] = MagicMock()