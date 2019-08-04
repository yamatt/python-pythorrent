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

from hashlib import sha1
from random import choice, randint
import string
import socket
from struct import pack, unpack
from collections import OrderedDict
import os
from random import choice

from . import splice
from .peer_stores import store_from_url
from .peer import Peer, BitTorrentPeerException
from .pieces import PieceLocal
from . import BitTorrentException

import requests
from torrentool.bencode import Bencode
from bitstring import BitArray

import logging
            
class Torrent(object):
    PIECE = PieceLocal
    CLIENT_NAME = "pythorrent"
    CLIENT_ID = "PY"
    CLIENT_VERSION = "0001"
    CLIENT_ID_LENGTH = 20
    CHAR_LIST = string.ascii_letters + string.digits
    PIECE_DIR = "_pieces"
    PROTOCOL_ID = "BitTorrent protocol"
    RESERVED_AREA = "\x00"*8
    DEFAULT_PORT = 6881
    MAX_PEERS = 20
    TORRENT_CACHE_URL="https://torcache.net/torrent/" \
        "{info_hash_hex}.torrent"
        
    @classmethod
    def from_info_hash(cls, info_hash, save_path):
        """
        Takes an info hash of a torrent as a binary string and builds a
        torrent from it.
        :param info_hash: A hashlib hash object.
        :param save_path: A string path to where the torrent should be
            saved.
        """
        return cls.from_info_hash_hex(
            info_hash.encode("hex")
        )
        
    @classmethod
    def from_info_hash_sha(cls, info_hash_sha, save_path):
        """
        Takes an info hash of a torrent as a hashlib sha object and
        builds a torrent from it.
        :param info_hash_sha:A hashlib hashed object.
        :param save_path: A string path to where the torrent should be
            saved.
        """
        return cls.from_info_hash_hex(
            info_hash_sha.hexdigest()
        )
        
    @classmethod
    def from_info_hash_hex(cls, info_hash_hex, save_path):
        """
        Takes an info hash of a torrent as a string and builds a URL for
        it so it can be looked up.
        :param info_hash_hex: A hex encoded string of the torrent's info
            hash.
        :param save_path: A string path to where the torrent should be
            saved.
        """
        url = self.TORRENT_CACHE_URL.format(
            info_hash_sha.hexdigest()
        )
        return cls.from_url(url)
    
    @classmethod
    def from_url(cls, url, save_path):
        """
        Takes a torrent from a URL, downloads it and loads it.
        :param url: The URL to the torrent file
        :param save_path: A string path to where the torrent should be
            saved.
        """
        response = requests.get(url)
        if response.status_code < 200 or response.status_code >= 300:
            raise BitTorrentException("Torrent file not found at:" \
                "{url}".format(url=url)
            )
        return cls.from_string(response.content, save_path)
        
    @classmethod
    def from_path(cls, path, save_path):
        """
        Takes a torrent from a path and loads it.
        :param path: A path as string to the path torrent file.
        :param save_path: A string path to where the torrent should be
            saved.
        """
        return cls.from_torrent_dict(
            Bencode.read_file(path),
            save_path
        )
        
    @classmethod
    def from_string(cls, s, save_path):
        """
        Takes a torrent file as a string and loads it.
        :param s:
        :param save_path: A string path to where the torrent should be
            saved.
        """
        return cls.from_torrent_dict(
            Bencode.read_string(s),
            save_path
        )
        
    @classmethod
    def from_torrent_dict(cls, metainfo, save_path):
        """
        Takes a torrent metainfo dictionary object and processes it for
        use in this object.
        :param metainfo:
        :param save_path: A string path to where the torrent should be
            saved.
        """
        info = metainfo['info']
        files = OrderedDict()
        if 'files' in info:
            for f in info['files']:
                files[os.path.join(*f['path'])] = f['length']
        else:
            files[info['name']] = info['length']
            
        return cls(
            name=info['name'],
            announce_urls=map(
                lambda url : url, metainfo['announce-list']
            ),
            # Note that info_hash is generated here because torrentool
            # returns the info_hash as hex encoded, which is really not
            # useful in most situations
            info_hash=sha1(Bencode.encode(info)).digest(), 
            piece_length=info['piece length'],
            files=files,
            piece_hashes=splice(info['pieces'], 20),
            save_path=save_path
        )
        
    def __init__(
        self, name, announce_urls, info_hash, piece_length, files, \
        piece_hashes, save_path
    ):
        """
        Represent a Torrent file and handle downloading and saving.
        :param name: Name of the torrent
        :param announce_urls: a list of URLs to find DHTs or trackers.
            The scheme is used to identify what kind of announce it is.
            http/https for normal HTTP trackers
        :param info_hash:The binary encoded info hash.
        :param piece_length: the default length of all (except the last)
            piece
        :param files: A dictionary of all the files where the key is the
            name of the file and the value is the size.
        :param piece_hashes: A list of all piece hashes as strings
        :param save_path: A string path to where the torrent should be
            saved.
        """
        self.name = name
        self.announce_urls = announce_urls
        self.info_hash = info_hash
        self.piece_length = piece_length
        self.files = files
        self.piece_hashes = piece_hashes
        self.save_path = save_path
        
        self._peer_stores = None
        self._pieces = None
        self._peer_id = None
        
        self._peers = {}
        
    @property
    def handshake_message(self):
        """
        Generate the string used to declare the protocol when passing
        messages during handshake
        """
        return "".join([
            chr(len(self.PROTOCOL_ID)),
            self.PROTOCOL_ID,
            self.RESERVED_AREA,
            self.info_hash,
            self.peer_id
        ])
        
    @property
    def peer_id(self):
        """
        Generate the peer id so that it is possible to identify other
        clients, and identify if you've connected to your own client
        """
        if self._peer_id is None:
            known_id = "-{id_}{version}-".format(
                id_=self.CLIENT_ID,
                version=self.CLIENT_VERSION,
            )
            remaining_length = self.CLIENT_ID_LENGTH - len(known_id)
            gubbins = "".join(
                [ choice(self.CHAR_LIST) for _ in range(remaining_length) ]
            )
            self._peer_id = known_id + gubbins
        return self._peer_id
        
    @property
    def port(self):
        """
        External port being used for incoming connections
        """
        return self.DEFAULT_PORT
        
    @property
    def peer_stores(self):
        """
        Returns a list of all the peer stores set up
        """
        if self._peer_stores is None:
            self._peer_stores = {}
            for url in self.announce_urls:
                self._peer_stores[url] = store_from_url(url)(url, self)
        return self._peer_stores
    
    @property
    def total_size(self):
        """
        The size of all the files
        """
        return sum(self.files.values())
        
    @property
    def downloaded(self):
        """
        Calculate the size of all the pieces that have been downloaded
        so far
        """
        return sum(map(
            lambda piece: self.piece_length if piece.valid else 0,
            self.pieces.values()
        ))
        
    @property
    def uploaded(self):
        # TODO
        return 0
    
    @property
    def remaining(self):
        """
        Calculates how much is left
        """
        return self.total_size - self.downloaded
        
    @property
    def complete(self):
        """
        Checks if all pieces have downloaded
        """
        return not any(map(lambda piece: not piece.valid,
            self.pieces.values()
        ))
        
    @property
    def peers(self):
        """
        A list of peers that gets updated when necessary
        """
        for peer_store in self.peer_stores.values():
            self._peers.update(peer_store.peers)
        return self._peers
            
    @property
    def pieces(self):
        """
        Map the pieces from the torrent file to memory.
        """
        if self._pieces is None:
            self._pieces = OrderedDict()
            for hash_index in range(len(self.piece_hashes)):
                piece_hash = self.piece_hashes[hash_index]
                piece = self.PIECE(piece_hash, hash_index)
                piece_path = piece.piece_path(self.piece_directory)
                if os.path.isfile(piece_path):
                    logging.info("Piece found on disk: {0}".format(
                        piece_path
                    ))
                    piece.load(piece_path)
                    if not piece.valid:
                        raise Exception("Not valid")
                        logging.warning("Piece on disk not valid. " \
                            "Clearing."
                        )
                        piece.clear()
                self._pieces[piece_hash] = piece
        return self._pieces
    
    @property
    def save_directory(self):
        """
        Return path for where the files should go.
        """
        return os.path.join(self.save_path, self.name)
    
    @property
    def piece_directory(self):
        """
        Return path for where pieces should go.
        """
        return os.path.join(self.save_directory, self.PIECE_DIR)
        
    def run(self):
        """
        Just download the torrent. No messing.
        """
        self.create_directory()
        while True:
            try:
                for peer in self.peers.values()[:self.MAX_PEERS]:
                    if peer.status == peer.ESTATUS.NOT_STARTED or \
                        peer.status == peer.ESTATUS.CLOSED:
                        peer.run()
                        logging.info("Handshake OK. Client ID: " \
                            "{client}".format(
                                client = peer.client
                            )
                        )
                        peer.handle_message() # should be bitfield
                
                # not a smart way to select pieces
                piece = choice(filter(
                    lambda piece: not piece.valid, self.pieces.values()
                ))
                logging.info("Piece {sha} selected".format(
                    sha=piece.hex
                ))
                peer = choice(filter(
                    lambda peer:
                        peer.pieces[piece.sha].have and not \
                        peer.status == peer.ESTATUS.CHOKE,
                        self.peers.values()
                ))
                logging.info("Peer {host} selected".format(
                    host=peer.hostport[0]
                ))
                piece.complete(peer.acquire(piece))
                piece_path = piece.piece_path(self.piece_directory)
                logging.info("Piece complete. Saving to: {0}".format(
                    piece_path
                ))
                with open(piece_path, "wb") as f:
                    piece.save(f)
                    

                if self.complete:
                    self.split_out()
                    
                self.advertise_piece(piece)
                
            except BitTorrentPeerException as e:
                logging.warning("Peer {host} disconnected".format(
                    host=peer.hostport[0]
                ))
                logging.debug("Disconnected because: {e}".format(e=e))
            self.clean_peers()
                
    def advertise_piece(self, piece):
        """
        For all peers let them know I now have this piece.
        :param piece: `class Piece` object
        """
        index = self.pieces.values().index(piece)
        for peer in self.peers.values():
            if peer.status == peer.ESTATUS.OK:
                peer.send_have(index)
                
    def split_out(self):
        """
        For all the files in the torrent, get the pieces and create the
        files.
        """
        extra_data = ""
        for file_name, size in self.files.items():
            size_count = 0
            file_path = os.path.join(
                self.save_directory,
                file_name
            )
            self.make_file_path(file_path)
            with open(file_path, "wb") as f:
                f.write(extra_data) # if any
                for piece in self.pieces:
                    size_count += len(piece.data)
                    if size_count > size:
                        overrun = size_count - size
                        data = piece.data[:overrun]
                        extra_data = piece.data[overrun:]
                    else:
                        data = piece.data
                    
    def make_file_path(self, file_path):
        """
        Create any necessary sub directories for torrent files
        :path file_path: directory to make
        """
        file_dir = os.path.dirname(file_path)
        if file_dir is not "" and not os.path.exists(file_dir):
            os.makedirs(file_dir)
        
    def create_directory(self):
        """
        Create directory for files to be saved in
        """
        if not self.save_directory.startswith(self.save_path):
            raise RuntimeError(
                "Torrent name innappropriately naviages directories. " \
                "Resulting path: {0}".format(path)
            )
        if not os.path.isdir(self.save_directory):
            try:
                os.mkdir(self.save_directory)
            except OSError as e:
                raise BitTorrentException("Cannot create path '{0}'. " \
                    "Does base path exist?".format(e))
        
        if not os.path.isdir(self.piece_directory):
            os.mkdir(self.piece_directory)
            
    def clean_peers(self):
        """
        Look for any peers in `self.peers` that have had their
        connections closed and remove them from the peer list.
        """
        for k, peer in self.peers.items():
            if peer.status == peer.ESTATUS.CLOSED:
                del self._peers[k]
            
            
class TorrentClient(object):
    def __init__(self, save_path, torrents=[]):
        self.save_path = save_path
        self.torrents = []
        
    def add_torrent(self, torrent_path):
        self.torrents.append(Torrent.from_path(
            torrent_path,
            self.save_path
        ))

