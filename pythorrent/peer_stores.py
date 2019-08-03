#    This file is part of PYTHorrent.
#
#    PYTHorrent is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    PYTHorrent is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with PYTHorrent.  If not, see <http://www.gnu.org/licenses/>.

import socket
import random
from urllib.parse import urlparse
from struct import unpack
from datetime import datetime, timedelta

from . import splice, BitTorrentException
from .peer import Peer

import requests
from torrentool.bencode import Bencode

import logging

def decode_binary_peers(peers):
    """ Return a list of IPs and ports, given a binary list of peers,
    from a tracker response. """

    peers = splice(peers, 6)	# Cut the response at the end of every peer
    return [(socket.inet_ntoa(p[:4]), decode_port(p[4:])) for p in peers]
    
def decode_port(port):
    """ Given a big-endian encoded port, returns the numerical port. """
    return unpack(">H", port)[0]
    
def store_from_url(url):
    """
    Get a store object based upon the URL used to access that peer
    store.
    :param url: URL used to access the peer store as string.
    """
    parsed_url = urlparse(url)
    if parsed_url.scheme.startswith("http"):
        return HTTPTracker
    if parsed_url.scheme.startswith("udp"):
        return UDPTracker
    # DHT would go here
    
class TrackerException(Exception):
    pass
    
class Tracker(object):
    PEER = Peer
    TRACKER_INTERVAL = 1800 # seconds
    
    def __init__(self, tracker_url, torrent):
        """
        Represents a tracker to get a list of peers from.
        :param tracker_url: URL to access the tracker at.
        :param torrent: Torrent object to hook back in to details needed
            to access the tracker.
        """
        self.tracker_url = tracker_url
        self.torrent = torrent
        self._peers = {}
        self.tracker_interval = self.TRACKER_INTERVAL
        self.last_run = None
    
    @property
    def now(self):
        """
        Use a consistent datetime now value.
        Returns DateTime object with value of now.
        """
        return datetime.utcnow()
        
    @property
    def delta(self):
        """
        Shortcut to get TimeDelta for delay between tracker requests.
        Returns TimeDelta object representing delay between tracker
            requests.
        """
        return timedelta(seconds=self.tracker_interval)
        
    @property
    def next_run(self):
        """
        Shortcut to find out when the tracker request should be next
        run.
        Returns DateTime object representing the next time the tracker
            wants an announce from the client as a minimum.
        """
        return self.last_run + self.delta
    
    @property
    def ok_to_announce(self):
        """
        Returns True when enough time has elapsed since last_run to
        announce again, and False if it has not, or has not been set,
        but also handles if has never been run.
        """
        if self.last_run is None:
            return True
        return self.now > self.next_run
        
    @property
    def peers(self):
        """
        If it is ok to get new peers will update the list of peers, then
        will return the list of peers.
        Returns list of Peer objects.
        """
        if self.ok_to_announce:
            logging.debug("Announcing to {url}".format(
                url=self.tracker_url
            ))
            self._peers.update(self.announce())
        return self._peers
        
    def announce(self):
        raise NotImplemented("Use this method to announce to tracker")
        
class HTTPTracker(Tracker):
    @property
    def announce_payload(self):
        """
        Returns the query params used to announce client to tracker.
        Returns dictionary of query params.
        """
        return {
            "info_hash" : self.torrent.info_hash,
            "peer_id" : self.torrent.peer_id,
            "port" : self.torrent.port,
            "uploaded" : self.torrent.uploaded,
            "downloaded" : self.torrent.downloaded,
            "left" : self.torrent.remaining,
            "compact" : 1
        }
    
    def announce(self):
        """
        Announces client to tracker and handles response.
        Returns dictionary of peers.
        """
        
        # Send the request
        try:
            response = requests.get(
                self.tracker_url,
                params=self.announce_payload,
                allow_redirects=False
            )
            logging.debug("Tracker URL: {0}".format(response.url))
        except requests.ConnectionError as e:
            logging.warn(
                "Tracker not found: {0}".format(
                    self.tracker_url
                )
            )
            return {}
            
        if response.status_code < 200 or response.status_code >= 300:
            raise BitTorrentException(
                "Tracker response error '{0}' for URL: {1}".format(
                    response.content,
                    response.url
                )
            )
            
        self.last_run = self.now
        
        decoded_response = Bencode.decode(response.content)
        
        self.tracker_interval = decoded_response.get(
            'interval',
            self.TRACKER_INTERVAL
        )
        logging.debug("Tracking interval set to: {interval}".format(
            interval=self.tracker_interval
        ))
        
        if "failure reason" in decoded_response:
            raise BitTorrentException(decoded_response["failure reason"])
    
        if "peers" in decoded_response: # ignoring `peer6` (ipv6) for now
            peers = decode_binary_peers(decoded_response['peers'])
        else:
            peers = []
        
        return dict(map(
                lambda hostport: (
                    hostport, self.PEER(hostport, self.torrent)
                ),
                peers
            ))

class UDPTracker(Tracker):
    DEFAULT_CONNECTION_ID = 0x41727101980
    
    class EACTION:
        NEW_CONNECTION = 0x0
        SCRAPE = 0x2
        ERROR = 0x3
    
    @staticmethod
    def generate_transaction_id():
        return int(random.randrange(0, 255))
    
    def __init__(self, *args, **kwargs):
        self.tracker_url_parts = urlparse(self.tracker_url)
        self._socket = None
        self._connection = None
        
    @property
    def socket(self):
        if self._socket is None:
            self._socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )
        return self._socket
        
    @property
    def connection(self):
        if self._connection is None:
            ip = socket.gethostbyname(self.tracker_url_parts.hostname)
            self._connection = (ip, self.tracker_url_parts.port)
        return self._connection
    
    def announce(self):
        connection_id = self.connection_request()
        peers, leechers, complete = self.scrape_request(connection_id)
        
    def generate_message(self,
        connection_id,
        action,
        transaction_id,
        payload=""
    ):
        buf = struct.pack("!q", connection_id)
        buf += struct.pack("!i", action)
        buf += struct.pack("!i", transaction_id)
        buf += payload
        return buf
        
    def send(self, msg):
        self.socket.sendto(msg, self.connection);
        
    def connection_request(self):
        transaction_id = self.generate_transaction_id()
        connection_request = self.generate_message(
            self.DEFAULT_CONNECTION_ID,
            self.EACTION.NEW_CONNECTION,
            transaction_id
        )
        
        self.send(connection_request)
        
        return parse_connection_response(transaction_id)

        
    def parse_connection_response(self, transaction_id):
        buf = self.socket.recvfrom(2048)[0]
        
        if len(buf) < 16:
            raise TrackerException(
                "Wrong response length getting connection id: " \
                "{0}".format(len(buf))
            )
        action = struct.unpack_from("!i", buf)[0]

        res_transaction_id = struct.unpack_from("!i", buf, 4)[0]
        if res_transaction_id != transaction_id:
            raise TrackerException("Transaction ID doesnt match in " \
                "connection response during connection request. " \
                "Expected {local}, got {response}".format(
                    local = transaction_id,
                    response = res_transaction_id
                )
            )

        if action == self.EACTION.NEW_CONNECTION:
            connection_id = struct.unpack_from("!q", buf, 8)[0] 
            return connection_id
        elif action == self.EACTION.ERROR:		
            error = struct.unpack_from("!s", buf, 8)
            raise TrackerException("Error while trying to get a " \
                "connection response: {0}".format(error))

    def scrape_request(self, connection_id):
        transaction_id = self.generate_transaction_id()
        request = self.generate_message(
            connection_id,
            self.EACTION.SCRAPE,
            transaction_id,
            struct.pack("!20s", self.torrent.info_hash)
        )
        self.send(request)
        
        return parse_scrape_response(transaction_id, info_hash)
    
    def parse_scrape_response(self, sent_transaction_id, info_hash):
        buf = self.socket.recvfrom(2048)[0]
        if len(buf) < 16:
            raise TrackerException(
                "Wrong response length while scraping: {0}".format(
                    len(buf)
                )
            )
                
        action = struct.unpack_from("!i", buf)[0]
        res_transaction_id = struct.unpack_from("!i", buf, 4)[0]	
        if res_transaction_id != sent_transaction_id:
            raise TrackerException("Transaction ID doesnt match in " \
                "connection response during scrape. Expected " \
                "{local}, got {response}".format(
                    local = transaction_id,
                    response = res_transaction_id
                )
            )
                
        if action == self.EACTION.SCRAPE:
            offset = 8; 
            seeds = struct.unpack_from("!i", buf, offset)[0]
            offset += 4
            complete = struct.unpack_from("!i", buf, offset)[0]
            offset += 4
            leeches = struct.unpack_from("!i", buf, offset)[0]
            offset += 4	
            return seeds, leeches, complete
            
        elif action == self.EACTION.ERROR:
            #an error occured, try and extract the error string
            error = struct.unpack_from("!s", buf, 8)
            raise TrackerException("Error while scraping: %s" % error)
    

