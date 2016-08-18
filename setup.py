from setuptools import setup
from os import path

def read(fname):
    return open(path.join(path.dirname(__file__), fname)).read()

setup(
    name='PYTHorrent',
    version='0.1',
    description="A BitTorrent client written entirely in Python so "\
        "that you can get to the depths of the protocol",
    long_description=read("README.rst"),
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
