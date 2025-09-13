from Opus.core.bot import Signal
from Opus.core.dir import dirr
from Opus.core.git import git
from Opus.core.userbot import Userbot
from Opus.misc import dbb, heroku

from .logging import LOGGER

dirr()
git()
dbb()
heroku()

app = Signal()
userbot = Userbot()



from .platforms import *
from .platforms import AppleAPI, CarbonAPI, SoundAPI, SpotifyAPI, RessoAPI, TeleAPI, YouTubeAPI, Saavn as PlaTForms

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
JioSavan = Saavn()


class PlaTForms:
    def __init__(self):
        self.apple = Apple()
        self.carbon = Carbon()
        self.saavn = Saavn()
        self.resso = Resso()
        self.soundcloud = SoundCloud()
        self.spotify = Spotify()
        self.telegram = Telegram()
        self.youtube = YouTube()

Platform = PlaTForms()

