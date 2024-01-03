import os
import json
from phue import Bridge

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, 'plugins', 'config', 'hue.json'))
config = {}

try:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
        # connect to bridge
        bridge = Bridge(config['bridge_ip'])
        bridge.connect()
        # Get the light objects
        lights = bridge.get_light_objects()
        # Print the lamp names and indices
        for lamp_id, light in enumerate(lights):
            print(f"{lamp_id}: {light.name}")

except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"config file not found")
except Exception as e:
    print(f"{e}")
