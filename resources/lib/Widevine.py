# -*- coding: utf-8 -*-

import json
import xml.etree.ElementTree as ET
import net
import xbmc

net = net.Net(user_agent="TVPlayer_4.1.3 (54059) - tv")


def log(msg):
    xbmc.log(msg=msg.encode('utf-8'), level=xbmc.LOGDEBUG)


class Widevine(object):
    license_url = 'https://widevine-proxy.drm.technology/proxy'

    def get_kid(self, mpd_url, AWSELB):
        """Parse the KID from the MPD manifest."""
        # mpd_data = helper.c.make_request(mpd_url, 'get')

        # log("-GET KID URL: %s" % mpd_url)

        headers = {
            'AWSELB': AWSELB
        }

        mpd_data = net.http_GET(mpd_url, headers).content

        # log("-MPD DATA: %s" % mpd_data)

        mpd_root = ET.fromstring(mpd_data)

        # log("-MPD ROOT: %s" % mpd_root)

        for i in mpd_root.iter('{urn:mpeg:dash:schema:mpd:2011}ContentProtection'):
            if '{urn:mpeg:cenc:2013}default_KID' in i.attrib:
                return i.attrib['{urn:mpeg:cenc:2013}default_KID']

    def get_license(self, mpd_url, wv_challenge, token, AWSELB):
        """Acquire the Widevine license from the license server and return it."""
        post_data = {
            'drm_info': [x for x in bytearray(wv_challenge)],  # convert challenge to a list of bytes
            'kid': self.get_kid(mpd_url, AWSELB),
            'token': token
        }

        # log("-GET LICENSE POST DATA: %s" % post_data)

        # wv_license = helper.c.make_request(self.license_url, 'post', payload=json.dumps(post_data))
        wv_license = net.http_POST(self.license_url, json.dumps(post_data), {'Content-Type': 'application/json'}).content
        return wv_license