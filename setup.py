import ast
import codecs
import os
import re
import sys
from setuptools import setup, find_packages


_version_re = re.compile(r'__version__\s+=\s+(.*)')
_source_dir = os.path.split(os.path.abspath(__file__))[0]

if sys.version_info[0] == 2:
    def read_file(path):
        with open(path, 'rb') as f:
            return f.read()
else:
    def read_file(path):
        with codecs.open(path, 'rb', 'utf-8') as f:
            return f.read()

version = str(ast.literal_eval(_version_re.search(
    read_file(os.path.join(_source_dir, 'photo_tool/__init__.py'))).group(1)))

requirements_list = list(filter(
    lambda v: v and not v.startswith('#'),
    (s.strip() for s in read_file(
        os.path.join(_source_dir, 'requirements.txt')).split('\n'))
))
dependency_links = [s for s in requirements_list if s.startswith('git+')]
install_requires = [s for s in requirements_list if not s.startswith('git+')]


setup(
    name='photo-tool',
    version=version,
    url='https://github.com/haowen-xu/photo-tool/',
    license='MIT',
    author='Haowen Xu',
    author_email='haowen.xu@outlook.com',
    description='A set of utilities to process photos.',
    long_description=__doc__,
    packages=find_packages('.', include=['photo_tool', 'photo_tool.*']),
    zip_safe=False,
    platforms='any',
    setup_requires=['setuptools'],
    install_requires=install_requires,
    dependency_links=dependency_links,
    entry_points='''
        [console_scripts]
        watermark.py=photo_tool.watermark:main
    '''
)
