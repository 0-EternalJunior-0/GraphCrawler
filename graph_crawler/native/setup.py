"""Build script for native Cython extensions.

Usage:
    cd graph_crawler/native
    python setup.py build_ext --inplace

    # Or install in development mode:
    pip install -e .

Cross-platform notes:
    - .so files are platform-specific (Linux)
    - .pyd files are for Windows
    - .dylib files are for macOS
    - Always rebuild on target platform!
"""

import os
import platform

from setuptools import Extension, setup

# Try to import Cython
try:
    from Cython.Build import cythonize
    USE_CYTHON = True
except ImportError:
    USE_CYTHON = False
    print("WARNING: Cython not found. Install with: pip install cython>=3.0.0")
    print("Building from pre-generated C files if available...")

# Platform detection
PLATFORM = platform.system().lower()
ARCH = platform.machine()
print(f"Building for: {PLATFORM} ({ARCH})")

# Extension modules
extensions = []

if USE_CYTHON:
    # Build from .pyx files
    extensions = cythonize(
        [
            Extension(
                "graph_crawler.native._url_utils",
                ["url_utils.pyx"],
            ),
            Extension(
                "graph_crawler.native._html_parser",
                ["html_parser.pyx"],
            ),
            Extension(
                "graph_crawler.native._bloom_filter",
                ["bloom_filter.pyx"],
            ),
        ],
        compiler_directives={
            'language_level': 3,
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
        }
    )
else:
    # Build from pre-generated .c files (if available)
    if os.path.exists('url_utils.c'):
        extensions.append(
            Extension(
                "graph_crawler.native._url_utils",
                ["url_utils.c"],
            )
        )
    if os.path.exists('html_parser.c'):
        extensions.append(
            Extension(
                "graph_crawler.native._html_parser",
                ["html_parser.c"],
            )
        )
    if os.path.exists('bloom_filter.c'):
        extensions.append(
            Extension(
                "graph_crawler.native._bloom_filter",
                ["bloom_filter.c"],
            )
        )

setup(
    name="graphcrawler-native",
    version="1.0.1",
    description="Native Cython extensions for GraphCrawler",
    ext_modules=extensions,
    python_requires=">=3.11",
    install_requires=[
        "mmh3>=3.0.0",  # Required for BloomFilter (MurmurHash3)
    ],
    extras_require={
        "build": ["cython>=3.0.0", "setuptools>=65.0.0", "wheel"],
    },
)
