import requests
import json
from datetime import datetime, timedelta
from plexapi.myplex import MyPlexAccount
from plexapi.exceptions import NotFound

# TheTVDB Authentication Information
TVDB_AUTH = {'apikey': ''
             }

# Plex Server Information
PLEX_SERVERNAME = ''    # Friendly name of the server. https://support.plex.tv/articles/200289496-general/.
PLEX_USERNAME = ''
PLEX_PASSWORD = ''

# Blacklist will ignore shows, make sure to wrap in single quote and add comma in between shows.
BLACKLIST = ['Show example',
             'Example 2']

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

        # Collect episodes
        episodes = []
        page = 1
        try:
            while page is not None:
                response = requests.get('https://api.thetvdb.com/series/{}/episodes?page={}'.format(show_id, page),
                                        headers=headers)
                if response.status_code != 200:
                    print('HTTP error:', response.status_code, 'Show id:', show_id, 'Page:', page)
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
                continue
            if episode['firstAired'] in [None, '']:
                continue
            date_first_aired = datetime.strptime(episode['firstAired'], '%Y-%m-%d')
            if datetime.now() + timedelta(days=-1) < date_first_aired:
                continue

            episode_name = episode['episodeName']
            aired_episode_number = episode['airedEpisodeNumber']

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














