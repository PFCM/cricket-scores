"""
Get scores for cricket matches.
"""
import collections

import dateutil.parser
import requests
from bs4 import BeautifulSoup


def _transfer_dict_keys(key_pairs, source, sink):
    """Copy items from `source` to `sink` if they exist."""
    for k1, k2 in key_pairs:
        try:
            sink[k2] = source[k1]
        except KeyError:
            pass
    return sink


def _get_teams(match):
    """Get real names for the teams involved in the match"""
    teams = [{
        'name': team['Name'],
        'id': team['id']
    } for team in match.find_all('Tm')]
    if len(teams) != 2:
        return None
    return teams


def _construct_time(time_element):
    """pull the time out of the time element for the game."""
    date = time_element['Dt']
    start_time = time_element['stTme']
    return dateutil.parser.parse('{} {} GMT'.format(date, start_time))


def _parse_innings(detail, bat, bowl):
    """Parse an innings from the three constituent parts."""
    # the detail has tihngs like the required run rate, we don't really care
    batting = {
        'team': bat['sName'],
        'declare': bool(bat.Inngs['Decl']),
        'follow_on': bool(bat.Inngs['FollowOn']),
        'overs': float(bat.Inngs['ovrs']),
        'runs': int(bat.Inngs['r']),
        'wickets': int(bat.Inngs['wkts'])
    }
    bowling = {
        'team': bowl['sName'],
        'declare': bool(bowl.Inngs['Decl']),
        'follow_on': bool(bowl.Inngs['FollowOn']),
        'overs': float(bowl.Inngs['ovrs']),
        'runs': int(bowl.Inngs['r']),
        'wickets': int(bowl.Inngs['wkts'])
    }

    return {'batting': batting, 'bowling': bowling}


def _parse_score(score_element):
    """Get the score info (as a list of inningses)"""
    # an innings should be 3 elements
    children = [child for child in score_element.children if child != '\n']
    first_innings = children[:3]
    score = _parse_innings(*first_innings)
    if children[3:]:
        score.append(_parse_innings(*children[3:]))
    return score


def _parse_single_match(match):
    """Get all the info we can out of one match object and its children"""
    # yapf: disable
    base_keys = [('datapath', 'datapath'),
                 ('id', 'id'),
                 ('inngCnt', 'innings_count'),
                 ('grnd', 'ground'),
                 ('mchDesc', 'description'),
                 ('vcity', 'city'),
                 ('vcountry', 'country'),
                 ('type', 'format'),
                 ('mnum', 'match_num')]
    # yapf: enable
    data = _transfer_dict_keys(base_keys, match, {})
    teams = _get_teams(match)
    if teams:
        data.update(zip(['team_one', 'team_two'], _get_teams(match)))

    # yapf: disable
    state_keys = [('TW', 'toss_won'),
                  ('decisn', 'decision'),
                  ('mchState', 'state'),
                  ('status', 'result_text')]
    # yapf: enable
    state = match.find('state')
    data = _transfer_dict_keys(state_keys, state, data)

    data['time'] = _construct_time(match.find('Tme'))

    score = match.find('mscr')
    if score:
        data['score'] = _parse_score(score)

    return data


def _join_match_group(matches):
    """Stick a bunch of representations of the same match together."""
    data = {}
    for match in matches:
        data.update(_parse_single_match(match))
    return data


def _group_by(key, data):
    """Group a sequence of data by values for a key."""
    groups = collections.OrderedDict()

    for item in data:
        if item[key] not in groups:
            groups[item[key]] = []
        groups[item[key]].append(item)

    return (groups[key] for key in groups)


def _parse_matches(xml_matches):
    """Parse out the matches XML into something more useful
    (& remove duplicates)"""
    xml_tree = BeautifulSoup(xml_matches, 'xml')
    # cricbuzz will duplicate matches with slightly different info sometimes
    matches = _group_by('datapath', xml_tree.find_all('match'))
    matches = [_join_match_group(group) for group in matches]

    return matches


def request_matches(url='http://synd.cricbuzz.com/j2me/1.0/livematches.xml'):
    """Ask cricbuzz what's going on.

    Args:
        url (Optional[str]): url for the request.

    Returns:
        list: a list of objects describing the matches. Should be only one per
            match.
    """
    result = requests.get(url)
    if result.status_code == 200:
        return _parse_matches(result.text)
    else:
        # just throw something for now
        raise ValueError('got a {} from cricbuzz'.format(result.status_code))


if __name__ == '__main__':
    # dirty little test
    import json
    matches = request_matches()
    for m in matches:
        m['time'] = m['time'].strftime('%G-%m-%dT%H:%M:%S%z')
        print(json.dumps(m, indent=2))
