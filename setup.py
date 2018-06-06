import os
import codecs
import versioneer
from setuptools import setup, find_packages

HERE = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    with codecs.open(os.path.join(HERE, *parts), 'rb', 'utf-8') as f:
        return f.read()


setup(
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    name='fugue',
    description='Contrapuntal composition for HTTP',
    license='Expat',
    url='https://github.com/jonathanj/fugue',
    author='Jonathan Jacobs',
    author_email='jonathan@jsphere.com',
    maintainer='Jonathan Jacobs',
    maintainer_email='jonathan@jsphere.com',
    long_description=read('README.rst'),
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    zip_safe=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries :: Python Modules',
        ],
    install_requires=[
        'Twisted[tls]>=15.5.0',
        'pyrsistent>=0.14.2',
        'hyperlink>=18.0.0',
        'multipart>=0.1',
        'eliot>=1.3.0',
        ],
    extras_require={
        'test': [
            'Nevow>=0.14.3',
            'testrepository>=0.0.20',
            'testtools>=2.3.0',
            ],
        },
    )
