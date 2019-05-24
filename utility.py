import datetime
import json
import pickle
import os.path
import pytz
import iso8601

import googleapiclient
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


def converted(data, timezone):
    tz = pytz.timezone(timezone)

    if type(data) == datetime.datetime:
        data = data.astimezone(tz)

        return data

    elif type(data) == tuple or type(data) == list:
        return [converted(item, timezone) for item in data]


def check_include(datetime_duration, a_date):
    if datetime_duration[0] <= a_date <= datetime_duration[1]:
        return True
    else:
        return False


def get_diff_minute(datetime1, datetime2):
    c = datetime2-datetime1

    return divmod(c.days * 86400 + c.seconds, 60)[0]


def subtract_between_datetime_durations(datetime_duration_list, datetime_duration, buffer_time):
    durations = []
    for item in datetime_duration_list:
        if item[1] < datetime_duration[0]:
            durations.append((item[0], item[1]))
        elif item[1] > datetime_duration[0] > item[0]:
            durations.append((item[0], datetime_duration[0]-datetime.timedelta(minutes=buffer_time)))
        elif item[0] > datetime_duration[1]:
            durations.append((item[0], item[1]))
        elif item[1] > datetime_duration[1] > item[0]:
            durations.append((datetime_duration[1]+datetime.timedelta(minutes=buffer_time), item[1]))

    return durations


def write_pickle(file_name, dict_data):
    with open(file_name, 'wb') as token:
        pickle.dump(dict_data, token)


def read_pickle(file_name):
    with open(file_name, 'rb') as token:
        data = pickle.load(token)

    return data


def get_availables(events, time_amount, minimum_notice, buffer_time, timezone):
    tz = pytz.timezone(timezone)
    now = datetime.datetime.now(tz)

    start_available = now + datetime.timedelta(minutes=minimum_notice)

    events = [
        (iso8601.parse_date(x), iso8601.parse_date(y)) for x, y in events]

    day = start_available.date()
    day_available = (tz.localize(datetime.datetime.combine(day, datetime.time(8, 00, 00))),
                     tz.localize(datetime.datetime.combine(day, datetime.time(17, 00, 00))))

    if check_include(day_available, start_available):
        day_available = (start_available,
                         tz.localize(datetime.datetime.combine(day, datetime.time(17, 00, 00))))

    elif start_available >= day_available[1]:
        day = day + datetime.timedelta(days=1)
        day_available = (tz.localize(datetime.datetime.combine(day, datetime.time(8, 00, 00))),
                         tz.localize(datetime.datetime.combine(day, datetime.time(17, 00, 00))))
    else:
        pass

    all_availables = []
    while True:
        day_events = [(x, y) for x, y in events if x.date() == day or y.date() == day]
        day_available = [day_available]
        for day_event in day_events:
            day_available = subtract_between_datetime_durations(day_available, day_event, buffer_time)

        day_available = [available for available in day_available if
                         get_diff_minute(*available) > time_amount]

        if len(day_available) > 0:
            all_availables.append(day_available)

        if len(all_availables) == 3:
            return all_availables

        day = day + datetime.timedelta(days=1)
        day_available = (tz.localize(datetime.datetime.combine(day, datetime.time(8, 00, 00))),
                         tz.localize(datetime.datetime.combine(day, datetime.time(17, 00, 00))))


def get_service():
    """Shows basic usage of the Admin SDK Directory API.
        Prints the emails and names of the first 10 users in the domain.
        """
    SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ]

    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)

    return service


def get_events(calendar_id, timezone=None):
    service = get_service()
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time

    future_events = []
    try:
        events_result = service.events().list(calendarId=calendar_id, timeMin=now,
                                            singleEvents=True,
                                            orderBy='startTime', timeZone=timezone).execute()
    except Exception as e:
        return "Not Found"

    print(events_result)
    events = events_result.get('items', [])
    timezone = events_result.get('timeZone')

    if not events:
        return []

    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))

        future_events.append((start, end))

    return future_events, timezone


def add_event(email, start_time, end_time):
    service = get_service()
    event = {
        'start': {
            'dateTime': start_time,
        },
        'end': {
            'dateTime': end_time,
        },
        'attendees': [
            {'email': email},
        ],
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 10},
            ],
        },
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    print('Event created: %s' % (event.get('htmlLink')))


if __name__ == "__main__":
    # print(get_events("saito.hideki1127@gmail.com"))
    # add_event('saito.hideki1127@gmail.com', '2019-05-23T09:00:00+07:00', '2019-05-23T10:00:00+07:00')

    # future_events = [('2019-05-24T14:00:00+09:00', '2019-05-25T15:00:00+09:00'), ('2019-05-25T17:00:00+09:00', '2019-05-25T17:15:00+09:00')]
    # availables = get_availables(future_events, 15, 60*24, 60, "Asia/Tokyo")
    # data = {}
    # data['availables'] = availables
    # write_pickle('temp', data)

    data = read_pickle('temp')
    availables = data['availables']
    print(availables[0][0][0].isoformat())
    # print(list(converted(availables, 'Asia/Taipei')))

    # data = read_pickle('819100378')
    # user = data['user']
    # recommend_date = data['recommend']
    # print(recommend_date)
    # add_event(user, recommend_date[0][0].isoformat() + "+00:00",
    #           (recommend_date[0][0] + datetime.timedelta(minutes=15)).isoformat() + '+00:00')