import sys
from typing import List, Dict, ClassVar
from subprocess import run, PIPE

from pydantic import InstanceOf, Field, model_validator, AliasChoices

from django.conf import settings

from pydantic_pkgr import BinProvider, BinName, BinProviderName, ProviderLookupDict
from plugantic.base_plugin import BasePlugin
from plugantic.base_configset import BaseConfigSet, ConfigSectionName
from plugantic.base_binary import BaseBinary, env, apt, brew
from plugantic.base_hook import BaseHook

from plugins_sys.config.apps import ARCHIVING_CONFIG
from plugins_pkg.pip.apps import pip

###################### Config ##########################


class YtdlpConfig(BaseConfigSet):
    section: ClassVar[ConfigSectionName] = "DEPENDENCY_CONFIG"

    USE_YTDLP: bool               = Field(default=True, validation_alias=AliasChoices('USE_YOUTUBEDL', 'SAVE_MEDIA'))

    YTDLP_BINARY: str             = Field(default='yt-dlp', alias='YOUTUBEDL_BINARY')
    YTDLP_EXTRA_ARGS: List[str]   = Field(default=[], alias='YOUTUBEDL_EXTRA_ARGS')
    
    YTDLP_CHECK_SSL_VALIDITY: bool = Field(default=lambda: ARCHIVING_CONFIG.CHECK_SSL_VALIDITY)
    YTDLP_TIMEOUT: int             = Field(default=lambda: ARCHIVING_CONFIG.MEDIA_TIMEOUT)
    
    @model_validator(mode='after')
    def validate_use_ytdlp(self):
        if self.USE_YTDLP and self.YTDLP_TIMEOUT < 20:
            print(f'[red][!] Warning: MEDIA_TIMEOUT is set too low! (currently set to MEDIA_TIMEOUT={self.YTDLP_TIMEOUT} seconds)[/red]', file=sys.stderr)
            print('    youtube-dl/yt-dlp will fail to archive any media if set to less than ~20 seconds.', file=sys.stderr)
            print('    (Setting it somewhere over 60 seconds is recommended)', file=sys.stderr)
            print(file=sys.stderr)
            print('    If you want to disable media archiving entirely, set SAVE_MEDIA=False instead:', file=sys.stderr)
            print('        https://github.com/ArchiveBox/ArchiveBox/wiki/Configuration#save_media', file=sys.stderr)
            print(file=sys.stderr)
        return self


YTDLP_CONFIG = YtdlpConfig()



class YtdlpBinary(BaseBinary):
    name: BinName = YTDLP_CONFIG.YTDLP_BINARY
    binproviders_supported: List[InstanceOf[BinProvider]] = [pip, apt, brew, env]

YTDLP_BINARY = YtdlpBinary()


class FfmpegBinary(BaseBinary):
    name: BinName = 'ffmpeg'
    binproviders_supported: List[InstanceOf[BinProvider]] = [apt, brew, env]

    provider_overrides: Dict[BinProviderName, ProviderLookupDict] = {
        'env': {
            # 'abspath': lambda: shutil.which('ffmpeg', PATH=env.PATH),
            # 'version': lambda: run(['ffmpeg', '-version'], stdout=PIPE, stderr=PIPE, text=True).stdout,
        },
        'apt': {
            # 'abspath': lambda: shutil.which('ffmpeg', PATH=apt.PATH),
            'version': lambda: run(['apt', 'show', 'ffmpeg'], stdout=PIPE, stderr=PIPE, text=True).stdout,
        },
        'brew': {
            # 'abspath': lambda: shutil.which('ffmpeg', PATH=brew.PATH),
            'version': lambda: run(['brew', 'info', 'ffmpeg', '--quiet'], stdout=PIPE, stderr=PIPE, text=True).stdout,
        },
    }

    # def get_ffmpeg_version(self) -> Optional[str]:
    #     return self.exec(cmd=['-version']).stdout

FFMPEG_BINARY = FfmpegBinary()


# class YtdlpExtractor(BaseExtractor):
#     name: str = 'ytdlp'
#     binary: str = 'ytdlp'



class YtdlpPlugin(BasePlugin):
    app_label: str = 'ytdlp'
    verbose_name: str = 'YT-DLP'
    docs_url: str = 'https://github.com/yt-dlp/yt-dlp'

    hooks: List[InstanceOf[BaseHook]] = [
        YTDLP_CONFIG,
        YTDLP_BINARY,
        FFMPEG_BINARY,
    ]


PLUGIN = YtdlpPlugin()
# PLUGIN.register(settings)
DJANGO_APP = PLUGIN.AppConfig
