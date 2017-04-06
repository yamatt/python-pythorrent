# PYTHorrent
This is a BitTorrent client written entirely in Python so that it can be easily used for experiments. It is a fully working BitTorrent client so you can use it below as an example. There is no intelligence in this such as getting rarest peice first. Everything is random.

It doesn't use `thread` or `multiprocessing` as it's designed to be used for experiments, and I don't know how someone may want to use it, while also making it impractical for general use, but I'd like to eventually support the most common schemes such as DHT, Magnet URLs, PHE tDP, and UPnP so it is possible to accept incoming connections.

## Installation
### PIP

    pip install pythorrent
    
### From Source

    pip install -r requirements.txt
    python setup.py install

## Usage
Depending on how you installed PYTHorrent you may need to go to the root of the source of the PYTHorrent directory.

    cd python-pythorrent

### Getting commands

    python -m pythorrent -h

### Downloading a Torrent using a torrent file

    python -m pythorrent --file ubuntu-16.04-desktop-amd64.iso.torrent --path . --log=info

## Overview
Documentation for the BitTorrent protocol is poor but these sources have been immensely helpful:

- http://jonas.nitro.dk/bittorrent/bittorrent-rfc.html
- https://wiki.theory.org/BitTorrentSpecification
- http://www.kristenwidman.com/blog/33/how-to-write-a-bittorrent-client-part-1/
- http://www.kristenwidman.com/blog/71/how-to-write-a-bittorrent-client-part-2/

## License
### AGPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

## To Do
### Tidy up documentation
### Memory efficiency
- Only load piece data in to memory when it is needed.

### Magnet URL Scheme
- https://en.wikipedia.org/wiki/Magnet_URI_scheme

### DHT
Options?
- https://github.com/drxzcl/lightdht/
    - I like this one best
    - Seems to lock out when finding peers
- https://github.com/gsko/mdht

### Encryption? PHE
- https://wiki.vuze.com/w/Message_Stream_Encryption

### UPnP
- https://code.google.com/archive/p/miranda-upnp/
    - Entirely Python code
- http://www.gniibe.org/memo/system/dynamic-ip/upnp.html
    - Has dependency on GNUPnP
- https://github.com/miniupnp/miniupnp


** **Always download legal torrents** **
