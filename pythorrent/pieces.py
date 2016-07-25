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
from os import path

import logging

class Piece(object):
    FILE_NAME_TEMPLATE = "{hex}"
    @classmethod
    def from_path(cls, sha, path):
        """
        Used to open a piece if it exists on disk.
        :param sha: hashlib hash object representing the real sha1 of
            the piece.
        :param path: path as string to the file as it exists on disk.
        """
        return cls.from_file(sha,open(path))
        
    @classmethod
    def from_file(cls, sha, f):
        """
        Used to open a piece if it exists as a file object.
        :param sha: hashlib hash object representing the real sha1 of
            the piece.
        :param f: file object representing the piece.
        """
        return cls(sha, f.read())
    
    def __init__(self, sha, data=""):
        """
        This basic Piece object represents a Piece from a torrent, its
        actual hash, and the data associated with it. Data may not
        necesserily valid data, could be incomplete, or corrupt.
        :param sha: hashlib hash object representing the real sha1 of
            the piece.
        :param data: string of bytes of the data in the piece.
        """
        self.sha = sha
        self.data = data
        
    @property
    def hex(self):
        """
        sha1 of the data in the piece as a hex string.
        """
        return sha1(self.data).hexdigest()
        
    @property
    def digest(self):
        """
        sha1 of the data in the piece as a binary string.
        """
        return sha1(self.data).digest()
        
    @property
    def size(self):
        """
        A shortcut to find what is the next block in the piece that
        should be downloaded.
        Returns a number representing the size of the piece so far.
        """
        return len(self.data)
        
    @property
    def valid(self):
        """
        Returns whether the data in the piece is valid against the sha.
        If it is invalid you have several options, perhaps the piece is
        incomplete, or the whole thing has been downloaded but it's too
        big. Up to the client to make that call.
        """
        return self.sha == self.digest
        
    @property
    def file_name(self):
        return self.FILE_NAME_TEMPLATE.format(hex=self.hex)
        
    def piece_path(self, save_dir):
        """
        Generate a path for this piece to be saved to.
        :param save_dir: The base path for this file to be saved in to.
        """
        return path.join(save_dir, self.file_name)
        
    def save(self, f):
        """
        Store the data in this piece to the file object.
        :param f: File object to save in to.
        """
        f.write(self.data)
        
    def clear(self):
        """
        Empty out the data in this piece.
        """
        self.data = ""
        
    def __eq__(self, o):
        """
        Compare this piece to another piece to see if they're the same.
        :param o: The other piece to compare to.
        """
        return self.sha == o.sha
        
class PieceRemote(Piece):
    def __init__(self, sha, peer, have=False, *args, **kwargs):
        """
        Represents a piece at a peer. Data can be empty before it is
        downloaded.
        :param sha: hashlib hash object representing the real sha1 of
            the piece.
        :param peer: Peer object used to link back to the torrent if
            necessary.
        :param have:Whether the Peer has the this piece. True for has,
            False for does not have.
        """
        super(PieceRemote, self).__init__(sha, *args, **kwargs)
        self.peer = peer
        self.have = have
        
    def insert_block(self, index, data):
        """
        Insert a new block of data in to this piece at a specific
        location in the data string.
        :param index: The start byte to enter the data in to.
        """
        right_index = index+len(data) # Not sure this is right
        self.data = self.data[:index] + data + self.data[right_index:]
        
class PieceLocal(Piece):
    def __init__(self, sha, data=""):
        """
        Represents a piece known to this client.
        Availability can be used to count how many of this piece exist
        among the peers.
        :param sha: hashlib hash object representing the real sha1 of
            the piece.
        :param path: path as string to the file as it exists on disk.
        """
        super(PieceLocal, self).__init__(sha, "")
        self.availability = 0
        
    def load(self, piece_dir):
        """
        Load data for piece from disk if path to where pieces are stored
        is known.
        :param piece_dir: Path as string to where pieces are stored.
        """
        with open(self.piece_path(piece_dir), "rb") as f:
            self.data = f.read()
        
    def complete(self, piece):
        """
        Used to merge a PieceRemote back in to a local piece. Once a
        piece has been downloaded use this function to copy that data in
        to this object.
        :param piece: RemotePiece object with the data to copy.
        """
        self.data = str(piece.data)
