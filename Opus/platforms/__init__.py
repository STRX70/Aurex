from .Apple import AppleAPI
from .Carbon import CarbonAPI
from .Resso import RessoAPI
from .Soundcloud import SoundAPI
from .Spotify import SpotifyAPI
from .Telegram import TeleAPI
from .Youtube import YouTubeAPI
from .JioSavan import Saavn

class PlaTForms:
    def __init__(self):
        self.saavn = Saavn()
