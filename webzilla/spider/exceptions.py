class SkipUrlException(Exception):
    """
    This exception is raised when a user defined condition is
    raised that tells the crawler not to crawl the current URL
    """
