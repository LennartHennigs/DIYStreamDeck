import json
import os
from typing import Dict, Callable, Union, Optional
from phue import Bridge, Light
from src.mac.plugins.base_plugin import BasePlugin

class HuePlugin(BasePlugin):
    verbose: bool
    config: Dict[str, Union[str, int]]
    bridge: Bridge

    def __init__(self, config_file: str, verbose: bool) -> None:
        self.verbose = verbose
        self.config = self._load_config(config_file)
        self.bridge = self._connect_to_bridge()

    def commands(self) -> Dict[str, Callable]:
        return {
            'hue.turn_on': self.turn_on,
            'hue.turn_off': self.turn_off,
            'hue.toggle': self.toggle,
        }

    def _load_config(self, config_file: str) -> Dict[str, Union[str, int]]:
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self._log_and_raise(f"Config file {config_file} not found.")
        except json.JSONDecodeError:
            self._log_and_raise(
                f"Failed to parse config file {config_file}. Please check if it is a valid JSON file."
            )

    def _connect_to_bridge(self) -> Bridge:
        bridge_ip = self.config.get('bridge_ip')
        if not bridge_ip:
            raise ValueError("Bridge IP not found in the config.")

        bridge = Bridge(bridge_ip)
        try:
            bridge.connect()
        except Exception as e:
            raise ConnectionError("Failed to connect to the bridge.") from e
        return bridge


    def _find_light(self, lamp_identifier: Union[int, str]) -> Optional[Light]:
        lights = list(self.bridge.lights)
        if isinstance(lamp_identifier, int):
            idx = lamp_identifier
            return lights[idx] if 0 <= idx < len(lights) else None
        return next(
            (light for light in lights if light.name.lower() == lamp_identifier.lower()), None
        )

    def _change_light_state(self, lamp_identifier: Union[int, str, Light], state: bool) -> None:
        light = self._find_light(lamp_identifier) if isinstance(lamp_identifier, (int, str)) else lamp_identifier
        if light is None:
            print(f"Could not find a light with the name or index: {lamp_identifier}")
            return
        light.on = state
        if self.verbose:
            print(f"Turned {'on' if state else 'off'} '{light.name}'")

    def turn_on(self, lamp_identifier: Union[int, str]) -> None:
        self._change_light_state(lamp_identifier, True)

    def turn_off(self, lamp_identifier: Union[int, str]) -> None:
        self._change_light_state(lamp_identifier, False)

    def toggle(self, lamp_identifier: Union[int, str]) -> None:
        light = self._find_light(lamp_identifier)
        if light is None:
            print(f"Could not find a light with the name or index: '{lamp_identifier}'")
            return
        self._change_light_state(light, not light.on)
