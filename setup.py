#!/usr/bin/env python
from os import environ

try:
    from setuptools import setup
except ImportError:
    from distutils import setup

version = '0.2'

setup(
        name='zsnapper',
        version=str(version),
        description="ZFS snapshot manager",
        author="Fredrik Eriksson",
        author_email="zsnapper@wb9.se",
        url="https://github.com/fredrik-eriksson/zsnapper",
        platforms=['any'],
        license='BSD',
        packages=['zsnaplib'],
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Environment :: Console',
            'Intended Audience :: System Administrators',
            'License :: OSI Approved :: BSD License',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 3',
            'Topic :: Utilities',
            ],
        keywords='zfs snapshot backup',
        scripts=['bin/zsnapper']
        )
