#!/usr/bin/env python

from setuptools import setup

setup(
    name='blobs',
    version='0.0.0',
    description="Analysis for gray scale images containing gaussian blobs",
    license='GPL-3',
    author='Michael Davidsaver',
    author_email='mdavidsaver@gmail.com',
    url='https://github.com/mdavidsaver/blobs',
    python_requires='>=2.7',

    packages=[
        'blobs',
        'blobs.test',
    ],
    install_requires = [
        'scipy',
        'nose',
    ],
    zip_safe = True,

    classifiers = [
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'License :: Freely Distributable',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',
    ],
    keywords='image fitting',
)
