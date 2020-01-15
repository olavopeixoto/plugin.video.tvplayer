# -*- coding: utf-8 -*-

import urllib, urllib2, sys, re, xbmcplugin, xbmcgui, xbmcaddon, xbmc, os
from datetime import datetime
import json
import util
from urlparse import urlparse
import net
import base64
from hashlib import md5
import uuid
import sys
import random

net = net.Net()

ADDON = xbmcaddon.Addon()

use_inputstream = util.use_inputstream()
allow_drm = util.allow_drm()

premium_enabled = ADDON.getSetting('premium') == 'true' and allow_drm
authentication_enabled = ADDON.getSetting('email') is not None and ADDON.getSetting('email') != '' and ADDON.getSetting('password') is not None and ADDON.getSetting('password') != ''
skinTheme = xbmc.getSkinDir().lower()
isJarvis = xbmc.getInfoLabel("System.BuildVersion").startswith("16.")
isFTV = skinTheme.startswith('skin.ftv')

addonPath = xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('path'))
artPath = os.path.join(addonPath, 'resources', 'media')
DEFAULT_THUMB = os.path.join(artPath, 'default_thumb.png')

PLATFORM = 'android-tv-v2'
VERSION = '4.5.1'
USER_AGENT = 'TVPlayer_4.1.3 (54059) - tv'

EPG_URL = 'http://api.tvplayer.com/api/v2/epg/?platform=' + PLATFORM + '&from=%s&hours=1'

STARTUP_URL = 'http://assets.storage.uk.tvplayer.com/android/v4/startups/tv/' + VERSION + '/startup.json'


def login_api():
    ADDON.setSetting('email_token', '')
    ADDON.setSetting('access_token', '')
    ADDON.setSetting('access_token_expires', '')

    email = ADDON.getSetting('email')
    password = ADDON.getSetting('password')

    loginUrl = 'https://api.tvplayer.com/api/v2/auth/?platform=' + PLATFORM

    headers = {'Authorization': 'Basic ' + base64.b64encode('%s:%s' % (email, password)),
               'User-Agent': USER_AGENT,
               'Accept-Encoding': 'gzip'}

    login_response = json.loads(net.http_GET(loginUrl, headers).content)['tvplayer']['response']

    access_token = login_response['access_token']
    access_token_expires = login_response['expires']

    ADDON.setSetting('email_token', email)
    ADDON.setSetting('access_token', access_token)
    ADDON.setSetting('access_token_expires', access_token_expires)

    return access_token, access_token_expires


def get_token(retry=1):
    if not is_token_valid():
        login_api()
        return get_token(retry - 1) if retry > 0 else None

    return ADDON.getSetting('access_token')


def is_token_valid():
    email_token = ADDON.getSetting('email_token')
    email = ADDON.getSetting('email')

    if email_token != email:
        return False

    access_token = ADDON.getSetting('access_token')
    access_token_expires = ADDON.getSetting('access_token_expires')

    expires = util.strptime_workaround(access_token_expires[:-5]) if access_token_expires else None  # 2018-04-13T02:53:14+0000

    return access_token and expires and expires >= datetime.utcnow()


def get_packs():

    packs_list = ADDON.getSetting('packs')

    if packs_list and is_token_valid():
        return json.loads(packs_list)

    token = get_token()

    url = 'https://api.tvplayer.com/api/v2/account/get?platform=%s&token=%s' % (PLATFORM, token)

    headers = {'User-Agent': USER_AGENT,
               'Accept-Encoding': 'gzip'}

    # xbmc.log('PACKS URL: %s' % url)

    response = json.loads(net.http_GET(url, headers).content)['tvplayer']['response']

    packs = response['packs']

    packs_list = [int(pack['id']) for pack in packs]

    ADDON.setSetting('packs', json.dumps(packs_list))

    return packs_list


def get_startup_settings():
    startup_settings = ADDON.getSetting('startup_settings')

    if startup_settings:
        return json.loads(startup_settings)

    headers = {'User-Agent': USER_AGENT,
               'Accept-Encoding': 'gzip'}

    startup_settings = json.loads(net.http_GET(STARTUP_URL, headers).content)

    ADDON.setSetting('startup_settings', json.dumps(startup_settings))

    return startup_settings


def find_programme(programmes, now):
    for programme in programmes:
        # try:
            start = util.strptime_workaround(programme['start'][:-5])
            end = util.strptime_workaround(programme['end'][:-5])

            if end >= now >= start:
                # xbmc.log('SELECTED PROGRAMME: %s (Start: %s | End: %s | Now: %s)' % (programme, start, end, now))
                return programme, start, end

            # xbmc.log('IGNORING PROGRAMME: %s (Start: %s | End: %s | Now: %s)' % (programme, start, end, now))

    # except:
        #     pass

    xbmc.log('NO PROGRAMME SELECTED: %s (Now: %s)' % (programmes, now))
    return None, None, None


def categories():
    now = datetime.utcnow()
    EST = now.strftime('%Y-%m-%dT%H:%M:%S')

    #xbmc.log("URL: %s" % URL)
    response = OPEN_URL(EPG_URL % str(EST))

    link = json.loads(response)

    data = link['tvplayer']['response']['channels']

    uniques = []

    if ADDON.getSetting('genre') == 'true':
        GENRE = 'All'
        uniques.append(GENRE)
        addDir(GENRE, 'url', 2, '', GENRE, '', GENRE, GENRE)

    my_packs = get_packs()

    for field in data:

        packs = field['packs']

        if len([pack for pack in packs if int(pack) in my_packs]) == 0:
            continue

        programme, start, end = find_programme(field['programmes'], now)

        sort_title = field['name'] if ADDON.getSetting('sort') == 'true' else field['order']
        id = str(field['id'])
        name = field['name']
        channel_name = name
        studio = name
        clearlogo = field['logo']['colour']
        icon = field['logo']['composite']
        tvshowtitle = programme['title'] or 'N/A' if programme is not None else 'N/A'
        title = programme['subtitle'] or 'N/A' if programme is not None else 'N/A'
        subtitle = programme['subtitle'] if programme is not None else ''
        GENRE = (field['genre'] or 'No Genre') if field['genre'] != 'No Genre' else field['group'] or field['genre']  #field["genre"]
        category = programme['category'] if programme is not None else GENRE
        is_closed = programme['category'] == 'Close' if programme is not None else True
        is_online = field['status'] == 'online'
        blackout = programme['blackout'] if programme is not None else True

        seasonNumber = programme['seasonNumber'] if programme is not None else None
        episodeNumber = programme['episodeNumber'] if programme is not None else None
        episodeInfo = u' (S%02d E%02d)' % (seasonNumber, episodeNumber) if seasonNumber and episodeNumber else ''

        # start = field['programmes'][0]['start']  #"start": "2017-05-18T23:40:00+0000"
        # end = field['programmes'][0]['end']  #"end": "2017-05-19T05:00:00+0000"

        try:
            duration = util.get_total_seconds(end - start)
            plotoutline = datetime.strftime(start, '%H:%M') + ' - ' + datetime.strftime(end, '%H:%M')
        except:
            duration = None
            plotoutline = None

        try:
            desc = programme['synopsis'].encode("utf-8")
        except:
            desc = ''

        color = '[COLOR royalblue]'

        add = ''
        if field['type'] == 'free' and field['authRequired'] is False:
            add = ''
        elif field['type'] == 'free' and field['authRequired'] is True:
            # color = '[COLOR navy]'
            pass
        else:
            color = '[COLOR magenta]'
        name = color + name.encode("utf-8") + '[/COLOR] - [COLOR white]' + tvshowtitle.encode("utf-8") + episodeInfo.encode("utf-8") + ((' / ' + subtitle.encode("utf-8")) if subtitle else '') + '[/COLOR]' + add
        status = field['status']
        fanart = programme['thumbnail'] if programme is not None else None
        if status == 'online' and not is_closed and is_online and not blackout and (allow_drm or (not field['drmEnabled'] and field['type'] != 'paid')):
            if ADDON.getSetting('genre') == 'false':
                if premium_enabled:
                    addDir(name, id, 200, icon, desc, fanart, category, sorttitle=sort_title, clearlogo=clearlogo, tvshowtitle=tvshowtitle, title=title, studio=studio, startdate=start, duration=duration, plotoutline=plotoutline, channel_name=channel_name)
                else:
                    if field['type'] == 'free' and field['authRequired'] is False:
                        addDir(name, id, 200, icon, desc, fanart, category, sorttitle=sort_title, clearlogo=clearlogo, tvshowtitle=tvshowtitle, title=title, studio=studio, startdate=start, duration=duration, plotoutline=plotoutline, channel_name=channel_name)
                    elif field['type'] == 'free' and field['authRequired'] is True and authentication_enabled is True:
                        addDir(name, id, 200, icon, desc, fanart, category, sorttitle=sort_title, clearlogo=clearlogo, tvshowtitle=tvshowtitle, title=title, studio=studio, startdate=start, duration=duration, plotoutline=plotoutline, channel_name=channel_name)
            else:
                if GENRE not in uniques:
                    if premium_enabled or (field['type'] == 'free' and not field['authRequired']) or (field['type'] == 'free' and field['authRequired'] and authentication_enabled):
                        uniques.append(GENRE)
                        addDir(GENRE, 'url', 2, '', GENRE, '', GENRE, GENRE)

    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE)
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL)

    setView('LiveTV' if isJarvis else 'artists', 'default')


def GENRE(genre, url):
    now = datetime.utcnow()
    est = now.strftime('%Y-%m-%dT%H:%M:%S')
    response = OPEN_URL(EPG_URL % str(est))

    link = json.loads(response)

    data = link['tvplayer']['response']['channels']

    # xbmc.log("DATA: %s" % data)

    genre = genre or 'No Genre'

    my_packs = get_packs()

    for field in data:

        packs = field['packs']

        if len([pack for pack in packs if int(pack) in my_packs]) == 0:
            continue

        programme, start, end = find_programme(field['programmes'], now)

        sort_title = field['name'] if ADDON.getSetting('sort') == 'true' else field['order']
        id = str(field['id'])
        name = field['name']
        channel_name = name
        studio = name
        clearlogo = field['logo']['colour']
        icon = field['logo']['composite']
        tvshowtitle = programme['title'] or 'N/A' if programme is not None else 'N/A'
        title = programme['subtitle'] or 'N/A' if programme is not None else 'N/A'
        subtitle = programme['subtitle'] if programme is not None else ''
        GENRE = (field['genre'] or 'No Genre') if field['genre'] != 'No Genre' else field['group'] or field[
            'genre']  # field["genre"]
        category = programme['category'] if programme is not None else GENRE
        is_closed = programme['category'] == 'Close' if programme is not None else True
        is_online = field['status'] == 'online'
        blackout = programme['blackout'] if programme is not None else True

        seasonNumber = programme['seasonNumber'] if programme is not None else None
        episodeNumber = programme['episodeNumber'] if programme is not None else None
        episodeInfo = u' - S%02d/E%02d' % (seasonNumber, episodeNumber) if seasonNumber and episodeNumber else ''

        # start = field['programmes'][0]['start']  #"start": "2017-05-18T23:40:00+0000"
        # end = field['programmes'][0]['end']  #"end": "2017-05-19T05:00:00+0000"

        try:
            duration = util.get_total_seconds(end - start)
            plotoutline = datetime.strftime(start, '%H:%M') + ' - ' + datetime.strftime(end, '%H:%M')
        except:
            duration = None
            plotoutline = None

        try:
            desc = programme['synopsis'].encode("utf-8")
        except:
            desc = ''

        color = '[COLOR royalblue]'

        add = ''
        if field['type'] == 'free' and field['authRequired'] is False:
            add = ''
        elif field['type'] == 'free' and field['authRequired'] is True:
            # color = '[COLOR navy]'
            pass
        else:
            color = '[COLOR magenta]'

        name = color + name.encode("utf-8") + '[/COLOR] - [COLOR white]' + tvshowtitle.encode("utf-8") + episodeInfo.encode("utf-8") + ((' / ' + subtitle.encode("utf-8")) if subtitle else '') + '[/COLOR]' + add

        status = field['status']
        fanart = programme['thumbnail'] if programme is not None else None
        if status == 'online' and not is_closed and is_online and not blackout and (allow_drm or (not field['drmEnabled'] and field['type'] != 'paid')):
            if GENRE in genre or (genre == 'All'):
                if premium_enabled:
                    addDir(name, id, 200, icon, desc, fanart, category, sorttitle=sort_title, clearlogo=clearlogo, tvshowtitle=tvshowtitle, title=title, studio=studio, startdate=start, duration=duration, plotoutline=plotoutline, channel_name=channel_name)
                else:
                    if field['type'] == 'free' and field['authRequired'] is False:
                        addDir(name, id, 200, icon, desc, fanart, category, sorttitle=sort_title, clearlogo=clearlogo, tvshowtitle=tvshowtitle, title=title, studio=studio, startdate=start, duration=duration, plotoutline=plotoutline, channel_name=channel_name)
                    elif field['type'] == 'free' and field['authRequired'] is True and authentication_enabled is True:
                        addDir(name, id, 200, icon, desc, fanart, category, sorttitle=sort_title, clearlogo=clearlogo, tvshowtitle=tvshowtitle, title=title, studio=studio, startdate=start, duration=duration, plotoutline=plotoutline, channel_name=channel_name)

    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE)
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL)

    setView('LiveTV' if isJarvis else 'artists', 'default')


def OPEN_URL(url):
    req = urllib2.Request(url)
    req.add_header('User-Agent', USER_AGENT)
    response = urllib2.urlopen(req)
    link = response.read()
    response.close()
    return link


def get_external_ip():
    url = 'https://api.tvplayer.com/checkip'
    return net.http_GET(url).content.strip().split(',')[0]


def validate():
    expiry = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+0000")

    token = expiry + "va27g19gWhqtFW3ff0bbDAaFVBOKAfRzwGA5L0ADu4p4ZWnOBGFgZAJgtdhOkzSVJhM4hRrk06LyXVMo" + get_external_ip()

    key = "d3a9547f-6a70-4631-b4c7-d66a8a9281d4"

    jsonToken = {
        "token": md5(token).hexdigest(),
        "key": key,
        "expiry": expiry
    }

    jsonString = json.dumps(jsonToken).replace(' ', '')

    return base64.b64encode(jsonString)


def get_stream_url(id):
    validation = urllib.quote_plus(validate())
    token = urllib.quote_plus(get_token())
    service = 1
    url = 'https://api.tvplayer.com/api/v2/stream/live/?service=%s&platform=%s&token=%s&validate=%s&id=%s' % (service, PLATFORM, token, validation, id)

    headers = {
        'accept':	'*/*',
        'user-agent': USER_AGENT,
        'accept-language':	'en-gb',
        'accept-encoding': 'gzip',
        'Need-Cache': 240
    }

    response = json.loads(net.http_GET(url, headers).content)

    print 'STREAM RESPONSE'
    print response

    if 'error' in response['tvplayer']['response']:
        raise Exception(response['tvplayer']['response']['error'])
        return None, None

    stream_url = response['tvplayer']['response']['stream']
    drm_token = response['tvplayer']['response']['drmToken']

    if int(id) == 607:
        ifa = ADDON.getSetting('ifa')

        if not ifa:
            ifa = str(uuid.uuid4()).upper()
            ADDON.setSetting('ifa', ifa)

        ip = get_external_ip()
        sid = str(random.randint(0, sys.maxint))
        auth_query = '&g=1000006&u=19287a324825cc5aacb7e46183c72324&z=268729&k=channel_id=221794;app_name=tvplayer;distributor=tvplayer;app_bundle=com.tvplayer;ifa=%s;ip=%s;dnt=0;channel_name=%s;content_type=live;sub_type=paid;gdpr=1;UA=device;consent=2&ptcueformat=turner&pttrackingmode=sstm&pttrackingversion=v2&__sid__=%s' % (ifa, ip, 'World%20Poker%20Tour', sid)
        stream_url = stream_url + auth_query

    return stream_url, drm_token


def play_stream_iplayer(channelname):
    # providers = [('ak', 'Akamai'), ('llnw', 'Limelight')]

    provider_url = 'ak'

    # First we query the available streams from this website
    if channelname in ['bbc_parliament', 'bbc_alba', 's4cpbs', 'bbc_one_london',
                       'bbc_two_wales_digital', 'bbc_two_northern_ireland_digital',
                       'bbc_two_scotland', 'bbc_one_cambridge', 'bbc_one_channel_islands',
                       'bbc_one_east', 'bbc_one_east_midlands', 'bbc_one_east_yorkshire',
                       'bbc_one_north_east', 'bbc_one_north_west', 'bbc_one_oxford',
                       'bbc_one_south', 'bbc_one_south_east', 'bbc_one_south_west',
                       'bbc_one_west', 'bbc_one_west_midlands', 'bbc_one_yorks']:
        device = 'tv'
    else:
        device = 'abr_hdtv'

    cast = "simulcast"

    url = 'https://a.files.bbci.co.uk/media/live/manifesto/audio_video/%s/hls/uk/%s/%s/%s.m3u8' \
          % (cast, device, provider_url, channelname)

    liz = xbmcgui.ListItem(name, iconImage='DefaultVideo.png', thumbnailImage=iconimage)
    liz.setInfo(type='Video', infoLabels={'Title': name})
    liz.setProperty("IsPlayable", "true")
    liz.setPath(url)

    if use_inputstream:
        liz.setProperty('inputstream.adaptive.manifest_type', 'hls')
        liz.setProperty('inputstreamaddon', 'inputstream.adaptive')

    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, liz)


def play_stream(name, url, iconimage, description, fanart, genre, title, tvshowtitle, studio, clearlogo, plotoutline):

    if ADDON.getSetting('use_iplayer') == 'true':
        settings = get_startup_settings()['iplayer_channelsid_values']
        for channel in settings:
            if int(url) == int(channel['id']):
                channelname = channel['value']
                return play_stream_iplayer(channelname)

    stream, drm_token = get_stream_url(url)

    liz = xbmcgui.ListItem(name)

    info_labels = {
                    "Plot": description,
                    "Genre": genre,
                    "title": title,
                    "studio": studio,
                    "tvshowtitle": tvshowtitle,
                    "PlotOutline": plotoutline
                }

    liz.setInfo(type='Video', infoLabels=info_labels)

    liz.setProperty("IsPlayable", "true")

    art = {
        'icon': iconimage,
        'clearlogo': clearlogo,
        'fanart': fanart,
        'thumb': fanart
    }

    liz.setArt(art)

    if use_inputstream or (allow_drm and drm_token):
        print 'USING INPUTSTREAM ADAPTIVE'

        parsed_url = urlparse(stream)
        # xbmc.log("PARSED STREAM URL: %s" % parsed_url.path)
        if parsed_url.path.endswith(".m3u8"):
            print 'HLS - M3U8'
            liz.setProperty('inputstream.adaptive.manifest_type', 'hls')
            liz.setProperty('inputstreamaddon', 'inputstream.adaptive')
            liz.setMimeType('application/vnd.apple.mpegurl')
            # liz.setProperty('inputstream.adaptive.stream_headers', 'cookie=' + token)
        elif parsed_url.path.endswith(".mpd"):
            print 'DASH - MPD'
            liz.setProperty('inputstream.adaptive.manifest_type', 'mpd')
            liz.setProperty('inputstreamaddon', 'inputstream.adaptive')
            liz.setMimeType('application/dash+xml')
            # liz.setProperty('inputstream.adaptive.stream_headers', 'cookie=' + token)

            # xbmc.log("-INPUTSTREAM.ADAPTIVE MPD-")
            # xbmc.log("DRM TOKEN: %s" % drm_token)

        if drm_token:

            print 'DRM STREAM - ' + drm_token

            # if util.use_drm_proxy():
            #     wv_proxy_base = 'http://localhost:' + str(ADDON.getSetting('wv_proxy_port'))
            #     wv_proxy_url = '{0}?mpd_url={1}&token={2}&{3}'.format(wv_proxy_base, stream,
            #                                                           base64.b64encode(drm_token),
            #                                                           drm_token)
            #     license_key = wv_proxy_url + '||R{SSM}|'
            # else:
            wv_proxy_url = 'https://widevine-proxy.drm.technology/proxy'
            post_data = urllib.quote_plus('{"token":"%s","drm_info":[D{SSM}],"kid":"{KID}"}' % drm_token)
            license_key = wv_proxy_url + '|Content-Type=application%2Fjson|' + post_data + '|'

            # xbmc.log("inputstream.adaptive.license_key: %s" % license_key)

            liz.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
            liz.setProperty('inputstream.adaptive.license_key', license_key)

    print 'STREAM URL - ' + stream
    liz.setPath(stream)

    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, liz)


def get_params():
    param = []
    paramstring = sys.argv[2]
    if len(paramstring) >= 2:
        params = sys.argv[2]
        cleanedparams = params.replace('?', '')
        if (params[len(params) - 1] == '/'):
            params = params[0:len(params) - 2]
        pairsofparams = cleanedparams.split('&')
        param = {}
        for i in range(len(pairsofparams)):
            splitparams = {}
            splitparams = pairsofparams[i].split('=')
            if (len(splitparams)) == 2:
                param[splitparams[0]] = splitparams[1]

    return param


def addDir(name, url, mode, iconimage, description, fanart, genre='', sorttitle=None, tvshowtitle=None, clearlogo=None, title=None, studio=None, startdate=None, duration=None, plotoutline=None, channel_name=None):

    print 'ADD-DIR-->'
    print name
    print url
    print mode
    print iconimage
    print description
    print fanart
    print genre
    print sorttitle
    print tvshowtitle
    print clearlogo
    print title
    print studio
    print startdate
    print duration
    print plotoutline
    print channel_name

    u = sys.argv[0] + "?url=" + urllib.quote_plus(url) + "&mode=" + str(mode) + "&name=" + urllib.quote_plus(channel_name or name) + "&iconimage=" + urllib.quote_plus(iconimage or '') + "&description=" + urllib.quote_plus(description or '') + "&genre=" + urllib.quote_plus(genre or '') + "&tvshowtitle=" + urllib.quote_plus(tvshowtitle or '') + "&fanart=" + urllib.quote_plus(fanart or '') + "&title=" + urllib.quote_plus(title or '') + "&studio=" + urllib.quote_plus(studio or '') + "&clearlogo=" + urllib.quote_plus(clearlogo or '') + "&plotoutline=" + urllib.quote_plus(plotoutline or '')

    liz = xbmcgui.ListItem(name, iconImage="DefaultFolder.png", thumbnailImage=iconimage)

    info_labels = {"Plot": description or ' ',
                   "Genre": genre,
                   'playcount': 0,
                   'overlay': 6
                   }

    if title and isFTV:
        info_labels.update({"title": title})

    if sorttitle:
        info_labels.update({"sorttitle": sorttitle})

    if studio:
        info_labels.update({"studio": studio})

    if tvshowtitle:
        info_labels.update({"tvshowtitle": tvshowtitle})

    if plotoutline:
        info_labels.update({'PlotOutline': plotoutline})

    if clearlogo:
        liz.setArt({'clearlogo': clearlogo})

    fanart = str(fanart) if len(re.findall(r'path=(.+)', str(fanart))) > 0 else DEFAULT_THUMB

    liz.setInfo(type="Video", infoLabels=info_labels)
    liz.setProperty('fanart_image', fanart)
    liz.setArt({'thumb': fanart})

    if duration:
        if startdate:
            offset = float(util.get_total_seconds(datetime.now(startdate.tzinfo) - startdate))
            liz.setProperty('Progress', str((offset / duration) * 100) if duration else str(0))
        liz.setProperty('totaltime', str(duration))

    if mode == 200:
        cm = [('Refresh', 'Container.Refresh')]
        liz.addContextMenuItems(cm)

        liz.setProperty("IsPlayable", "true")

        return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=False)

    return xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True)


def setView(content, viewType):
    if content:
        xbmcplugin.setContent(int(sys.argv[1]), content)
    if ADDON.getSetting('auto-view') == 'true':  # <<<----see here if auto-view is enabled(true)
        xbmc.executebuiltin("Container.SetViewMode(%s)" % ADDON.getSetting(viewType))  # <<<-----then get the view type

    # xbmcplugin.setPluginCategory(int(sys.argv[1]), 'TVPLAYER')


params = get_params()
url = None
name = None
mode = None
iconimage = None
description = None
fanart = None
genre = None

try:
    url = urllib.unquote_plus(params["url"])
except:
    pass
try:
    name = urllib.unquote_plus(params["name"])
except:
    pass
try:
    iconimage = urllib.unquote_plus(params["iconimage"])
except:
    pass
try:
    mode = int(params["mode"])
except:
    pass
try:
    description = urllib.unquote_plus(params["description"])
except:
    pass

try:
    fanart = urllib.unquote_plus(params["fanart"])
except:
    pass
try:
    genre = urllib.unquote_plus(params["genre"])
except:
    pass
try:
    tvshowtitle = urllib.unquote_plus(params["tvshowtitle"])
except:
    pass
try:
    title = urllib.unquote_plus(params["title"])
except:
    pass
try:
    studio = urllib.unquote_plus(params["studio"])
except:
    pass
try:
    clearlogo = urllib.unquote_plus(params["clearlogo"])
except:
    pass
try:
    plotoutline = urllib.unquote_plus(params["plotoutline"])
except:
    pass

# these are the modes which tells the plugin where to go
if mode is None or url is None or len(url) < 1:

    categories()

elif mode == 2:

    GENRE(name, url)

elif mode == 200:

    play_stream(name, url, iconimage, description, fanart, genre, title, tvshowtitle, studio, clearlogo, plotoutline)

xbmcplugin.endOfDirectory(int(sys.argv[1]), cacheToDisc=False)
