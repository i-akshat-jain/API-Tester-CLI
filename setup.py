"""
Setup configuration for API Tester CLI
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read PyPI description (concise version)
pypi_readme_file = Path(__file__).parent / "README_PYPI.md"
if not pypi_readme_file.exists():
    # Fallback to full README if PyPI version doesn't exist
    pypi_readme_file = Path(__file__).parent / "README.md"
long_description = pypi_readme_file.read_text(encoding='utf-8') if pypi_readme_file.exists() else ""

setup(
    name="apitest-cli",
    version="1.0.0",
    description="Automate OpenAPI/Swagger API testing from the command line - Test your entire API in seconds",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Akshat Jain",
    author_email="akshatjain1502@gmail.com",
    url="https://github.com/i-akshat-jain/API-Tester-CLI",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "requests>=2.28.0",
        "pyyaml>=6.0",
        "jsonschema>=4.0.0",
        "rich>=13.0.0",
        "keyring>=24.0.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "apitest=apitest.cli:main",
        ],
    },
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Utilities",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    keywords="api testing openapi swagger cli automation testing tools rest api validator",
    project_urls={
        "Bug Reports": "https://github.com/i-akshat-jain/API-Tester-CLI/issues",
        "Source": "https://github.com/i-akshat-jain/API-Tester-CLI",
        "Documentation": "https://github.com/i-akshat-jain/API-Tester-CLI#readme",
    },
)

