from setuptools import setup, find_packages

setup(
    name="osm_importer",
    version="1.0.0",
    description="OSM Importer for Transport Fever 2",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/your-repo/osm-importer",  # Replace with your repository URL
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "certifi==2024.7.4",
        "geographiclib==2.0",
        "geopy==2.3.0",
        "luadata==1.0.0",
        "lupa==1.10",
        "lxml==4.9.2",
        "networkx==3.0",
        "osmread==0.1.2",
        "packaging==23.1",
        "pyparsing==3.0.9",
        "pyproj==3.4.1",
        "python-dateutil==2.8.2",
        "utm==0.7.0",
        "scipy==1.10.1",
        "numpy==1.24.2",
        "tqdm==4.64.1",
    ],
    entry_points={
        "console_scripts": [
            "osm-importer=osm_importer.main:main",  # Entry point for the main script
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
