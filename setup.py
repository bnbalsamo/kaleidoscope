from setuptools import setup, find_packages


def readme():
    with open("README.md", 'r') as f:
        return f.read()


setup(
    name="kaleidoscope",
    description="An IIIF image server",
    version="0.0.3",
    long_description=readme(),
    author="Brian Balsamo",
    author_email="brian@brianbalsamo.com",
    packages=find_packages(
        exclude=[
        ]
    ),
    include_package_data=True,
    url='https://github.com/bnbalsamo/kaleidoscope',
    install_requires=[
        'flask>0',
        'flask_env',
        'flask_restful',
        'pillow'
    ],
    tests_require=[
        'pytest'
    ],
    test_suite='tests'
)
