import logging
import click
import coloredlogs

from webzilla import spider

logger = logging.getLogger(__name__)


def ascii():
    # fmt: off
    print("____    __    ____  _______ .______    ________   __   __       __          ___      ")
    print("\\   \\  /  \\  /   / |   ____||   _  \\  |       /  |  | |  |     |  |        /   \\     ")
    print(" \\   \\/    \\/   /  |  |__   |  |_)  | `---/  /   |  | |  |     |  |       /  ^  \\    ")
    print("  \\            /   |   __|  |   _  <     /  /    |  | |  |     |  |      /  /_\\  \\   ")
    print("   \\    /\\    /    |  |____ |  |_)  |   /  /----.|  | |  `----.|  `----./  _____  \\  ")
    print("    \\__/  \\__/     |_______||______/   /________||__| |_______||_______/__/     \\__\\ \n")
    # fmt: on


# def setup_cmdline_logging(args: GeneralArguments):
def setup_cmdline_logging(verbose=False):
    lvl = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s %(levelname)s %(filename)s:%(lineno)s %(message)s"
    coloredlogs.install(fmt=fmt, level=lvl)
    logging.getLogger("chardet").propagate = False
    logging.getLogger("chardet").disabled = True
    logging.getLogger("bs4").propagate = False
    logging.getLogger("bs4").disabled = True
    logging.getLogger("bs4.dammit").propagate = False
    logging.getLogger("bs4.dammit").disabled = True


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="verbose mode")
def cli(verbose=False):
    setup_cmdline_logging(verbose=verbose)
    logger.debug("Setup logging")


@click.command("spider")
@click.argument("url")
@click.option("--workers", "-w", type=int, help="Number of async workers in the pool")
@click.option(
    "--output",
    "-o",
    type=click.File(mode="w", lazy=False),
    default="/tmp/spider.log",
    help="Save crawled URLs to disk",
    show_default=True,
)
def spider_handler(url, workers=50, output=None):
    print(output)
    logger.debug(url)
    spider.spawn_cmdline_spider(url, workers=workers, output=output)
    logger.info("Finsihed crawling")


if __name__ == "__main__":
    try:
        cli.add_command(spider_handler)
        cli()
    except KeyboardInterrupt:
        logger.warning("Shutting down")
