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