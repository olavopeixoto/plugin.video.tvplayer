# Author: asciidisco
# Module: service
# Created on: 13.01.2017
# License: MIT https://goo.gl/5bMj3H

import threading
import SocketServer
import socket
import xbmc
from xbmc import Monitor
from xbmcaddon import Addon
from resources.lib.WidevineHTTPRequestHandler import WidevineHTTPRequestHandler
import util


# helper function to select an unused port on the host machine
def select_unused_port():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        addr, port = sock.getsockname()
        sock.shutdown()
        sock.close()
        return port
    except Exception as ex:
        return 8000


def log(msg):
    xbmc.log(msg=msg.encode('utf-8'), level=xbmc.LOGDEBUG)


if __name__ == '__main__':

    if util.use_drm_proxy():

        # pick & store a port for the proxy service
        wv_proxy_port = select_unused_port()
        Addon().setSetting('wv_proxy_port', str(wv_proxy_port))
        log('Port {0} selected'.format(str(wv_proxy_port)))

        # server defaults
        SocketServer.TCPServer.allow_reuse_address = True
        # configure the proxy server
        wv_proxy = SocketServer.TCPServer(('127.0.0.1', wv_proxy_port), WidevineHTTPRequestHandler)
        wv_proxy.server_activate()
        wv_proxy.timeout = 1

        # start thread for proxy server
        proxy_thread = threading.Thread(target=wv_proxy.serve_forever)
        proxy_thread.daemon = True
        proxy_thread.start()

        monitor = Monitor()

        # kill the services if kodi monitor tells us to
        while not monitor.abortRequested():
            # xbmc.sleep(100)
            if monitor.waitForAbort(1):
                break

        # wv-proxy service shutdown sequence
        wv_proxy.shutdown()
        wv_proxy.server_close()
        wv_proxy.socket.close()
        log('wv-proxy stopped')