import datetime as dt

import pytz

from flask import request, session

# Anywhere-On-Earth timezone for checking expirations
tz_aoe = dt.timezone(dt.timedelta(hours=-12), name="AOE")


def date_is_past(date):
    """Return True if the given date object is in the past everywhere on Earth.
    Put another way: return True if the current time in the anywhere-on-Earth
    timezone is later than the given date."""
    now_aoe = dt.datetime.now(tz_aoe)
    given_aoe = dt.datetime.combine(date, dt.time.max, tz_aoe)
    return now_aoe > given_aoe


# Set up route for getting user's local timezone and filter for converting UTC to their timezone
def init_app(app):
    @app.route('/set_timezone', methods=['POST'])
    def set_timezone():
        '''Get timezone from the browser and store it in the session object.'''
        timezone = request.data.decode('utf-8')
        session['timezone'] = timezone
        return ""

    @app.template_filter('localtime')
    def localtime_filter(value):
        '''Use timezone from the session object, if available, to localize datetimes from UTC.'''
        if 'timezone' not in session:
            return value

        # https://stackoverflow.com/a/34832184
        utc_dt = pytz.utc.localize(value)
        local_tz = pytz.timezone(session['timezone'])
        local_dt = utc_dt.astimezone(local_tz)
        return local_dt.strftime("%Y-%m-%d %-I:%M%P")
