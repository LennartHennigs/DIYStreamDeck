# DIY Streamdeck Plugin code
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-18
# https://github.com/LennartHennigs/DIYStreamDeck


import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from base_plugin import BasePlugin


class SpotifyPlugin(BasePlugin):
    def commands(self):
            return {
                'spotify.play': self.play,
                'spotify.pause': self.pause,
                'spotify.next': self.next,
                'spotify.prev': self.prev,
                'spotify.volume_up': self.volume_up,
                'spotify.volume_down': self.volume_down,
                'spotify.playpause': self.playpause,
            }

    def __init__(self, config_file):
        try:
            self.config = self.load_config(config_file)
            self.sp = self.authenticate()
        except Exception as e:
            print(f"Failed to initialize SpotifyPlugin: {e}")
            raise

    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            print(f"Config file {config_file} not found.")
            raise
        except json.JSONDecodeError:
            print(
                f"Failed to parse config file {config_file}. Please check if it is a valid JSON file.")
            raise

    def authenticate(self):
        try:
            scope = "user-read-playback-state, user-modify-playback-state,"
            auth_manager = SpotifyOAuth(client_id=self.config['client_id'],
                                        client_secret=self.config['client_secret'],
                                        redirect_uri=self.config['redirect_uri'],
                                        scope=scope)
            return spotipy.Spotify(auth_manager=auth_manager)
        except Exception as e:
            print(f"Failed to authenticate with Spotify: {e}")
            raise

    def execute_command(self, command):
        try:
            command_parts = command.split('(')
            command_name = command_parts[0]

            if len(command_parts) > 1:
                params = command_parts[1][:-1].split(',')
                params = [param.strip() for param in params]
            else:
                params = []

            plugin_command = self.commands().get(command_name)
            if plugin_command:
                plugin_command(*params)
            else:
                print(f"Invalid command: {command}")
        except Exception as e:
            pass
            # print(f"Failed to execute the command: {e}")

    def playpause(self):
        try:
            current_playback = self.sp.current_playback()
            if current_playback is not None and current_playback['is_playing']:
                self.pause()
            else:
                self.play()
        except Exception as e:
            # print(f"Failed to toggle play/pause: {e}")
            pass


    def play(self):
        try:
            current_playback = self.sp.current_playback()
            if current_playback is not None and current_playback['is_playing']:
                print("The device is already playing.")
            else:
                self.sp.start_playback()
                print("Playback started.")
        except Exception as e:
            pass
            # print(f"Failed to execute play command: {e}")

    def pause(self):
        try:
            self.sp.pause_playback()
        except Exception as e:
            pass
            # print(f"Failed to execute pause command: {e}")

    def next(self):
        try:
            self.sp.next_track()
        except Exception as e:
            pass
            # print(f"Failed to execute next command: {e}")

    def prev(self):
        try:
            self.sp.previous_track()
        except Exception as e:
            pass
            # print(f"Failed to execute next command: {e}")

    def volume_up(self, volume_change=10):
        try:
            current_volume = self.sp.current_playback()[
                'device']['volume_percent']
            new_volume = min(current_volume + volume_change, 100)
            print(new_volume)
            self.sp.volume(new_volume, None)
            print(f"Volume increased to {new_volume}%")
        except Exception as e:
            print(f"Failed to increase volume: {e}")

    def volume_down(self, volume_change=10):
        try:
            current_volume = self.sp.current_playback()[
                'device']['volume_percent']
            new_volume = max(current_volume - volume_change, 0)
            # None indicates the active device
            self.sp.volume(new_volume, None)
            print(f"Volume decreased to {new_volume}%")
        except Exception as e:
            print(f"Failed to decrease volume: {e}")
