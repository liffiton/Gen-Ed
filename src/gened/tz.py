# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import datetime as dt
import platform

import pytz
from flask import request, session
from flask.app import Flask

# Anywhere-On-Earth timezone for checking expirations
tz_aoe = dt.timezone(dt.timedelta(hours=-12), name="AOE")


def date_is_past(date: dt.date) -> bool:
    """Return True if the given date object is in the past everywhere on Earth.
    Put another way: return True if the current time in the anywhere-on-Earth
    timezone is later than the given date."""
    now_aoe = dt.datetime.now(tz_aoe)
    given_aoe = dt.datetime.combine(date, dt.time.max, tz_aoe)
    return now_aoe > given_aoe


# Set up route for getting user's local timezone and filter for converting UTC to their timezone
def init_app(app: Flask) -> None:
    @app.route('/set_timezone', methods=['POST'])
    def set_timezone() -> str:
        '''Get timezone from the browser and store it in the session object.'''
        timezone = request.data.decode('utf-8')
        session['timezone'] = timezone
        return ""

    @app.template_filter('localtime')
    def localtime_filter(value: dt.datetime) -> str:
        '''Use timezone from the session object, if available, to localize datetimes from UTC.'''
        # https://stackoverflow.com/a/34832184
        utc_dt = pytz.utc.localize(value)

        # Windows uses a different format string for non-zero-padded hours
        # in strftime and does not support lowercase am/pm ('%P').
        # https://strftime.org/
        if platform.system() == "Windows":
            time_fmt = "%Y-%m-%d %#I:%M%p"
        else:
            time_fmt = "%Y-%m-%d %-I:%M%P"

        if 'timezone' not in session:
            return utc_dt.strftime(f"{time_fmt} %Z")  # %Z to include 'UTC'
        else:
            local_tz = pytz.timezone(session['timezone'])
            local_dt = utc_dt.astimezone(local_tz)
            return local_dt.strftime(time_fmt)
