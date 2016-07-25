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

from datetime import timedelta, datetime
from struct import unpack, pack
import socket
from collections import OrderedDict

from bitstring import BitArray

from .pieces import PieceRemote
from . import BitTorrentException

import logging

class BitTorrentPeerException(BitTorrentException):
    pass

class Peer(object):
    PIECE = PieceRemote
    CONNECTION_TIMEOUT = 10
    BLOCK_SIZE = pow(2,14)
    class ESTATUS:
        """
        Connection status.
        """
        BAD = -3
        NOT_STARTED = -2
        CLOSED = -1
        CHOKE = 0
        OK = 1
    
    def __init__(self, hostport, torrent):
        """
        Represents the peer you're connected to.
        :param hostport: tuple containing IP and port of remote client
        :param torrent: Torrent object representing what is being
            downloaded.
        """
        self.hostport = hostport
        self.torrent = torrent
        self.status = self.ESTATUS.NOT_STARTED
        self.reserved = None
        self.info_hash = None
        self.peer_id = None
        self._pieces = None
        self.uploaded = 0
        self.buff = ""
        
    @property
    def client(self):
        """
        Quick and dirty check to find the name of the peer's client
        """
        return self.peer_id[1:7]
        
    @property
    def pieces(self):
        """
        Return all the peices associated with this torrent but from the
        peer's perspective.
        Returns list of RemotePiece
        """
        if self._pieces is None:
            self._pieces = OrderedDict()
            for torrent_piece in self.torrent.pieces.values():
                peer_piece = self.PIECE(
                    torrent_piece.sha,
                    self
                )
                self._pieces[peer_piece.sha] = peer_piece
        return self._pieces
        
    def run(self):
        """
        Get everything in place to talk to peer
        """
        self.setup()
        self.handshake()
        self.recv_handshake()
        
    def setup(self):
        """
        Open socket with peer
        """
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.settimeout(self.CONNECTION_TIMEOUT)
        try:
            self.conn.connect(self.hostport)
        except socket.error:
            self.close()
            raise BitTorrentPeerException(
                "Could not connect to peer: {0}".format(self.hostport)
            )
        self.status = self.ESTATUS.OK
            
    def close(self):
        """
        Central closing function
        """
        self.status = self.ESTATUS.CLOSED
        self.conn.close()
            
    def bad(self):
        """
        Like the close function but marks this peer as a bad peer so
        that the connection does not get reopened.
        """
        self.conn.close()
        self.status = self.ESTATUS.BAD
        
    def send(self, message):
        """
        Send a byte string to the peer.
        :param message: Binary string of bytes to send
        """
        try:
            self.conn.sendall(message)
        except socket.error as e:
            self.close()
            raise BitTorrentPeerException(
                "Connection closed by peer when sending"
            )
        
    def recv(self, length):
        """
        Grab custom lengths of data rather than binary divisible, or
        find that we didn't get all of it.
        Possibly not best practice but wanted a central place to do it.
        
        :param length: Integer for much to receive and recieve from the
                       socket.
        """
        buff = ""
        remaining = length
            
        while len(buff) < length:
            try:
                if remaining > 4096:
                    recvd = self.conn.recv(4096)
                else:
                    recvd = self.conn.recv(remaining)
            except socket.error as e:
                self.close()
                raise BitTorrentPeerException(
                    "Connection closed by peer when receiving"
                )
            if not recvd:
                raise BitTorrentPeerException("Received {0} {1}".format(
                    len(buff), remaining
                ))
            buff += recvd
            remaining -= len(recvd)
        return buff
        
    # HANDSHAKE
        
    def handshake(self):
        """
        Send handshake message
        """
        self.send(self.torrent.handshake_message)
        
    def recv_handshake(self):
        """
        Handle receiving handshake from peer
        """
        protocol_id_length = ord(self.recv(1))
        protocol_id = self.recv(protocol_id_length)
        if protocol_id != self.torrent.PROTOCOL_ID:
            self.bad()
            raise BitTorrentPeerException("Connection is not serving " \
                "the BitTorrent protocol. Closed connection.")
        self.reserved = self.recv(8)
        self.info_hash = self.recv(20)
        self.peer_id = self.recv(20)
        
    # HANDLE MESSAGES
    
    def handle_message(self):
        """
        Takes the message from the socket and processes it.
        """
        message_type, payload_length = self.handle_message_type()
        message_type(payload_length)
                    
    def handle_message_type(self):
        """
        Takes the message header from the socket and processes it.
        Returns the message_type as a function and the payload length as
        a tuple.
        """
        message_type, payload_length = self.handle_message_header()
        logging.debug("Message type: {0}".format(message_type))
        logging.debug("Message payload length: {0}".format(
            payload_length
        ))
        return self.type_convert(message_type), payload_length
            
    def handle_message_header(self):
        """
        Accepts the first 5 bytes from the socket that make up the
        message header and returns the message type number and the
        length of the payload as a tuple.
        """
        payload_length = unpack(">I", self.recv(4))[0]
        # protection from a keep-alive
        if payload_length > 0:
            message_type = ord(self.recv(1))
        else:
            message_type = None
        return message_type, payload_length-1
        
    def type_convert(self, message_type):
        """
        Take an integer and translate it in to the function that can
        handle that message type.
        :param message_type: integer
        Returns function.
        """
        if 0 == message_type: return self.recv_choke
        if 1 == message_type: return self.recv_unchoke
        if 2 == message_type: return self.recv_interested
        if 3 == message_type: return self.recv_uninterested
        if 4 == message_type: return self.recv_have
        if 5 == message_type: return self.recv_bitfield
        if 6 == message_type: return self.recv_request
        if 7 == message_type: return self.recv_piece
        if 8 == message_type: return self.recv_cancel
        if 9 == message_type: return self.recv_port
        return self.recv_keep_alive
            
    def acquire(self, torrent_piece):
        """
        Takes a torrent piece and makes sures to get all the blocks to
        build that piece.
        :param torrent_piece: Piece object.
        Returns Piece if correctly downloaded or None if not downloaded
        """
        index = self.torrent.pieces.values().index(torrent_piece)
        peer_piece = self.pieces[torrent_piece.sha]
        
        logging.info("Sending requests for piece: {0}".format(
            torrent_piece.hex
        ))
        self.send_interested()
        next_block = peer_piece.size
        while next_block < self.torrent.piece_length:
            self.send_request(index, next_block)
            next_block += self.BLOCK_SIZE
        
        received = 0
        while not peer_piece.valid or received < self.BLOCK_SIZE:
            message_type, payload_len = self.handle_message_type()
            if message_type == self.recv_piece:
                received += len(message_type(payload_len))
            else:
                message_type(payload_len)
        logging.info("Download complete for piece: {0}".format(
            torrent_piece.hex
        ))
        if peer_piece.valid:
            return peer_piece
            
        self.bad()
        raise BitTorrentPeerException("Downloaded piece not valid. " \
            "Cut off peer."
        )
        
    # RECEIVE FUNCTIONS
        
    def recv_keep_alive(self, length=None):
        """
        These messages are sent to check the connection to the peer is
        still there.
        :param length: Does nothing here.
        """
        pass
        
    def recv_choke(self, length=None):
        """
        Recieved when the remote peer is over-loaded and won't handle
        any more messages send to it.
        :param length: Does nothing here.
        """
        self.status = self.ESTATUS.CHOKE
        payload = self.recv(length)
        
    def recv_unchoke(self, length=None):
        """
        Recieved when the remote peer has stopped being over-loaded.
        :param length: Does nothing here.
        """
        self.status = self.ESTATUS.OK
        payload = self.recv(length)
        
    def recv_interested(self, length=None):
        """
        Received when remote peer likes the look of one of your sexy
        pieces.
        :param length: Does nothing here.
        """
        payload = self.recv(length)
        
    def recv_uninterested(self, length=None):
        """
        Received when remote peer decides it can get the piece it wants
        from someone else :,(
        :param length: Does nothing here.
        """
        payload = self.recv(length)
       
    def recv_have(self, length):
        """
        Received when a peer was nice enough to tell you it has a piece
        you might be interested in.
        :param length: The size of the payload, normally a 4 byte
            integer
        """
        payload = self.recv(length)
        index = unpack(">I", payload)[0]
        self.pieces.values()[index].have = True
    
    def recv_bitfield(self, length):
        """
        Received only at the start of a connection when a peer wants to
        tell you all the pieces it has in a very compact form.
        :param length: The size of the payload, a number of bits
            representing the number of pieces
        """
        payload = self.recv(length)
        bits = BitArray(bytes=payload)
        for i in range(len(self.torrent.pieces)):
            sha, piece = self.torrent.pieces.items()[i]
            piece = self.PIECE(sha, self, have=bits[i])
            self.pieces[sha] = piece
            
    def recv_request(self, length):
        """
        Received when a peer wants a bit of one of your pieces.
        :param length: The size of the payload, a bunch of 4 byte
            integers representing the data the peer wants.
        """
        payload = self.recv(length)
        index, begin, size = unpack(">III", payload)
        if size > self.BLOCK_SIZE:
            self.bad()
            raise BitTorrentPeerException("Peer requested too much " \
                "data for a normal block: {size}".format(
                size=size
            ))
        data = self.pieces.values()[index].data[begin:size]
        self.send_piece(index, begin, data)
            
    def recv_piece(self, length):
        """
        The good stuff. Receives a block of data, not a whole piece, but
        makes up a part of a piece.
        :param length: The size of the payload, two 4 byte integers
            representing the position of the block, and then the block
            itself.
        """
        payload = self.recv(length)
        index, begin = unpack(">II", payload[:8])
        block = payload[8:]
        self.pieces.values()[index].insert_block(begin, block)
        return block
            
    def recv_cancel(self, length):
        """
        Received when a peer has made a request of a piece (or block),
        and you haven't yet fulfilled it, but the peer doesn't want it
        any more anyway.
        :param length: Not used here.
        """
        pass
            
    def recv_port(self, length):
        """
        Received when we're talking DHT, but for now, not used.
        :param length: Not used here.
        """
        payload = self.recv(length)
        
    # SEND
        
    def send_payload(self, message_type, payload=""):
        """
        Handy shortcut for sending messages.
        :param message_type: integer representing the message type
        :param payload: string of bytes of what to send
        """
        encoded_message_type = pack(">B", message_type)
        message_length = pack(
            ">I",
            len(payload) + len(encoded_message_type)
        )
        self.send(message_length + encoded_message_type + payload)
        
    def send_keep_alive(self):
        """
        Used to make sure the connection remains open.
        Doesn't use `send_payload` as it doesn't have a message type.
        """
        self.send("\x00"*4)
            
    def send_choke(self):
        """
        Tell the peer that this client can't handle any more messages
        and that all messages received will be ignored.
        """
        self.send_payload(0)
            
    def send_unchoke(self):
        """
        Tell a peer that it won't ignore it any more.
        """
        self.send_payload(1)
            
    def send_interested(self):
        """
        Tell the peer that you're interested in one of it's delicious
        pieces.
        """
        self.send_payload(2)
            
    def send_uninterested(self):
        """
        Tell the peer you've found someone better and there's plenty more
        fish in the sea.
        """
        self.send_payload(3)
        
    def send_have(self, index):
        """
        Tell the peer that this client now has this piece.
        :param index: Index of the piece you want to tell the peer is
            here.
        """
        payload = pack(">I", index)
        self.send_payload(4, payload)
        
    def send_bitfield(self):
        """
        Tell the peer all the pieces you have in a really compact form.
        """
        # the pieces are compacted in sequence in to bits
        field = BitArray(
            map(
                lambda (sha, piece): sha == piece.digest,
                self.torrent.pieces.items()
            )
        )
        self.send_payload(5, field.tobytes())
            
    def send_request(self, index, begin, length=None):
        """
        Request a block (rather than piece) from the peer, using the
        location and start point of the piece. The BitTorrent protocol
        uses a request/send method of downloading, so this asks a peer
        to send me a piece. It may work, it may not.
        :param index: Integer index of the piece being requested.
        :param begin: Integer of the byte that represents the block to
            download.
        :param length: Optional integer for how much to send, can also
            work it out itself.
        """
        if length is None:
            length = self.BLOCK_SIZE
        payload = pack(">III", index, begin, length)
        self.send_payload(6, payload)
            
    def send_piece(self, index, begin, data=None):
        """
        Send a requested piece to the peer, using the location and start
        point of the piece. Can work out what to send itself or can send
        whatever you like.
        :param index: Integer index of the piece was requested.
        :param begin: Integer of the byte that represents the block to
            upload.
        """
        if data is None:
            data = self.torrent.pieces.values()[index] \
                [begin:self.BLOCK_SIZE]
        header = pack(">II", index, begin)
        self.send_payload(7, header + data)
        self.uploaded += len(data)
            
    def send_cancel(self, index, begin, length=None):
        """
        Tells the peer that any pieces that have been requested can now
        be ignored and not sent to this client. The index, begin, and
        possibly length are used as identifiers to find that request and
        remove it from the queue of requests.
        :param index: Integer index of the piece was requested.
        :param begin: Integer of the byte that represents the block to
            upload.
        :param length: Integer representing the size of the block that
            was requested. If not known, will guess.
        """
        if length is None:
            length = self.BLOCK_SIZE
        payload = pack(">III", index, begin, length)
        self.send_payload(8, header + payload)
            
    def send_port(self):
        """
        Send when we're talking DHT, but for now, not used.
        :param length: Not used here.
        """
        pass


