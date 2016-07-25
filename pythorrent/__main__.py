#    This file is part of PYThorrent.
#
#    PYThorrent is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    PYThorrent is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with PYThorrent.  If not, see <http://www.gnu.org/licenses/>.

from .torrent import Torrent
from .config import load_config

import logging

from random import choice

from optparse import OptionParser

def get_args():
    parser = OptionParser()
    parser.add_option("-f", "--file", dest="file",
                      help="Torrent FILE", metavar="FILE")
    parser.add_option("-p", "--path", dest="path",
                      help="Where to save the torrent output")
    parser.add_option("--log", dest="log", help="Log level")
                      
    options, _ = parser.parse_args()
    
    auto_args(options)

    return options
    
def auto_args(options):
    """
    """
    level = getattr(logging, options.log.upper())
    logging.basicConfig(level=level)

if __name__ == "__main__":
    options = get_args()
    client = Torrent.from_path(options.file, options.path)
    client.run()
    
    
