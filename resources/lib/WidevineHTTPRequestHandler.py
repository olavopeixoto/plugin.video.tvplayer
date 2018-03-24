# -*- coding: utf-8 -*-

import BaseHTTPServer
import urlparse
import base64
import traceback
import xbmc

from Widevine import Widevine

wv = Widevine()


def log(msg):
    xbmc.log(msg=msg.encode('utf-8'), level=xbmc.LOGDEBUG)


class WidevineHTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)

    def do_POST(self):
        length = int(self.headers['content-length'])
        wv_challenge = self.rfile.read(length)

        # log("WidevineHTTPRequestHandler - PATH: %s" % self.path)

        query = dict(urlparse.parse_qsl(urlparse.urlsplit(self.path).query))
        mpd_url = query['mpd_url']

        # log("WidevineHTTPRequestHandler - mpd_url: %s" % mpd_url)

        token = base64.b64decode(query['token'])

        # log("WidevineHTTPRequestHandler - token: %s" % token)

        AWSELB = query['AWSELB']

        # log("WidevineHTTPRequestHandler - AWSELB: %s" % AWSELB)

        try:
            wv_license = wv.get_license(mpd_url, wv_challenge, token, AWSELB)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(wv_license)
            self.finish()
        except Exception as ex:
            log("WidevineHTTPRequestHandler - ERROR: %s" % ex)
            traceback.print_exc()

            self.send_response(400)
            self.wfile.write(ex.message)

    def log_message(self, format, *args):
        """Disable the BaseHTTPServer log."""
        return