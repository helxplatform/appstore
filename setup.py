#!/usr/bin/env python

import setuptools

def parse_requirements(filename):
    with open(filename, "r") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

setuptools.setup(
    name="appstore",
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=parse_requirements("requirements.txt"),
)