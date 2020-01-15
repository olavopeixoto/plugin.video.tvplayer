import json
import xbmc, xbmcaddon
from xbmcaddon import Addon
from distutils.version import LooseVersion

def get_utc_delta():
    import datetime as dt
    return get_total_hours(dt.datetime.now() - dt.datetime.utcnow())

def strptime(date_string, format):
    import time
    from datetime import datetime
    try:
        return datetime.strptime(date_string, format)
    except TypeError:
        return datetime(*(time.strptime(date_string, format)[0:6]))

def strptime_workaround(date_string, format='%Y-%m-%dT%H:%M:%S'):
    import time
    from datetime import datetime
    try:
        return datetime.strptime(date_string, format)
    except TypeError:
        return datetime(*(time.strptime(date_string, format)[0:6]))

def get_total_seconds(timedelta):
    return (timedelta.microseconds + (timedelta.seconds + timedelta.days * 24 * 3600) * 10 ** 6) / 10 ** 6

def get_total_hours(timedelta):
    import datetime as dt
    hours = int(round(((timedelta.microseconds + (timedelta.seconds + timedelta.days * 24 * 3600) * 10 ** 6) / 10 ** 6) / 3600.0))
    return dt.timedelta(hours=hours)

def get_inputstream_addon():
    """Checks if the inputstream addon is installed & enabled.
       Returns the type of the inputstream addon used and if it's enabled,
       or None if not found.
    Returns
    -------
    :obj:`tuple` of obj:`str` and bool, or None
        Inputstream addon and if it's enabled, or None
    """
    type = 'inputstream.adaptive'
    payload = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'Addons.GetAddonDetails',
        'params': {
            'addonid': type,
            'properties': ['enabled']
        }
    }
    response = xbmc.executeJSONRPC(json.dumps(payload))
    data = json.loads(response)
    if 'error' not in data.keys():
        return type, data['result']['addon']['enabled']
    return None, None


def use_drm_proxy():

    addon_type, addon_enabled = get_inputstream_addon()

    try:
        inputstream_adaptive_addon = xbmcaddon.Addon ('inputstream.adaptive')
        inputstream_adaptive_version = inputstream_adaptive_addon.getAddonInfo('version')
        inputstream_adaptive_fixed = LooseVersion(inputstream_adaptive_version) >= LooseVersion('2.2.18')
        xbmc.log("INPUTSTREAM.ADAPTIVE VERSION: %s" % inputstream_adaptive_version)
        if not addon_enabled:
            xbmc.log("INPUTSTREAM.ADAPTIVE NOT ENABLED!")
    except Exception as ex:
        inputstream_adaptive_fixed = False
        xbmc.log("INPUTSTREAM.ADAPTIVE NOT AVAILABLE!")

    return not inputstream_adaptive_fixed and allow_drm() and Addon().getSetting('disable_drm_proxy') != 'true'


def is_inputstream_addon_available():

    addon_type, addon_enabled = get_inputstream_addon()

    return addon_type is not None and addon_enabled


def use_inputstream():
    return Addon().getSetting('use_inputstream') == 'true' and is_inputstream_addon_available()


def allow_drm():
    return Addon().getSetting('allow_drm') == 'true' and is_inputstream_addon_available()