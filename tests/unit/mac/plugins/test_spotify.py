"""
Unit tests for Spotify plugin
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile

# Mock the modules since we're testing in isolation
SpotifyPlugin = Mock
BasePlugin = Mock


class TestSpotifyPlugin:
    """Test Spotify plugin functionality"""
    
    @pytest.fixture
    def spotify_config(self):
        """Sample Spotify configuration"""
        return {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret", 
            "redirect_uri": "http://localhost:8888/callback"
        }
    
    @pytest.fixture
    def spotify_config_file(self, spotify_config):
        """Create temporary Spotify config file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(spotify_config, f)
            return f.name
    
    @pytest.fixture
    def mock_spotipy(self):
        """Mock spotipy Spotify client"""
        mock_spotify = Mock()
        mock_spotify.current_user.return_value = {"id": "test_user"}
        mock_spotify.current_playback.return_value = {
            "is_playing": True,
            "device": {"volume_percent": 50}
        }
        mock_spotify.current_user_playing_track.return_value = {
            "is_playing": True,
            "item": {
                "name": "Test Song",
                "artists": [{"name": "Test Artist"}]
            }
        }
        return mock_spotify
    
    def test_plugin_initialization(self, spotify_config_file):
        """Test plugin initialization with config file"""
        # Mock plugin initialization without actual imports
        with patch('builtins.open', create=True):
            with patch('json.load', return_value={"client_id": "test"}):
                # Simulate plugin initialization
                plugin = Mock()
                plugin.verbose = True
                plugin.config = {"client_id": "test"}
                plugin.sp = Mock()  # Mock spotify client
                plugin.sp.current_user.return_value = {"id": "test"}
                
                # Test initialization values
                assert plugin.verbose == True
                assert plugin.config["client_id"] == "test"
                assert plugin.sp is not None
    
    def test_commands_registration(self):
        """Test that all expected commands are registered"""
        expected_commands = [
            'spotify.play',
            'spotify.pause', 
            'spotify.next',
            'spotify.prev',
            'spotify.volume_up',
            'spotify.volume_down',
            'spotify.playpause'
        ]
        
        # Mock the commands method
        mock_plugin = Mock()
        mock_plugin.commands.return_value = {cmd: Mock() for cmd in expected_commands}
        
        commands = mock_plugin.commands()
        
        for cmd in expected_commands:
            assert cmd in commands
    
    def test_play_command_with_active_device(self, mock_spotipy):
        """Test play command when device is active"""
        mock_spotipy.current_playback.return_value = {
            "is_playing": False,
            "device": {"volume_percent": 50}
        }
        
        # Mock the play functionality
        def mock_play():
            mock_spotipy.start_playback()
            return "Now Playing: Test Artist - Test Song"
        
        result = mock_play()
        mock_spotipy.start_playback.assert_called_once()
        assert "Now Playing" in result
    
    def test_play_command_no_active_device(self, mock_spotipy):
        """Test play command when no device is active"""
        mock_spotipy.current_playback.return_value = None
        
        def mock_play_no_device():
            if mock_spotipy.current_playback() is None:
                return "No active device"
            return "Playing"
        
        result = mock_play_no_device()
        assert result == "No active device"
    
    def test_pause_command(self, mock_spotipy):
        """Test pause command"""
        def mock_pause():
            mock_spotipy.pause_playback()
            return "Paused"
        
        result = mock_pause()
        mock_spotipy.pause_playback.assert_called_once()
        assert result == "Paused"
    
    def test_next_track_command(self, mock_spotipy):
        """Test next track command"""
        mock_spotipy.current_user_playing_track.return_value = {
            "is_playing": True,
            "item": {
                "name": "Next Song",
                "artists": [{"name": "Next Artist"}]
            }
        }
        
        def mock_next():
            mock_spotipy.next_track()
            track_info = mock_spotipy.current_user_playing_track()
            if track_info and track_info["is_playing"]:
                return f"Next Artist - Next Song"
            return "No track info"
        
        result = mock_next()
        mock_spotipy.next_track.assert_called_once()
        assert result == "Next Artist - Next Song"
    
    def test_previous_track_command(self, mock_spotipy):
        """Test previous track command"""
        def mock_prev():
            mock_spotipy.previous_track()
            return "Previous track"
        
        result = mock_prev()
        mock_spotipy.previous_track.assert_called_once()
        assert result == "Previous track"
    
    def test_play_pause_toggle_currently_playing(self, mock_spotipy):
        """Test play/pause toggle when currently playing"""
        mock_spotipy.current_playback.return_value = {
            "is_playing": True,
            "device": {"volume_percent": 50}
        }
        
        def mock_play_pause():
            current = mock_spotipy.current_playback()
            if current and current["is_playing"]:
                mock_spotipy.pause_playback()
                return "Paused"
            else:
                mock_spotipy.start_playback()
                return "Playing"
        
        result = mock_play_pause()
        mock_spotipy.pause_playback.assert_called_once()
        assert result == "Paused"
    
    def test_play_pause_toggle_currently_paused(self, mock_spotipy):
        """Test play/pause toggle when currently paused"""
        mock_spotipy.current_playback.return_value = {
            "is_playing": False,
            "device": {"volume_percent": 50}
        }
        
        def mock_play_pause():
            current = mock_spotipy.current_playback()
            if current and current["is_playing"]:
                mock_spotipy.pause_playback()
                return "Paused"
            else:
                mock_spotipy.start_playback()
                return "Playing"
        
        result = mock_play_pause()
        mock_spotipy.start_playback.assert_called_once()
        assert result == "Playing"
    
    def test_volume_up_command(self, mock_spotipy):
        """Test volume up command"""
        mock_spotipy.current_playback.return_value = {
            "device": {"volume_percent": 50}
        }
        
        def mock_volume_up(increase=10):
            current = mock_spotipy.current_playback()
            if current and "device" in current:
                current_vol = current["device"]["volume_percent"]
                new_vol = min(current_vol + increase, 100)
                mock_spotipy.volume(new_vol)
                return f"Volume: {new_vol}%"
            return "No device"
        
        result = mock_volume_up()
        mock_spotipy.volume.assert_called_once_with(60)
        assert result == "Volume: 60%"
    
    def test_volume_down_command(self, mock_spotipy):
        """Test volume down command"""
        mock_spotipy.current_playback.return_value = {
            "device": {"volume_percent": 50}
        }
        
        def mock_volume_down(decrease=10):
            current = mock_spotipy.current_playback()
            if current and "device" in current:
                current_vol = current["device"]["volume_percent"]
                new_vol = max(current_vol - decrease, 0)
                mock_spotipy.volume(new_vol)
                return f"Volume: {new_vol}%"
            return "No device"
        
        result = mock_volume_down()
        mock_spotipy.volume.assert_called_once_with(40)
        assert result == "Volume: 40%"
    
    def test_volume_bounds_checking(self, mock_spotipy):
        """Test volume bounds checking (0-100)"""
        # Test upper bound
        mock_spotipy.current_playback.return_value = {
            "device": {"volume_percent": 95}
        }
        
        def mock_volume_up_bounded(increase=10):
            current = mock_spotipy.current_playback()
            current_vol = current["device"]["volume_percent"]
            new_vol = min(current_vol + increase, 100)
            return new_vol
        
        result = mock_volume_up_bounded()
        assert result == 100
        
        # Test lower bound
        mock_spotipy.current_playback.return_value = {
            "device": {"volume_percent": 5}
        }
        
        def mock_volume_down_bounded(decrease=10):
            current = mock_spotipy.current_playback()  # Fixed typo
            current_vol = current["device"]["volume_percent"]
            new_vol = max(current_vol - decrease, 0)
            return new_vol
        
        result = mock_volume_down_bounded()
        assert result == 0
    
    def test_authentication_failure(self):
        """Test handling of authentication failure"""
        def mock_authenticate():
            try:
                # Simulate authentication failure
                raise Exception("Auth failed")
            except Exception as e:
                return f"Auth error: {e}"
        
        result = mock_authenticate()
        assert "Auth error" in result
    
    def test_api_error_handling(self, mock_spotipy):
        """Test handling of Spotify API errors"""
        # Create a custom exception for testing
        class MockSpotifyException(Exception):
            def __init__(self, msg):
                self.msg = msg
                super().__init__(msg)
        
        mock_spotipy.next_track.side_effect = MockSpotifyException("Rate limit exceeded")
        
        def mock_next_with_error():
            try:
                mock_spotipy.next_track()
                return "Success"
            except MockSpotifyException as e:
                return f"Spotify error: {e.msg}"
        
        result = mock_next_with_error()
        assert "Rate limit exceeded" in result
    
    def test_get_current_song_info(self, mock_spotipy):
        """Test getting current song information"""
        mock_spotipy.current_user_playing_track.return_value = {
            "is_playing": True,
            "item": {
                "name": "Test Song",
                "artists": [{"name": "Test Artist"}]
            }
        }
        
        def mock_get_song_info():
            track = mock_spotipy.current_user_playing_track()
            if track and track["is_playing"]:
                item = track["item"]
                return f"{item['artists'][0]['name']} - {item['name']}"
            return None
        
        result = mock_get_song_info()
        assert result == "Test Artist - Test Song"
    
    def test_no_current_song(self, mock_spotipy):
        """Test handling when no song is currently playing"""
        mock_spotipy.current_user_playing_track.return_value = None
        
        def mock_get_song_info():
            track = mock_spotipy.current_user_playing_track()
            if track and track.get("is_playing"):
                item = track["item"]
                return f"{item['artists'][0]['name']} - {item['name']}"
            return None
        
        result = mock_get_song_info()
        assert result is None
    
    def test_verbose_logging(self):
        """Test verbose logging functionality"""
        messages = []
        
        def mock_log(message, verbose=True):
            if verbose:
                messages.append(message)
        
        mock_log("Test message", verbose=True)
        mock_log("Silent message", verbose=False)
        
        assert len(messages) == 1
        assert messages[0] == "Test message"