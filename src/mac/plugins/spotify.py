# DIY Streamdeck Plugin code
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-18
# https://github.com/LennartHennigs/DIYStreamDeck


import json
from typing import Optional
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from base_plugin import BasePlugin


class SpotifyPlugin(BasePlugin):

    def __init__(self, config_file: str, verbose: bool) -> None:
        self.verbose = verbose
        self.config = self._load_config(config_file)
        self.sp = self._authenticate()

    def commands(self):
        return {
            'spotify.play': self.play,
            'spotify.pause': self.pause,
            'spotify.next': self.next,
            'spotify.prev': self.prev,
            'spotify.volume_up': self.volume_up,
            'spotify.volume_down': self.volume_down,
            'spotify.playpause': self.play_pause,
        }

    def _load_config(self, config_file: str) -> dict:
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self._log_and_raise(str(e))

    def _authenticate(self) -> Spotify:
        try:
            scope = "user-read-playback-state, user-modify-playback-state,"
            auth_manager = SpotifyOAuth(
                client_id=self.config['client_id'],
                client_secret=self.config['client_secret'],
                redirect_uri=self.config['redirect_uri'],
                scope=scope)
            return Spotify(auth_manager=auth_manager)
        except Exception as e:
            self._log_and_raise(f"Failed to authenticate with Spotify: {e}")

    def execute_command(self, command: str) -> None:
        command_name, params = self._parse_command(command)
        plugin_command = self.commands().get(command_name)
        if plugin_command:
            plugin_command(*params)
        else:
            self._log(f"Invalid command: {command}")

    def _parse_command(self, command: str) -> tuple:
        command_parts = command.split('(')
        command_name = command_parts[0]
        params = command_parts[1][:-1].split(',') if len(command_parts) > 1 else []
        params = [param.strip() for param in params]
        return command_name, params

    def play_pause(self) -> None:
        try:
            if self.sp.current_playback()['is_playing']:
                self._log("Pause")
                self.pause()
            else:
                self.play()
        except Exception as e:
            self._log(f"An error occurred: {e}")
    
    def play(self) -> None:
        current_playback = self.sp.current_playback()
        if current_playback is None or not current_playback['is_playing']:
            self.sp.start_playback()
            self._log(self.get_current_song_info())
        else:
            self._log("No song is currently playing.")

    def pause(self) -> None:
        self.sp.pause_playback()

    def next(self) -> None:
        self.sp.next_track()
        self._log(self.get_current_song_info())

    def prev(self) -> None:
        self.sp.previous_track()
        self._log(self.get_current_song_info())

    def volume_up(self, volume_change: int = 10) -> None:
        self._adjust_volume(volume_change)

    def volume_down(self, volume_change: int = 10) -> None:
        self._adjust_volume(-volume_change)

    def _adjust_volume(self, volume_change: int) -> None:
        try:
            current_volume = self.sp.current_playback()['device']['volume_percent']
            new_volume = max(min(current_volume + volume_change, 100), 0)
            self.sp.volume(new_volume)
            self._log(f"Volume {'increased' if volume_change > 0 else 'decreased'} to {new_volume}%")
        except Exception as e:
            self._log(f"Failed to {'increase' if volume_change > 0 else 'decrease'} volume: {e}")

    def get_current_song_info(self) -> Optional[str]:
        current_song = self.sp.current_user_playing_track()
        if current_song is not None and current_song['is_playing']:
            track = current_song['item']
            artist = track['artists'][0]['name']
            song_name = track['name']
            return f"{artist} - {song_name}"
        else:
            return None

    def _log_and_raise(self, message: str) -> None:
        self._log(message)
        raise Exception(message)

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message)
