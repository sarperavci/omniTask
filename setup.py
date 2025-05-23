from setuptools import setup, find_packages

setup(
    name="omniTask",
    version="0.3.0",
    packages=find_packages(),
    install_requires=[],
    author="SARPER AVCI",
    author_email="sarperavci20@gmail.com",
    description="A powerful Python-based workflow automation tool",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/sarperavci/omniTask",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8"
) 