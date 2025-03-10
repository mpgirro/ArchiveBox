import platform
from pathlib import Path
from typing import List, Optional, Dict, ClassVar

from django.conf import settings

# Depends on other PyPI/vendor packages:
from pydantic import InstanceOf, computed_field, Field
from pydantic_pkgr import (
    BinName,
    BinProvider,
    BinProviderName,
    ProviderLookupDict,
    InstallArgs,
    PATHStr,
    HostBinPath,
    bin_abspath,
    OPERATING_SYSTEM,
    DEFAULT_ENV_PATH,
)

import archivebox

# Depends on other Django apps:
from plugantic.base_plugin import BasePlugin
from plugantic.base_configset import BaseConfigSet
from plugantic.base_binary import BaseBinary, BaseBinProvider, env
# from plugantic.base_extractor import BaseExtractor
# from plugantic.base_queue import BaseQueue
from plugantic.base_hook import BaseHook

from plugins_pkg.pip.apps import SYS_PIP_BINPROVIDER, VENV_PIP_BINPROVIDER, LIB_PIP_BINPROVIDER


###################### Config ##########################


class PlaywrightConfigs(BaseConfigSet):
    # section: ConfigSectionName = 'DEPENDENCY_CONFIG'

    # PLAYWRIGHT_BINARY: str = Field(default='wget')
    # PLAYWRIGHT_ARGS: Optional[List[str]] = Field(default=None)
    # PLAYWRIGHT_EXTRA_ARGS: List[str] = []
    # PLAYWRIGHT_DEFAULT_ARGS: List[str] = ['--timeout={TIMEOUT-10}']
    pass


PLAYWRIGHT_CONFIG = PlaywrightConfigs()

LIB_DIR_BROWSERS = archivebox.CONSTANTS.LIB_BROWSERS_DIR



class PlaywrightBinary(BaseBinary):
    name: BinName = "playwright"

    binproviders_supported: List[InstanceOf[BinProvider]] = [LIB_PIP_BINPROVIDER, VENV_PIP_BINPROVIDER, SYS_PIP_BINPROVIDER, env]
    


PLAYWRIGHT_BINARY = PlaywrightBinary()


class PlaywrightBinProvider(BaseBinProvider):
    name: BinProviderName = "playwright"
    INSTALLER_BIN: BinName = PLAYWRIGHT_BINARY.name

    PATH: PATHStr = f"{archivebox.CONSTANTS.LIB_BIN_DIR}:{DEFAULT_ENV_PATH}"

    puppeteer_browsers_dir: Optional[Path] = (
        Path("~/Library/Caches/ms-playwright").expanduser()      # macos playwright cache dir
        if OPERATING_SYSTEM == "darwin" else
        Path("~/.cache/ms-playwright").expanduser()              # linux playwright cache dir
    )
    puppeteer_install_args: List[str] = ["install"]              # --with-deps

    packages_handler: ProviderLookupDict = Field(default={
        "chrome": lambda: ["chromium"],
    }, exclude=True)

    _browser_abspaths: ClassVar[Dict[str, HostBinPath]] = {}

    @computed_field
    @property
    def INSTALLER_BIN_ABSPATH(self) -> HostBinPath | None:
        return PLAYWRIGHT_BINARY.load().abspath

    def setup(self) -> None:
        assert SYS_PIP_BINPROVIDER.INSTALLER_BIN_ABSPATH, "Pip bin provider not initialized"

        if self.puppeteer_browsers_dir:
            self.puppeteer_browsers_dir.mkdir(parents=True, exist_ok=True)

    def installed_browser_bins(self, browser_name: str = "*") -> List[Path]:
        if browser_name == 'chrome':
            browser_name = 'chromium'
        
        # if on macOS, browser binary is inside a .app, otherwise it's just a plain binary
        if platform.system().lower() == "darwin":
            # ~/Library/caches/ms-playwright/chromium-1097/chrome-mac/Chromium.app/Contents/MacOS/Chromium
            return sorted(
                self.puppeteer_browsers_dir.glob(
                    f"{browser_name}-*/*-mac*/*.app/Contents/MacOS/*"
                )
            )

        # ~/Library/caches/ms-playwright/chromium-1097/chrome-linux/chromium
        return sorted(self.puppeteer_browsers_dir.glob(f"{browser_name}-*/*-linux/*"))

    def on_get_abspath(self, bin_name: BinName, **context) -> Optional[HostBinPath]:
        assert bin_name == "chrome", "Only chrome is supported using the @puppeteer/browsers install method currently."

        # already loaded, return abspath from cache
        if bin_name in self._browser_abspaths:
            return self._browser_abspaths[bin_name]

        # first time loading, find browser in self.puppeteer_browsers_dir by searching filesystem for installed binaries
        matching_bins = [abspath for abspath in self.installed_browser_bins() if bin_name in str(abspath)]
        if matching_bins:
            newest_bin = matching_bins[-1]  # already sorted alphabetically, last should theoretically be highest version number
            self._browser_abspaths[bin_name] = newest_bin
            return self._browser_abspaths[bin_name]
        
        # playwright sometimes installs google-chrome-stable via apt into system $PATH, check there as well
        abspath = bin_abspath('google-chrome-stable', PATH=env.PATH)
        if abspath:
            self._browser_abspaths[bin_name] = abspath
            return self._browser_abspaths[bin_name]

        return None

    def on_install(self, bin_name: str, packages: Optional[InstallArgs] = None, **context) -> str:
        """playwright install chrome"""
        self.setup()
        assert bin_name == "chrome", "Only chrome is supported using the playwright install method currently."

        if not self.INSTALLER_BIN_ABSPATH:
            raise Exception(
                f"{self.__class__.__name__} install method is not available on this host ({self.INSTALLER_BIN} not found in $PATH)"
            )
        packages = packages or self.on_get_packages(bin_name)

        # print(f'[*] {self.__class__.__name__}: Installing {bin_name}: {self.INSTALLER_BIN_ABSPATH} install {packages}')

        install_args = [*self.puppeteer_install_args]

        proc = self.exec(bin_name=self.INSTALLER_BIN_ABSPATH, cmd=[*install_args, *packages])

        if proc.returncode != 0:
            print(proc.stdout.strip())
            print(proc.stderr.strip())
            raise Exception(f"{self.__class__.__name__}: install got returncode {proc.returncode} while installing {packages}: {packages}")

        # chrome@129.0.6668.58 /data/lib/browsers/chrome/mac_arm-129.0.6668.58/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
        output_info = proc.stdout.strip().split("\n")[-1]
        browser_abspath = output_info.split(" ", 1)[-1]
        # browser_version = output_info.split('@', 1)[-1].split(' ', 1)[0]

        self._browser_abspaths[bin_name] = Path(browser_abspath)

        return proc.stderr.strip() + "\n" + proc.stdout.strip()

PLAYWRIGHT_BINPROVIDER = PlaywrightBinProvider()



class PlaywrightPlugin(BasePlugin):
    app_label: str = 'playwright'
    verbose_name: str = 'Playwright (PIP)'

    hooks: List[InstanceOf[BaseHook]] = [
        PLAYWRIGHT_CONFIG,
        PLAYWRIGHT_BINPROVIDER,
        PLAYWRIGHT_BINARY,
    ]



PLUGIN = PlaywrightPlugin()
# PLUGIN.register(settings)
DJANGO_APP = PLUGIN.AppConfig
