import platform
from pathlib import Path
from typing import List, Optional, Dict, ClassVar

from django.conf import settings

# Depends on other PyPI/vendor packages:
from pydantic import InstanceOf, Field
from pydantic_pkgr import (
    BinProvider,
    BinName,
    BinProviderName,
    ProviderLookupDict,
    InstallArgs,
    PATHStr,
    HostBinPath,
)

import archivebox

# Depends on other Django apps:
from plugantic.base_plugin import BasePlugin
from plugantic.base_configset import BaseConfigSet
from plugantic.base_binary import BaseBinary, BaseBinProvider, env
# from plugantic.base_extractor import BaseExtractor
# from plugantic.base_queue import BaseQueue
from plugantic.base_hook import BaseHook

# Depends on Other Plugins:
from plugins_pkg.npm.apps import LIB_NPM_BINPROVIDER, SYS_NPM_BINPROVIDER


###################### Config ##########################


class PuppeteerConfigs(BaseConfigSet):
    # section: ConfigSectionName = 'DEPENDENCY_CONFIG'

    # PUPPETEER_BINARY: str = Field(default='wget')
    # PUPPETEER_ARGS: Optional[List[str]] = Field(default=None)
    # PUPPETEER_EXTRA_ARGS: List[str] = []
    # PUPPETEER_DEFAULT_ARGS: List[str] = ['--timeout={TIMEOUT-10}']
    pass


PUPPETEER_CONFIG = PuppeteerConfigs()

LIB_DIR_BROWSERS = archivebox.CONSTANTS.LIB_BROWSERS_DIR


class PuppeteerBinary(BaseBinary):
    name: BinName = "puppeteer"

    binproviders_supported: List[InstanceOf[BinProvider]] = [LIB_NPM_BINPROVIDER, SYS_NPM_BINPROVIDER, env]


PUPPETEER_BINARY = PuppeteerBinary()


class PuppeteerBinProvider(BaseBinProvider):
    name: BinProviderName = "puppeteer"
    INSTALLER_BIN: BinName = "npx"

    PATH: PATHStr = str(archivebox.CONSTANTS.LIB_BIN_DIR)

    puppeteer_browsers_dir: Optional[Path] = LIB_DIR_BROWSERS
    puppeteer_install_args: List[str] = ["@puppeteer/browsers", "install", "--path", str(LIB_DIR_BROWSERS)]

    packages_handler: ProviderLookupDict = Field(default={
        "chrome": lambda:
            ['chrome@stable'],
    }, exclude=True)
    
    _browser_abspaths: ClassVar[Dict[str, HostBinPath]] = {}
    
    def setup(self) -> None:
        assert SYS_NPM_BINPROVIDER.INSTALLER_BIN_ABSPATH, "NPM bin provider not initialized"
        
        if self.puppeteer_browsers_dir:
            self.puppeteer_browsers_dir.mkdir(parents=True, exist_ok=True)
    
    def installed_browser_bins(self, browser_name: str='*') -> List[Path]:
        # if on macOS, browser binary is inside a .app, otherwise it's just a plain binary
        if platform.system().lower() == 'darwin':
            # /data/lib/browsers/chrome/mac_arm-129.0.6668.58/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
            return sorted(self.puppeteer_browsers_dir.glob(f'{browser_name}/mac*/chrome*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'))

        # /data/lib/browsers/chrome/linux-131.0.6730.0/chrome-linux64/chrome
        return sorted(self.puppeteer_browsers_dir.glob(f"{browser_name}/linux*/chrome*/chrome"))

    def on_get_abspath(self, bin_name: BinName, **context) -> Optional[HostBinPath]:
        assert bin_name == 'chrome', 'Only chrome is supported using the @puppeteer/browsers install method currently.'
        
        # already loaded, return abspath from cache
        if bin_name in self._browser_abspaths:
            return self._browser_abspaths[bin_name]
        
        # first time loading, find browser in self.puppeteer_browsers_dir by searching filesystem for installed binaries
        matching_bins = [abspath for abspath in self.installed_browser_bins() if bin_name in str(abspath)]
        if matching_bins:
            newest_bin = matching_bins[-1]  # already sorted alphabetically, last should theoretically be highest version number
            self._browser_abspaths[bin_name] = newest_bin
            return self._browser_abspaths[bin_name]
        
        return None

    def on_install(self, bin_name: str, packages: Optional[InstallArgs] = None, **context) -> str:
        """npx @puppeteer/browsers install chrome@stable"""
        self.setup()
        assert bin_name == 'chrome', 'Only chrome is supported using the @puppeteer/browsers install method currently.'

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
        output_info = proc.stdout.strip().split('\n')[-1]
        browser_abspath = output_info.split(' ', 1)[-1]
        # browser_version = output_info.split('@', 1)[-1].split(' ', 1)[0]
        
        self._browser_abspaths[bin_name] = Path(browser_abspath)

        return proc.stderr.strip() + "\n" + proc.stdout.strip()

PUPPETEER_BINPROVIDER = PuppeteerBinProvider()


# ALTERNATIVE INSTALL METHOD using Ansible:
# install_playbook = self.plugin_dir / 'install_puppeteer.yml'
# chrome_bin = run_playbook(install_playbook, data_dir=archivebox.DATA_DIR, quiet=quiet).BINARIES.chrome
# return self.__class__.model_validate(
#     {
#         **self.model_dump(),
#         "loaded_abspath": chrome_bin.symlink,
#         "loaded_version": chrome_bin.version,
#         "loaded_binprovider": env,
#         "binproviders_supported": self.binproviders_supported,
#     }
# )


class PuppeteerPlugin(BasePlugin):
    app_label: str ='puppeteer'
    verbose_name: str = 'Puppeteer (NPM)'

    hooks: List[InstanceOf[BaseHook]] = [
        PUPPETEER_CONFIG,
        PUPPETEER_BINPROVIDER,
        PUPPETEER_BINARY,
    ]



PLUGIN = PuppeteerPlugin()
# PLUGIN.register(settings)
DJANGO_APP = PLUGIN.AppConfig
