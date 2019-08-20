import os
import re

SEPARATORS = r'[-\s\.]'


def handle(folder, language=True, dry_run=True):
    parsed = dict()
    for file_name in os.listdir(folder):
        full_name = '/'.join([folder, file_name])
        if os.path.isdir(full_name):
            m = re.search(r'S\d+', file_name)
            if m:
                new_name = '/'.join([folder, m.group()])
                if new_name != full_name:
                    print('Renaming "{}" to "{}"...'.format(full_name, new_name))
                    if not dry_run:
                        os.rename(full_name, new_name)
                        full_name = new_name

            handle(full_name, dry_run=dry_run)
        else:
            ext = file_name.split('.')[-1]
            name = '.'.join(file_name.split('.')[:-1])
            pattern = '{separator}'.join([r'(?P<name>.*)',
                                          r'[sS](?P<season>\d+)[eE](?P<episode>\d+)({separator}(?P<title>.*))?',
                                          r'(?P<resolution>\d+[pP])({separator}(?P<source>.*))?',
                                          r'(?P<rip>[xXhH]\.?26[45])',
                                          r'(?P<group>.*)'])
            pattern = pattern.format(separator=SEPARATORS)
            match = re.match(pattern, name)
            if not match:
                raise ValueError('Cannot match %s', file_name)
            sections = match.groupdict()
            sections['folder'] = folder
            sections['filename'] = '/'.join([folder, file_name])
            parsed.setdefault(sections['season'], dict()).setdefault(sections['episode'], dict())[ext] = sections

    organize(parsed, language=language, dry_run=dry_run)


def organize(parsed, language=True, dry_run=True):
    ret = dict()
    for season, episodes in parsed.items():
        for episode, files in episodes.items():
            if 'mkv' in files:
                rename(files, language=language, dry_run=dry_run)
    return ret


def rename(files, language=True, dry_run=True):
    get_new_name(files, language=language)

    for ext, definitions in files.items():
        old = definitions['filename']
        new = definitions['new_name']

        if new != old:
            print('Renaming "{}" to "{}"...'.format(old, new))
            if not dry_run:
                os.rename(old, new)


def get_new_name(files, language=True):
    sections = dict()
    mkv = files['mkv']
    for key, value in mkv.items():
        if key != 'filename':
            if not value:
                value = get_value_from_subtitles(files, key)
            sections[key] = capitalize(key, value)

    parts = [sections['name'],
             'S{}E{}'.format(sections['season'], sections['episode']),
             sections['title'],
             sections['resolution'],
             sections['rip']]
    parts = [p for p in parts if p]
    new_name = '.'.join(parts)
    new_name = '-'.join([new_name, sections['group']])

    for ext, definitions in files.items():
        fullname = new_name

        if language and ext != 'mkv':
            language = definitions['filename'].split('.')[-2]
            if language in ['chs', 'cht', 'chs&eng', 'cht&eng', 'eng']:
                fullname = '.'.join([new_name, language])

        fullname = '.'.join([fullname, ext])

        definitions['new_name'] = '/'.join([definitions['folder'], fullname])


def get_value_from_subtitles(files, key):
    for ext, sub in files.items():
        if ext != 'mkv' and sub.get(key):
            return sub[key]


def capitalize(key, value):
    if value:
        words = []
        for word in re.split(SEPARATORS, value):
            if not re.match('\(\d+\)', word):  # Ignore stuff like '(1)'
                if key == 'resolution':
                    word = word.lower()
                elif key in ['name', 'title']:
                    if word.lower() in ['in', 'as', 'of']:
                        word = word.lower()
                    else:
                        word = word.capitalize()
                elif key == 'rip':
                    if word.lower().startswith('x26'):
                        word = word.lower()
                    elif word.upper().startswith('H.'):
                        word = word.upper()
                words.append(word)
        return '.'.join(words)


def main():
    folder = r"Y:\TV Shows\Marvel's Agents of S.H.I.E.L.D"
    os.chdir(folder)

    handle(folder, language=True, dry_run=True)


if __name__ == '__main__':
    main()