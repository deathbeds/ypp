from pathlib import Path
import setuptools

name = "ypp"

__version__ = None

here = Path(__file__).parent

__version__ = "0.0.1"

setup_args = dict(
    name=name,
    version=__version__,
    author="deathbeds",
    author_email="tony.fast@gmail.com",
    description="A kernel as an application.",
    long_description=(
        (here / "readme.md").read_text() + "\n\n"
    ),
    long_description_content_type='text/markdown',
    url="https://github.com/deathbeds/ypp",
    python_requires=">=3.6",
    license="BSD-3-Clause",
    setup_requires=[],
    tests_require=['nbval'],
    install_requires=[
        "IPython", "pyld", "jsonschema", "jsonpatch", "jsondiff"
    ],
    extras_require={'i': ['ipywidgets']},
    include_package_data=True,
    py_modules=['ypp', 'maus'],
    classifiers=(
        "Development Status :: 4 - Beta",
        "Framework :: IPython",
        "Framework :: Jupyter",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",),
    zip_safe=False,
)

if __name__ == "__main__":
    setuptools.setup(**setup_args)
