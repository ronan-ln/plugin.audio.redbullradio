# -*- coding: utf-8 -*-
from kodiswift import Plugin
import requests
import json

plugin = Plugin()

def extract(text, startText, endText):
    start = text.find(startText, 0)
    if start != -1:
        start = start + startText.__len__()
        end = text.find(endText, start + 1)
        if end != -1:
            return text[start:end]
    return None


@plugin.cached(ttl=5)
def get_json_content(url):
    html = requests.get(url, verify=False).text
    json_content_str = extract(html, '<script>window.__INITIAL_STATE__ = ', '</script>')
    return json.loads(json_content_str)

def build_onair_item(json_content):
    episode = json_content['channels']['main']['currentTimeslot']['episode']
    show_slug = json_content['channels']['main']['currentTimeslot']['showSlug']

    episode_details = json_content['episodes'][show_slug][episode]
    try:
        episode_image = 'http:' + episode_details['imageURL']['landscape']
    except KeyError:
        episode_image = 'http:' + episode_details['imageURL']['portrait']
    episode_title = episode_details['title']
    episode_audio = episode_details['audioURL']
    return {
        'label': 'On Air',
        'path': 'http://broadcast.rbmaradio.net/main',
        'is_playable': True
    }

@plugin.route('/')
def index():
    index_json_content = get_json_content("https://redbullradio.com")

    items = [build_onair_item(index_json_content)]

    for label in ['channels', 'shows', 'on-demand', 'search']:
        item = {
            'label': label.replace('-', ' ').title(),
            'path': ':/{}'.format(label),
            'is_playable': False,
        }
        items.append(item)

    items += load_channels(featured=True)

    return items

@plugin.route('/channels/')
def load_channels(featured=False):

    if featured:
        json_content = get_json_content("https://redbullradio.com/")
    else:
        json_content = get_json_content("https://redbullradio.com/channels")

    items = []
    for channel_name in json_content['indexes']['channel']:
        if channel_name == 'main':
            continue

        channel_details = json_content['channels'].get(channel_name)
        if not channel_details:
            continue

        channel_title = channel_details['title']
        current_episode = channel_details['currentEpisode']
        channel_stream_url = channel_details['streamURL']
        show_slug = channel_details['showSlug']

        episode_details = json_content['episodes'][show_slug][current_episode]
        try:
            episode_image = 'http:' + episode_details['imageURL']['landscape']
        except KeyError:
            episode_image = 'http:' + episode_details['imageURL']['portrait']

        genres = ', '.join(map(unicode.title, [g['title'] for g in episode_details.get('genres', [])]))

        item = {
            'label': ('Channel:' if featured else '') + channel_title,
            'path': channel_stream_url if featured else ':/channels/{}'.format(channel_name),
            'is_playable': featured,
            'icon': episode_image,
            'info_type': 'music',
            'info': {'genre': genres}
        }
        items.append(item)

    return items

@plugin.route('/channels/<channel_name>')
def load_channel(channel_name):
    items = []

    json_content = get_json_content("https://redbullradio.com/")
    if channel_name not in json_content['channels']:
        json_content = get_json_content("https://redbullradio.com/channels/{}".format(channel_name))

    channel_details = json_content['channels'][channel_name]
    show_slug = channel_details['showSlug']

    current_episode = channel_details['currentEpisode']
    current_episode_details = json_content['episodes'][show_slug][current_episode]
    current_episode_title = current_episode_details['title']
    current_episode_url = current_episode_details['audioURL']
    try:
        current_episode_image = 'http:' + current_episode_details['imageURL']['landscape']
    except KeyError:
        current_episode_image = 'http:' + current_episode_details['imageURL']['portrait']

    current_episode_genres = ', '.join(map(unicode.title, [g['title'] for g in current_episode_details.get('genres', [])]))

    current_episode_item = {'label': 'Current-'+current_episode_title,
                            'path': current_episode_url,
                            'is_playable': True,
                            'icon': current_episode_image,
                            'info_type': 'music',
                            'info': {'genre': current_episode_genres}}
    items.append(current_episode_item)

    for episode in channel_details['episodes']:
        episode_name = episode['showSlug']
        show_name = episode['slug']

        if episode_name not in json_content['episodes'] \
        or show_name not in json_content['episodes'][episode_name]:
            continue

        episode_details = json_content['episodes'][episode_name][show_name]
        show_title = episode_details['showTitle']
        episode_title = episode_details['title']
        episode_url = episode_details['audioURL']
        try:
            episode_image = 'http:' + current_episode_details['imageURL']['landscape']
        except KeyError:
            episode_image = 'http:' + current_episode_details['imageURL']['portrait']

        episode_genres = ', '.join(map(unicode.title, [g['title'] for g in episode_details.get('genres', [])]))

        episode_item = {'label': ':'.join([show_title, episode_title]),
                        'path': episode_url,
                        'is_playable': True,
                        'icon': episode_image,
                        'info_type': 'music',
                        'info': {'genre': episode_genres}}

        if episode_item not in items:
            items.append(episode_item)

    return items

@plugin.route('/shows/')
def load_shows():
    json_content = get_json_content("https://redbullradio.com/shows")

    shows = {}
    featured_shows = []

    for show_name in json_content['indexes']['show']:
        show_details = json_content['shows'][show_name]
        show_title = show_details['title']

        item = {
            'label': show_title,
            'path': ':/shows/{}'.format(show_name),
            'is_playable': False
        }

        featured = show_details.get('featured', False)
        if featured:
            featured_shows.append(item)

        show_category = show_details.get('category')
        try:
            shows[show_category].append(item)
        except KeyError:
            shows[show_category]= [item]

    selected_category = plugin.request.args.get('category', [None])[0]
    if not selected_category:
        for s in featured_shows:
            s['label'] = 'Featured:' + s['label']
        items = featured_shows
        for category in shows.keys() + ['all']:
            if category:
                item = {
                    'label': category.replace('-', ' ').title(),
                    'path': ':/shows/?category={}'.format(category),
                    'is_playable': False
                }
                items.append(item)
    elif selected_category == 'all':
        items = featured_shows
        for category_shows in shows.values():
            items += category_shows
        items = sorted(items)
    else:
        items = shows[selected_category]
    return items

@plugin.route('/shows/<show_name>')
def load_show(show_name):
    json_content = get_json_content("https://redbullradio.com/shows/{}".format(show_name))

    items = []
    for episode_name in json_content['shows'][show_name]['previousEpisodes']:
        episode_details = json_content['episodes'][show_name][episode_name]
        episode_title = episode_details['title']
        episode_url = episode_details['audioURL']
        try:
            episode_image = 'http:' + current_episode_details['imageURL']['landscape']
        except KeyError:
            episode_image = 'http:' + current_episode_details['imageURL']['portrait']

        episode_genres = ', '.join([g['title'] for g in episode_details.get('genres',[])])

        episode_item = {'label': episode_title,
                        'path': episode_url,
                        'is_playable': True,
                        'icon': episode_image,
                        'info_type': 'music',
                        'info': {'genre': episode_genres}}
        items.append(episode_item)

    return items

@plugin.route('/shows/<show_name>/episodes/<episode_name>')
def load_episode(show_name, episode_name):
    json_content = get_json_content("https://redbullradio.com/shows/{}/episodes/{}".format(show_name, episode_name))

    items = []
    episode_details = json_content['episodes'][show_name][episode_name]
    episode_title = episode_details['title']
    episode_url = episode_details['audioURL']
    try:
        episode_image = 'http:' + current_episode_details['imageURL']['landscape']
    except KeyError:
        episode_image = 'http:' + current_episode_details['imageURL']['portrait']

    episode_genres = ', '.join([g['title'] for g in episode_details.get('genres',[])])

    episode_item = {'label': episode_title,
                    'path': episode_url,
                    'is_playable': True,
                    'icon': episode_image,
                    'info_type': 'music',
                    'info': {'genre': episode_genres}}
    items.append(episode_item)

    return items

@plugin.route('/on-demand/')
def load_ondemand(featured=False):

    json_content = get_json_content("https://redbullradio.com/")
    filter =  plugin.request.args.get('filter')

    items = []
    if not filter:
        for label, menu in [('Latest', 'latest'), ('Featured', 'featured'), ('Genres', 'byGenre')]:
            item = {'label': label,
                    'path': ':/on-demand?filter={}'.format(menu),
                    'is_playable': False}
            items.append(item)
    else:
        filter = filter[0]
        if filter == 'byGenre':
            for genre in json_content['onDemand'][filter].keys():
                item = {'label': genre.replace('-', ' ').title(),
                        'path': ':/on-demand/genres/{}'.format(genre),
                        'is_playable': False}
                items.append(item)
        else:
            for episode_details in json_content['onDemand'][filter]['episodes']:
                show_title = episode_details['showTitle']
                episode_title = episode_details['title']
                episode_url = episode_details['audioURL']
                episode_genres = ', '.join([g['title'] for g in episode_details.get('genres',[])])
                episode_image = episode_details['imageURL'].get('landscape')
                if not episode_image:
                    episode_image = episode_details['imageURL']['portrait']
                episode_image = 'http:' + episode_image

                episode_item = {'label': ':'.join([show_title, episode_title]),
                                'path': episode_url,
                                'is_playable': True,
                                'icon': episode_image,
                                'info_type': 'music',
                                'info': {'genre': episode_genres}}

                items.append(episode_item)

    return items

@plugin.route('/on-demand/genres/<genre>')
def load_ondemand_genre(genre):

    json_content = get_json_content("https://redbullradio.com/on-demand/genres/{}".format(genre))
    items = []
    for episode_details in json_content['onDemand']['byGenre'][genre]['episodes']:
        show_title = episode_details['showTitle']
        episode_title = episode_details['title']
        episode_url = episode_details['audioURL']
        episode_genres = ', '.join([g['title'] for g in episode_details.get('genres',[])])
        episode_image = episode_details['imageURL'].get('landscape')
        if not episode_image:
            episode_image = episode_details['imageURL']['portrait']
        episode_image = 'http:' + episode_image

        episode_item = {'label': ':'.join([show_title, episode_title]),
                        'path': episode_url,
                        'is_playable': True}

        items.append(episode_item)

    return items

@plugin.route('/search')
def search():

    query =  (plugin.request.args.get('q') or [plugin.keyboard()])[0]
    json_content = get_json_content("https://redbullradio.com/search?q={}".format(query))

    category = plugin.request.args.get('category', [None])[0]
    items = []
    if not category:
        for result_category, results in json_content['search']['results'].items():
            if len(results) > 0:
                item = {
                    'label': '{} ({})'.format(result_category.title(), len(results)),
                    'path': ':/search?q={}&category={}'.format(query, result_category),
                    'is_playable': False
                }
                items.append(item)
    else:
        for result in json_content['search']['results'][category]:
            show_title = result.get('showTitle', category.title())
            episode_title = result['title']
            path = result['path']
            image = 'http:' + result['image']

            result_item = {'label': ':'.join([show_title, episode_title]),
                            'path': ':{}'.format(path),
                            'is_playable': False}
            items.append(result_item)
    return items

if __name__ == '__main__':
    plugin.run()
