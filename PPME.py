import requests
import json
from datetime import datetime, timedelta
from plexapi.myplex import MyPlexAccount
from plexapi.exceptions import NotFound

# TheTVDB Authentication Information
TVDB_AUTH = {'apikey': '0d70d6c2d66e60ec1abf15f7d4528c6f',
             'userkey': '',
             'username': ''
             }

# Plex Server Information
PLEX_SERVERNAME = ''    # Friendly name of the server, by default your computer's name.
PLEX_USERNAME = ''
PLEX_PASSWORD = ''

BLACKLIST = ['The Big Bang Theory',
             'Dirty Jobs']

TIMEOUT = 20
MAX_ATTEMPTS = 3

if __name__ == '__main__':

    # Get TVDB token
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}

    response = requests.post('https://api.thetvdb.com/login', json=TVDB_AUTH, headers=headers)
    if response.status_code != 200:
        print('Failed to get TVDB token. HTTP error: ', response.status_code)
        exit(-1)

    token = json.loads(response.content.decode('utf-8'))['token']

    headers['Authorization'] = 'Bearer ' + token

    # Log in to Plex
    account = MyPlexAccount(PLEX_USERNAME, PLEX_PASSWORD)
    plex = account.resource(PLEX_SERVERNAME).connect()  # returns a PlexServer instance

    # Get shows from all show libraries
    plex_shows = []
    sections = [s for s in plex.library.sections() if s.type == 'show']
    for section in sections:
        plex_shows += [s for s in section.search() if s.title not in BLACKLIST]

    missing = {}

    for show in plex_shows:
        print('Collecting episodes for', show.title,
              '| Progress: {}%'.format(round((plex_shows.index(show) + 1) / len(plex_shows) * 100)))
        idx = show.guid
        show_id = idx[idx.index('//') + 2:idx.index('?')]
        #print('Show id:', show_id)

        response = requests.get('https://api.thetvdb.com/search/series?' + urlencode({'name': show.title}),
                                headers=headers)
        if response.status_code != 200:
            print('Warning: Could not check show id. Http error', response.status_code)
        else:
            series = None
            try:
                data = json.loads(response.content.decode('utf-8'))['data']
                series = [x for x in data if x['seriesName'] == show.title or show.title in x['aliases']][0]
                idx = series['id']
                if str(idx) != show_id:
                    print('Warning: ids do not match.')
                    print('Show id:', show_id, 'Id:', idx)
                    print(series)
            except:
                print('Warning: Could not check show id.')
                print('Series data:', series)
                print(traceback.format_exc())

        # Collect episodes
        episodes = []
        page = 1
        try:
            while page is not None:

                attempt = 1
                success = False
                while attempt < MAX_ATTEMPTS and not success:
                    response = requests.get('https://api.thetvdb.com/series/{}/episodes?page={}'.format(show_id, page),
                                            headers=headers)
                    if response.status_code != 200:
                        print('HTTP error:', response.status_code, 'Attempt:', attempt, 'Page:', page)
                        attempt += 1
                        sleep(TIMEOUT)
                    else:
                        success = True

                episodes_json = json.loads(response.content)
                page = episodes_json['links']['next']
                episodes += episodes_json['data']
        except:
            print('Failed to get episodes for ' + show.title)
            episodes = []

        # Check for missing
        for episode in episodes:

            aired_season = episode['airedSeason']
            if aired_season in [None, 0]:
                #print('No season')
                continue
            if episode['firstAired'] in [None, '']:
                #print('Not aired')
                continue
            date_first_aired = datetime.strptime(episode['firstAired'], '%Y-%m-%d')
            if datetime.now() + timedelta(days=-1) < date_first_aired:
                #print('Time not ok')
                continue

            episode_name = episode['episodeName']
            aired_episode_number = episode['airedEpisodeNumber']
            #print(episode_name, aired_episode_number)

            try:
                season = show.season(aired_season)
                titles = [e.title for e in season.episodes()]
                indexes = [e.index for e in season.episodes()]
            except NotFound:
                # Season is not on Plex server
                titles = []
                indexes = []

            if episode_name not in titles and aired_episode_number not in indexes:
                if show.title not in missing:
                    missing[show.title] = {}
                if aired_season not in missing[show.title]:
                    missing[show.title][aired_season] = []
                missing[show.title][aired_season].append({'airedEpisodeNumber': aired_episode_number,
                                                          'episodeName': episode_name})

    # Output
    for show_title in sorted(missing.keys()):
        for season_index in sorted(missing[show_title]):
            for e in missing[show_title][season_index]:
                print('{} S{}E{} - {}'.format(show_title,
                                              season_index,
                                              str(e['airedEpisodeNumber']).zfill(2),
                                              e['episodeName']))














