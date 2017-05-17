# -*- coding: utf-8 -*-
from kodiswift import Plugin
import requests
import json

plugin = Plugin()

def make_image_url(url, thumbnail=True):
    url = 'http:' + url
    if thumbnail:
        url += '?auto=format&dpr=1&crop=faces&fit=crop&w=70&h=70'
    return url

def extract(text, startText, endText):
    start = text.find(startText, 0)
    if start != -1:
        start = start + startText.__len__()
        end = text.find(endText, start + 1)
        if end != -1:
            return text[start:end]
    return None

@plugin.cached(ttl=60)
def get_json_content(url):
    html = requests.get(url, verify=False).text
    json_content_str = extract(html, '<script>window.__INITIAL_STATE__ = ', '</script>')
    return json.loads(json_content_str)

def build_onair_item(json_content):
    onair_channel = json_content['channels']['main']
    episode = onair_channel['currentTimeslot']['episode']
    show_slug = onair_channel['currentTimeslot']['showSlug']
    details = json_content['episodes'][show_slug][episode]

    onair_channel_url = onair_channel['streamURL']
    return build_item(details, prefix='On Air', force_url=onair_channel_url)

menu_map = {'channels': 'load_channels',
            'channel': 'load_channel',
            'shows': 'load_shows',
            'on-demand': 'load_ondemand',
            'search': 'search'
}
@plugin.route('/')
def index():
    json_content = get_json_content("https://redbullradio.com")

    items = [build_onair_item(json_content)]

    for label in ['channels', 'shows', 'on-demand', 'search']:
        item = {
            'label': label.replace('-', ' ').title(),
            'path': plugin.url_for(menu_map[label]),
            'is_playable': False,
        }
        items.append(item)

    items += load_channels(featured=True)

    return items

def build_item(details, prefix='', force_url=None, playable=True, label=''):
    title = details['title']
    url = force_url or details['audioURL']
    genres = ', '.join(map(unicode.title, [g['title'] for g in details.get('genres', [])]))
    image_url = details['imageURL'].get('landscape') or details['imageURL'].get('portrait')
    if not label:
        if prefix:
            label = ':'.join([prefix, title])
        else:
            label = title

    item = {
        'label': label,
        'path': url,
        'icon': make_image_url(image_url, thumbnail=True),
        'thumbnail': make_image_url(image_url, thumbnail=True),
        'poster': make_image_url(image_url, thumbnail=False),
        'info_type': 'music',
        'info': {'genre': genres,
                 'date': '.'.join(details['premiereOn'].split(' ')[0].split('-')[-1:0]) if 'premierOn' in details else None,
                 'duration': details.get('duration'),
                 'title': title,
                 'description': details.get('descriptionText')
                 },
        'is_playable': playable,}

    return item


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

        if featured:
            item = build_item(episode_details,
                              prefix=channel_title,
                              force_url=channel_stream_url,
                              playable=True)
        else:
            item = build_item(episode_details,
                              label=channel_title,
                              force_url=plugin.url_for(menu_map['channel'], channel_name=channel_name),
                              playable=False)

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

    current = channel_details['currentEpisode']
    current_details = json_content['episodes'][show_slug][current]

    items.append(build_item(current_details, prefix='OnAir'))

    for episode in channel_details['episodes']:
        show_name = episode['showSlug']
        episode_name = episode['slug']

        show_url = plugin.url_for('episode_route', episode_name=episode_name, show_name=show_name)
        item = build_item(episode, force_url=show_url, playable=False)

        if item and item not in items:
            items.append(item)

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
            'path': plugin.url_for('show_route', show_name=show_name),
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
        items = []
        for category in shows.keys() + ['all']:
            if category:
                item = {
                    'label': category.replace('-', ' ').title(),
                    'path': plugin.url_for(menu_map['shows'], category=category),
                    'is_playable': False
                }
                items.append(item)
        items += featured_shows
    elif selected_category == 'all':
        items = featured_shows
        for category_shows in shows.values():
            items += category_shows
        items = sorted(items)
    else:
        items = shows[selected_category]
    return items

@plugin.route('/shows/<show_name>/episodes/<episode_name>', name='episode_route')
@plugin.route('/shows/<show_name>', name='show_route')
def load_episode(show_name, episode_name=None):
    json_content = get_json_content("https://redbullradio.com/shows/{}".format(show_name))
    if episode_name:
        episode_names = [episode_name]
    else:
        episode_names = json_content['shows'][show_name]['previousEpisodes']

    items = []
    for episode_name in episode_names:
        if episode_name in json_content['episodes'][show_name]:
            episode_details = json_content['episodes'][show_name][episode_name]
            items.append(build_item(episode_details))

    return items

@plugin.route('/on-demand/')
def load_ondemand(featured=False):

    json_content = get_json_content("https://redbullradio.com/")
    filter =  plugin.request.args.get('filter')

    items = []
    if not filter:
        for label, menu in [('Latest', 'latest'), ('Featured', 'featured'), ('Genres', 'byGenre')]:
            item = {'label': label,
                    'path': plugin.url_for(menu_map['on-demand'], filter=menu),
                    'is_playable': False}
            items.append(item)
    else:
        filter = filter[0]
        if filter == 'byGenre':
            for genre in json_content['onDemand'][filter].keys():
                item = {'label': genre.replace('-', ' ').title(),
                        'path': plugin.url_for('load_ondemand_genre', genre=genre),
                        'is_playable': False}
                items.append(item)
        else:
            for episode_details in json_content['onDemand'][filter]['episodes']:
                items.append(build_item(episode_details))

    return items

@plugin.route('/on-demand/genres/<genre>')
def load_ondemand_genre(genre):

    json_content = get_json_content("https://redbullradio.com/on-demand/genres/{}".format(genre))
    items = []
    for episode_details in json_content['onDemand']['byGenre'][genre]['episodes']:
        items.append(build_item(episode_details))

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
                    'path': plugin.url_for(menu_map['search'])+'?q={}&category={}'.format(query, result_category),
                    'is_playable': False
                }
                items.append(item)
    else:
        for result in json_content['search']['results'][category]:
            show_title = result.get('showTitle', category.title())
            episode_title = result['title']
            path = result['path']

            result_item = {'label': ':'.join([show_title, episode_title]),
                           'path': ':{}'.format(path),
                           'thumbnail': make_image_url(result['image'], thumbnail=True),
                           'is_playable': False}
            items.append(result_item)
    return items

if __name__ == '__main__':
    plugin.run()
