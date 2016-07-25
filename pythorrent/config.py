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

import yaml

import logging

class Config(object):
    @classmethod
    def from_path(cls, path):
        """
        """
        return cls.from_file(
            open(path)
        )
    
    @classmethod
    def from_file(cls, f):
        """
        """
        return cls(
            yaml.safe_load(f)
        )
        
    def __init__(self, config):
        """
        """
        self._config = config
        
    def __getitem__(self, key):
        """
        """
        return self._config.get(key)
        
    def __getattribute__(self, attr):
        """
        """
        return self[attr]

def load_config(opts):
    """
    """
    return Config.from_path(opts)
