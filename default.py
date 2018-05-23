# -*- coding: utf-8 -*-

import urllib, urllib2, sys, re, xbmcplugin, xbmcgui, xbmcaddon, xbmc, os
from datetime import datetime, tzinfo, timedelta
import json
import util
from urlparse import urlparse
import net
import base64

net = net.Net()

ADDON = xbmcaddon.Addon()

datapath = xbmc.translatePath(ADDON.getAddonInfo('profile'))
cookie_path = os.path.join(datapath, 'cookies')
cookie_jar = os.path.join(cookie_path, 'tvplayer.lwp')
if not os.path.exists(cookie_path):
    os.makedirs(cookie_path)

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

unwanted_genres = ['Desi','Teleshopping','Music','Lifestyle']

platform = 'android'
version = '4.1.3'

EPG_URL = 'http://api.tvplayer.com/api/v2/epg/?platform=' + platform + '&from=%s&hours=1'

STARTUP_URL = 'http://assets.storage.uk.tvplayer.com/' + platform + '/v4/startups/tv/' + version + '/startup.json'

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_1) AppleWebKit/604.3.5 (KHTML, like Gecko) Version/11.0.1 Safari/604.3.5'
API_USER_AGENT = 'TVPlayer_4.1.3 (54059) - tv'
MOBILE_USER_AGENT = 'iPhone/iOS 8.4 (iPhone; U; CPU iPhone OS 8_4 like Mac OS X;)'


def login():
    loginurl = 'https://tvplayer.com/account/login/'
    email = ADDON.getSetting('email')
    password = ADDON.getSetting('password')

    headers = {'Host': 'tvplayer.com',
               'User-Agent': USER_AGENT,
               'Content-Type': 'application/x-www-form-urlencoded',
               'Accept': 'text/html',
               'Referer': 'https://tvplayer.com/watch',
               'Accept-Encoding': 'gzip',
               'Accept-Language': 'en-US'}

    link = net.http_GET(loginurl, headers).content
    net.save_cookies(cookie_jar)
    token = re.compile('name="token" value="(.+?)"').findall(link)[0]
    data = {'email': email, 'password': str(password), 'token': token}

    net.set_cookies(cookie_jar)

    net.http_POST(loginurl, data, headers)
    net.save_cookies(cookie_jar)


def login_api():
    ADDON.setSetting('email_token', '')
    ADDON.setSetting('access_token', '')
    ADDON.setSetting('access_token_expires', '')

    loginUrl = 'https://api.tvplayer.com/api/v2/auth/?platform=' + platform

    email = ADDON.getSetting('email')
    password = ADDON.getSetting('password')

    headers = {'Authorization': 'Basic ' + base64.b64encode('%s:%s' % (email, password)),
               'User-Agent': API_USER_AGENT,
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

    if email_token <> email:
        return False

    access_token = ADDON.getSetting('access_token')
    access_token_expires = ADDON.getSetting('access_token_expires')

    expires = util.strptime_workaround(access_token_expires[:-5]) if access_token_expires else None  # 2018-04-13T02:53:14+0000

    if not access_token or not expires or expires < datetime.utcnow():
        return False

    return True


def get_packs():

    packs_list = ADDON.getSetting('packs')

    if packs_list and is_token_valid():
        return json.loads(packs_list)

    token = get_token()

    url = 'https://api.tvplayer.com/api/v2/account/get?platform=%s&token=%s' % (platform, token)

    headers = {'User-Agent': API_USER_AGENT,
               'Accept-Encoding': 'gzip'}

    xbmc.log('PACKS URL: %s' % url)

    response = json.loads(net.http_GET(url, headers).content)['tvplayer']['response']

    packs = response['packs']

    packs_list = [int(pack['id']) for pack in packs]

    ADDON.setSetting('packs', json.dumps(packs_list))

    return packs_list


def get_startup_settings():
    startup_settings = ADDON.getSetting('startup_settings')

    if startup_settings:
        return json.loads(startup_settings)

    headers = {'User-Agent': API_USER_AGENT,
               'Accept-Encoding': 'gzip'}

    startup_settings = json.loads(net.http_GET(STARTUP_URL, headers).content)

    ADDON.setSetting('startup_settings', json.dumps(startup_settings))

    return startup_settings


def findprogramme(programmes, now):
    for programme in programmes:
        # try:
            start = util.strptime_workaround(programme['start'][:-5])
            end = util.strptime_workaround(programme['end'][:-5])

            if end >= now >= start:
                xbmc.log('SELECTED PROGRAMME: %s (Start: %s | End: %s | Now: %s)' % (programme, start, end, now))
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

        programme, start, end = findprogramme(field['programmes'], now)

        sort_title = field['order']
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
                if ADDON.getSetting('filter_channels') != 'true' or GENRE not in unwanted_genres:
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
    EST = now.strftime('%Y-%m-%dT%H:%M:%S')
    response = OPEN_URL(EPG_URL % str(EST))

    link = json.loads(response)

    data = link['tvplayer']['response']['channels']

    xbmc.log("DATA: %s" % data)

    genre = genre or 'No Genre'

    my_packs = get_packs()

    for field in data:

        packs = field['packs']

        if len([pack for pack in packs if int(pack) in my_packs]) == 0:
            continue

        programme, start, end = findprogramme(field['programmes'], now)

        sort_title = field['order']
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

        if field['type'] == 'free' and field['authRequired'] is False:
            add = ''
        elif field['type'] == 'free' and field['authRequired'] is True:
            # color = '[COLOR navy]'
            pass
        else:
            color = '[COLOR magenta]'

        name = color + name.encode("utf-8") + '[/COLOR] - [COLOR white]' + tvshowtitle.encode("utf-8") + episodeInfo + ((' / ' + subtitle) if subtitle else '') + '[/COLOR]' + add

        status = field['status']
        fanart = programme['thumbnail'] if programme is not None else None
        if status == 'online' and not is_closed and is_online and not blackout and (allow_drm or (not field['drmEnabled'] and field['type'] != 'paid')):
            if GENRE in genre or (genre == 'All' and (ADDON.getSetting('filter_channels') != 'true' or GENRE not in unwanted_genres)):
                if premium_enabled:
                    addDir(name, id, 200, icon, desc, fanart, category, sorttitle=sort_title, clearlogo=clearlogo, tvshowtitle=tvshowtitle, title=title, studio=studio, startdate=start, duration=duration, plotoutline=plotoutline, channel_name=channel_name)
                else:
                    if field['type'] == 'free' and field['authRequired'] is False:
                        addDir(name, id, 200, icon, desc, fanart, category, sorttitle=sort_title, clearlogo=clearlogo, tvshowtitle=tvshowtitle, title=title, studio=studio, startdate=start, duration=duration, plotoutline=plotoutline, channel_name=channel_name)
                    elif field['type'] == 'free' and field['authRequired'] is True and authentication_enabled is True:
                        addDir(name, id, 200, icon, desc, fanart, category, sorttitle=sort_title, clearlogo=clearlogo, tvshowtitle=tvshowtitle, title=title, studio=studio, startdate=start, duration=duration, plotoutline=plotoutline, channel_name=channel_name)

    if ADDON.getSetting('sort') == 'true':
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_TITLE)

    setView('LiveTV' if isJarvis else 'artists', 'default')


def OPEN_URL(url):
    req = urllib2.Request(url)
    req.add_header('User-Agent', USER_AGENT)
    response = urllib2.urlopen(req)
    link = response.read()
    response.close()
    return link


def OPEN_URL_STREAM_URL(url):
    import time
    # timestamp = int(time.time()) + 4 * 60 * 60
    header = {'Token': ADDON.getSetting('token'), 'Token-Expiry': ADDON.getSetting('expiry'),
              'Referer': ADDON.getSetting('referer'),
              'User-Agent': MOBILE_USER_AGENT}
    req = urllib2.Request(url, headers=header)

    response = urllib2.urlopen(req)
    link = response.read()
    response.close()
    cookie = response.info()['Set-Cookie']
    return link, cookie


def tvplayer(url, name):
    if authentication_enabled:
        login()
        net.set_cookies(cookie_jar)

    headers = {'Host': 'tvplayer.com',
               'Connection': 'keep-alive',
               'Origin': 'http://tvplayer.com',
               'User-Agent': USER_AGENT,
               'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
               'Accept': '*/*',
               'Accept-Encoding': 'gzip, deflate',
               'Accept-Language': 'en-US,en;q=0.8'}

    html = net.http_GET('http://tvplayer.com/watch/%s' % name.lower().replace(' ', ''), headers).content

    resource = re.compile('data-resource="(.+?)"').findall(html)[0]
    nouce = re.compile('data-token="(.+?)"').findall(html)[0]

    jsonString = net.http_GET('https://tvplayer.com/watch/context?resource=%s&gen=%s' % (resource, nouce), headers).content

    context = json.loads(jsonString)

    validate = context['validate']

    token = context['token'] if 'token' in context else 'null'

    data = {'service': '1',
            'platform': 'chrome',
            'id': url,
            'token': token,
            'validate': validate}

    post_url = 'http://api.tvplayer.com/api/v2/stream/live'
    headers = {'Host': 'api.tvplayer.com',
               'Connection': 'keep-alive',
               'Origin': 'http://api.tvplayer.com',
               'User-Agent': USER_AGENT,
               'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
               'Accept': '*/*',
               'Accept-Encoding': 'gzip, deflate',
               'Accept-Language': 'en-US,en;q=0.8'}

    link = net.http_POST(post_url, data, headers=headers).content

    xbmc.log('LINK: %s' % link)

    net.save_cookies(cookie_jar)

    link_json = json.loads(link)

    return link_json['tvplayer']['response']['stream'], link_json['tvplayer']['response']['drmToken'] if 'drmToken' in link_json['tvplayer']['response'] else None, context

    # GET WORKS TOO
    # POSTURL='http://api.tvplayer.com/api/v2/stream/live?service=1&platform=website&id=%stoken=null&validate=%s'% (url,VALIDATE)
    # LINK=net.http_GET(POSTURL,headers=headers).content
    # return re.compile('stream": "(.+?)"').findall(LINK)[0]

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
        device = 'hls_tablet'
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


def play_stream(name, url, iconimage):

    if ADDON.getSetting('use_iplayer') == 'true':
        settings = get_startup_settings()['iplayer_channelsid_values']
        for channel in settings:
            if int(url) == int(channel['id']):
                channelname = channel['value']
                return play_stream_iplayer(channelname)

    stream, drm_token, context = tvplayer(url, name)

    token = open(cookie_jar).read()
    token = 'AWSELB=' + re.compile('AWSELB=(.+?);').findall(token)[0]

    epg = context['epg']
    channel = context['channel']

    label = channel['name'] # + ' - ' + epg['title']
    title = label
    clearlogo = channel['logo']['compositeWide']
    studio = channel['name']
    tvshowtitle = epg['seriesTitle']
    synopsis = epg['synopsis']
    thumb = epg['thumbnail']
    genre = channel['genre']

    liz = xbmcgui.ListItem(label)

    info_labels = {
                    # "Plot": synopsis,
                    "Genre": genre,
                    "title": title,
                    "studio": studio,
                    # "tvshowtitle": tvshowtitle,
                    # "PlotOutline": synopsis
                }

    liz.setInfo(type='Video', infoLabels=info_labels)

    liz.setProperty("IsPlayable", "true")

    # art = {
    #         'icon': clearlogo,
    #         'clearlogo': clearlogo,
    #         'fanart': thumb,
    #         'thumb': thumb
    #     }

    art = {
        'icon': clearlogo,
        'clearlogo': clearlogo,
        'fanart': clearlogo,
        'thumb': clearlogo
    }

    liz.setArt(art)

    if use_inputstream:
        parsed_url = urlparse(stream)
        xbmc.log("PARSED STREAM URL: %s" % parsed_url.path)
        if parsed_url.path.endswith(".m3u8"):
            liz.setProperty('inputstream.adaptive.manifest_type', 'hls')
            liz.setProperty('inputstreamaddon', 'inputstream.adaptive')
            liz.setProperty('inputstream.adaptive.stream_headers', 'cookie=' + token)
        elif parsed_url.path.endswith(".mpd"):
            liz.setProperty('inputstream.adaptive.manifest_type', 'mpd')
            liz.setProperty('inputstreamaddon', 'inputstream.adaptive')
            liz.setProperty('inputstream.adaptive.stream_headers', 'cookie=' + token)

            xbmc.log("-INPUTSTREAM.ADAPTIVE MPD-")
            xbmc.log("DRM TOKEN: %s" % drm_token)

            if drm_token:

                if util.use_drm_proxy():
                    wv_proxy_base = 'http://localhost:' + str(ADDON.getSetting('wv_proxy_port'))
                    wv_proxy_url = '{0}?mpd_url={1}&token={2}&{3}'.format(wv_proxy_base, stream, base64.b64encode(drm_token), token)
                    license_key = wv_proxy_url + '||R{SSM}|'
                else:
                    wv_proxy_url = 'https://widevine-proxy.drm.technology/proxy'
                    post_data = urllib.quote_plus('{"token":"%s","drm_info":[D{SSM}],"kid":"{KID}"}' % drm_token)
                    license_key = wv_proxy_url + '|Content-Type=application%2Fjson|' + post_data + '|'


                # wv_proxy_base = 'http://localhost:' + str(ADDON.getSetting('wv_proxy_port'))
                # wv_proxy_url = '{0}?mpd_url={1}&token={2}&{3}'.format(wv_proxy_base, STREAM,
                #                                                       base64.b64encode(drm_token), TOKEN)
                # license_key = wv_proxy_url + '||R{SSM}|'

                xbmc.log("inputstream.adaptive.license_key: %s" % license_key)

                liz.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
                liz.setProperty('inputstream.adaptive.license_key', license_key)
    else:
        stream = stream + '|Cookies=' + token

    item_path = stream

    liz.setPath(item_path)

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
    u = sys.argv[0] + "?url=" + urllib.quote_plus(url) + "&mode=" + str(mode) + "&name=" + urllib.quote_plus(channel_name or name) + "&iconimage=" + urllib.quote_plus(iconimage) + "&description=" + urllib.quote_plus(description) + "&genre=" + urllib.quote_plus(genre)

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

# these are the modes which tells the plugin where to go
if mode is None or url is None or len(url) < 1:

    categories()

elif mode == 2:

    GENRE(name, url)

elif mode == 200:

    play_stream(name, url, iconimage)

xbmcplugin.endOfDirectory(int(sys.argv[1]), cacheToDisc=False)






# WARNING: CreateLoader - unsupported protocol(plugin) in plugin://plugin.video.tvplayer/?url=90&mode=200&name=%5BCOLOR+royalblue%5DBBC+Two%5B%2FCOLOR%5D+-+%5BCOLOR+white%5DThe+World+According+to+Kids%5B%2FCOLOR%5D&iconimage=https%3A%2F%2Fassets.tvplayer.com%2Fcommon%2Flogos%2F256%2FColour%2F90.png&description=A+further+insight+into+how+children+see+the+world+as+youngsters+from+a+boxing+club+in+London%2C+a+pony+club+in+Berkshire+and+a+choir+in+Liverpool+reveal+how+they+tell+right+from+wrong.+They+include+10-year-old+Ma-Leiha%2C+who+is+struggling+at+school+after+fighting+with+boys%2C+and+nine-year-old+Jumi%2C+who+is+so+easily+influenced+his+family+worry+it+could+land+him+in+trouble.&genre=Entertainment
# ERROR: Open - failed to open source <plugin://plugin.video.tvplayer/?url=90&mode=200&name=%5BCOLOR+royalblue%5DBBC+Two%5B%2FCOLOR%5D+-+%5BCOLOR+white%5DThe+World+According+to+Kids%5B%2FCOLOR%5D&iconimage=https%3A%2F%2Fassets.tvplayer.com%2Fcommon%2Flogos%2F256%2FColour%2F90.png&description=A+further+insight+into+how+children+see+the+world+as+youngsters+from+a+boxing+club+in+London%2C+a+pony+club+in+Berkshire+and+a+choir+in+Liverpool+reveal+how+they+tell+right+from+wrong.+They+include+10-year-old+Ma-Leiha%2C+who+is+struggling+at+school+after+fighting+with+boys%2C+and+nine-year-old+Jumi%2C+who+is+so+easily+influenced+his+family+worry+it+could+land+him+in+trouble.&genre=Entertainment>