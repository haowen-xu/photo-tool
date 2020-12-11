import os
import sys

__all__ = ['get_font']


def get_font(family: str) -> str:
    if sys.platform == 'darwin':
        search_dirs = [
            '/System/Library/Fonts',
            os.path.expanduser('~/Library/Fonts')
        ]
    else:
        raise RuntimeError(f'Not supported platform: {sys.platform}')

    search_names = [n.strip() for n in family.split(',') if n.strip()]
    search_exts = ('.otf', '.ttf', '.ttc')

    def traverse_dir(search_dir, search_name):
        # for name in search_names:
        for ext in search_exts:
            path = os.path.join(search_dir, f'{search_name}{ext}')
            if os.path.isfile(path):
                return path

        for subdir in os.listdir(search_dir):
            path = os.path.join(search_dir, subdir)
            if os.path.isdir(path):
                r = traverse_dir(path, search_name)
                if r is not None:
                    return r

    for search_name in search_names:
        for search_dir in search_dirs:
            r = traverse_dir(search_dir, search_name)
            if r is not None:
                return r

    raise IOError(f'Font not found: {family}')
