"""webzilla

Usage:
    webzilla spider <url> [-dp]

Options:
    -d --debug          Show extra logs
    -p --progress-bar   Show progress bar
"""

import logging

from dataclasses import dataclass

from docopt import docopt

import coloredlogs

import webzilla

logger = logging.getLogger(__name__)


@dataclass
class GeneralArguments:
    debug: bool = False


def ascii():
    # fmt: off
    print("____    __    ____  _______ .______    ________   __   __       __          ___      ")
    print("\   \  /  \  /   / |   ____||   _  \  |       /  |  | |  |     |  |        /   \     ")
    print(" \   \/    \/   /  |  |__   |  |_)  | `---/  /   |  | |  |     |  |       /  ^  \    ")
    print("  \            /   |   __|  |   _  <     /  /    |  | |  |     |  |      /  /_\  \   ")
    print("   \    /\    /    |  |____ |  |_)  |   /  /----.|  | |  `----.|  `----./  _____  \  ")
    print("    \__/  \__/     |_______||______/   /________||__| |_______||_______/__/     \__\ \n")
    # fmt: on


def setup_cmdline_logging(args: GeneralArguments):
    lvl = logging.DEBUG if args.debug else logging.INFO
    fmt = "%(asctime)s %(levelname)s %(message)s"
    coloredlogs.install(fmt=fmt, level=lvl)
    # logging.basicConfig(level=lvl)


def handle_cmdline(arguments):
    genral_options = GeneralArguments(debug=arguments["--debug"])
    setup_cmdline_logging(genral_options)
    if arguments["spider"]:
        args = webzilla.spider.SpiderDocoptArgs(
            url=arguments["<url>"], progress=arguments["--progress-bar"]
        )
        return webzilla.spider.spawn_cmdline_spider(args)


if __name__ == "__main__":
    ascii()
    arguments = docopt(__doc__, version=webzilla.__version__)
    try:
        handle_cmdline(arguments)
    except KeyboardInterrupt:
        pass
