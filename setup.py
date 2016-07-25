from setuptools import setup
from os import path

def read(fname):
    return open(path.join(path.dirname(__file__), fname)).read()

setup(
    name='pythorrent',
    version='0.1a',
    description=read("README.md"),
    author='Matt Copperwaite',
    author_email='mattcopp@gmail.com',
    url='https://github.com/yamatt/python-pthorrent',
    packages=[
        'pythorrent',
    ],
    license="AGPLv3",
    test_suite="tests",
    install_requires=read("requirements.txt").split()
)
