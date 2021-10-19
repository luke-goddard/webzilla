"""
____    __    ____  _______ .______    ________   __   __       __          ___      
\   \  /  \  /   / |   ____||   _  \  |       /  |  | |  |     |  |        /   \     
 \   \/    \/   /  |  |__   |  |_)  | `---/  /   |  | |  |     |  |       /  ^  \    
  \            /   |   __|  |   _  <     /  /    |  | |  |     |  |      /  /_\  \   
   \    /\    /    |  |____ |  |_)  |   /  /----.|  | |  `----.|  `----./  _____  \  
    \__/  \__/     |_______||______/   /________||__| |_______||_______/__/     \__\ 
"""

__title__ = "Webzilla"
__version__ = "0.0.1"
__author__ = "Luke Goddard"
__licence__ = "BSD 3-Clause"
__copyright__ = "Copyright 2021 Luke Goddard"

VERSION = __version__

from .spider import AsyncSpider

__all__ = [
    "__title__",
    "__version__",
    "__author__",
    "__licence__",
    "__copyright__",
    "VERSION",
    "AsyncSpider",
]
