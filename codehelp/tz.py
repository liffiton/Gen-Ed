import pytz

from flask import request, session


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
        return local_dt
