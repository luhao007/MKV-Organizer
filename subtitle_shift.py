import os
import datetime


def adjust_time(file_name, td, dry_run=True):

    try:
        with open(file_name, 'r', encoding="utf-8") as f:
            f.readline()
        encoding = "utf-8"
    except UnicodeError:
        try:
            with open(file_name, 'r', encoding="utf-16") as f:
                f.readline()
            encoding = "utf-16"
        except UnicodeError:
            encoding = None # Use system default

    with open(file_name, 'r', encoding=encoding) as f:
        lines = f.readlines()
        new_lines = []
        for line in lines:
            if file_name.endswith('.ass') and line.startswith('Dialogue:'):
                for t in line.split(',')[1:3]:
                    nt = datetime.datetime.strptime(t, '%H:%M:%S.%f')
                    nt += td
                    nt = nt.strftime('%H:%M:%S.%f')[1:-4]
                    line = line.replace(t, nt)
            elif file_name.endswith('.srt'):
                if '-->' in line:
                    for t in line.strip().split(' --> '):
                        nt = datetime.datetime.strptime(t, '%H:%M:%S,%f')
                        nt += td
                        nt = nt.strftime('%H:%M:%S,%f')[:-3]
                        line = line.replace(t, nt)
                line = line.replace('{\\an4}', '').replace('{\\an8}', '')

            new_lines.append(line)

    with open(file_name+'.tmp' if dry_run else file_name, 'w', encoding=encoding) as f:
        f.writelines(new_lines)

    print('Modified {0}'.format(file_name))

def main():
    folder = r"Y:\TV Shows\Marvel's Agents of S.H.I.E.L.D\S04"
    for f in os.listdir(folder):
        if f.endswith('.ass') or f.endswith('.srt'):
            adjust_time('\\'.join([folder, f]), datetime.timedelta(seconds=1), True)

if __name__ == '__main__':
    main()