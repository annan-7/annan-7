import collections
import datetime
import json
import os
import pathlib
import urllib.request

TOKEN = os.environ['PROFILE_TOKEN']
OWNER = os.environ.get('PROFILE_OWNER', 'annan-7')
PRIVATE = os.environ.get('PRIVATE_STATS') == 'true'

def api(path, data=None):
    url = path if path.startswith('https://api.github.com/') else 'https://api.github.com' + path
    request = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
        headers={'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json', 'User-Agent': 'profile-stats'})
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if isinstance(result, dict) and result.get('errors'):
        raise RuntimeError('GitHub GraphQL query failed; check token permissions')
    return result

def generate():
    repos = []
    for page in range(1, 10000):
        endpoint = f'/user/repos?affiliation=owner&per_page=100&page={page}' if PRIVATE else f'/users/{OWNER}/repos?type=owner&per_page=100&page={page}'
        batch = api(endpoint)
        repos.extend(r for r in batch if r['owner']['login'].lower() == OWNER.lower())
        if len(batch) < 100:
            break
    languages = collections.Counter()
    for repo in repos:
        if not repo['fork']:
            languages.update(api(repo['languages_url']))
    query = '''query($login:String!){user(login:$login){contributionsCollection{totalCommitContributions totalIssueContributions totalPullRequestContributions totalPullRequestReviewContributions restrictedContributionsCount contributionCalendar{totalContributions}}}}'''
    stats = api('/graphql', {'query': query, 'variables': {'login': OWNER}})['data']['user']['contributionsCollection']
    scope = 'Repositorios propios accesibles al token (públicos y privados)' if PRIVATE else 'Repositorios públicos propios'
    rows = ['<!-- STATS:START -->', f'**Alcance:** {scope}.', '', '| Actividad | Total |', '|:---|---:|',
        f'| Repositorios | {len(repos)} |',
        f"| Commits de contribución · últimos 12 meses | {stats['totalCommitContributions']} |",
        f"| Contribuciones · últimos 12 meses | {stats['contributionCalendar']['totalContributions']} |", '',
        '**Lenguajes por volumen de código** · repositorios propios, sin forks.', '', '| Lenguaje | Proporción |', '|:---|---:|']
    total = sum(languages.values())
    for language, size in languages.most_common(10):
        rows.append(f'| {language.replace(chr(124), "")} | {size / total:.1%} |')
    rows += ['', 'Los commits siguen las reglas del gráfico de contribuciones de GitHub; no representan todos los commits históricos ni todas las ramas.', '',
        'Actualizado: ' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), '<!-- STATS:END -->']
    path = pathlib.Path('README.md')
    text = path.read_text()
    start, end = '<!-- STATS:START -->', '<!-- STATS:END -->'
    assert text.count(start) == text.count(end) == 1
    path.write_text(text.split(start)[0] + '\n'.join(rows) + text.split(end)[1])

if __name__ == '__main__':
    generate()
