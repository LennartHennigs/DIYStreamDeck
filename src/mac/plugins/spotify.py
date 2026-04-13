# DIY Streamdeck Plugin code
# L. Hennigs and ChatGPT 4.0
# last changed: 23-05-18
# https://github.com/LennartHennigs/DIYStreamDeck


from typing import Optional
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from src.mac.plugins.base_plugin import BasePlugin


class SpotifyPlugin(BasePlugin):

    def __init__(self, config_file: str, verbose: bool) -> None:
        super().__init__(config_file, verbose)
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

    def _authenticate(self) -> Spotify:
        scope = "user-read-playback-state user-modify-playback-state"
        auth_manager = SpotifyOAuth(
            client_id=self.config['client_id'],
            client_secret=self.config['client_secret'],
            redirect_uri=self.config['redirect_uri'],
            scope=scope)
        spotify = Spotify(auth_manager=auth_manager)

        user = spotify.current_user()
        if not user:
            raise Exception("Failed to authenticate with Spotify.")
        return spotify


    def has_active_device(self):
        current_playback = self.sp.current_playback()
        if current_playback is None:
            self._log("No active device")
            return False
        return True


    def play_pause(self) -> None:
        try:
            current_playback = self.sp.current_playback()
            if current_playback is None:
                self._log("No active device")
                return
            if current_playback['is_playing']:
                self._log("Pause")
                self.sp.pause_playback()
            else:
                self.sp.start_playback()
                self._log(self.get_current_song_info())
        except Exception as e:
            self._log(f"Error: {e}")


    def play(self) -> None:
        current_playback = self.sp.current_playback()
        if current_playback is None:
            self._log("No active device")
            return
        if not current_playback['is_playing']:
            try:
                self.sp.start_playback()
                self._log(self.get_current_song_info())
            except Exception as e:
                self._log(f"Error: {e}")
        else:
            self._log("Already playing.")


    def pause(self) -> None:
        if self.has_active_device():
            try:
                self.sp.pause_playback()
            except Exception as e:
                self._log(f"Error: {e}")


    def next(self) -> None:
        if self.has_active_device():
            try:
                self.sp.next_track()
                self._log(self.get_current_song_info())
            except Exception as e:
                self._log(f"Error: {e}")


    def prev(self) -> None:
        if self.has_active_device():
            try:
                self.sp.previous_track()
                self._log(self.get_current_song_info())
            except Exception as e:
                self._log(f"Error: {e}")


    def volume_up(self, volume_change: int = 10) -> None:
        self._adjust_volume(volume_change)


    def volume_down(self, volume_change: int = 10) -> None:
        self._adjust_volume(-volume_change)


    def _adjust_volume(self, volume_change: int) -> None:
        playback = self.sp.current_playback()
        if not playback or 'device' not in playback:
            self._log("No active device")
            return
        try:
            current_volume = playback['device']['volume_percent']
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
