import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="NERDA_Con", 
    version="0.0",
    author="Supriti Vijay, Aman Priyanshu",
    author_email="supriti.vijay@gmail.com",
    description="Extending NERDA Library for Continual Learning",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SupritiVijay/NERDA-Con",
    packages=setuptools.find_packages(where='src'),
    package_dir={'': 'src'},
    python_requires='>=3.6',
    install_requires=[
        'torch',
        'transformers',
        'sklearn',
        'nltk',
        'pandas',
        'progressbar',
        'pyconll'
    ],
    setup_requires=['pytest-runner'],
    tests_require=['pytest',
                   'pytest-cov'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
    include_package_data=True
    )
