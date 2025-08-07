# Configuration file for the Sphinx documentation builder.

import os
import sys

# -- Path setup --------------------------------------------------------------
# Add the parent directory to the path so we can import pytanque
sys.path.insert(0, os.path.abspath('..'))

# -- Project information -----------------------------------------------------
project = 'Pytanque'
copyright = '2025, Pytanque Contributors'
author = 'Pytanque Contributors'

# The full version, including alpha/beta/rc tags
release = '0.2.0'

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.linkcode',
    'sphinx.ext.intersphinx',
    'myst_parser',
    'numpydoc',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
html_theme = 'furo'
html_static_path = ['_static']

# HTML title
html_title = "Pytanque Documentation"

# Add custom links to the header
html_logo = None

# Furo theme options
html_theme_options = {
    "source_repository": "https://github.com/llm4rocq/pytanque",
    "source_branch": "PetanqueV2",
    "source_directory": "docs/",
    "navigation_with_keys": True,
    "top_of_page_button": "edit",
    "sidebar_hide_name": False,
    "light_css_variables": {
        "color-brand-primary": "#2563eb",
        "color-brand-content": "#2563eb",
    },
    "dark_css_variables": {
        "color-brand-primary": "#60a5fa",
        "color-brand-content": "#60a5fa",
    },
    "announcement": None,
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/llm4rocq/pytanque",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        },
    ],
}

# Add external links to the navigation
html_context = {
    "default_mode": "light"
}

# -- Extension configuration -------------------------------------------------

# Numpydoc settings
numpydoc_show_class_members = False
numpydoc_show_inherited_class_members = False
numpydoc_class_members_toctree = False

# Autodoc settings
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
    'special-members': '__init__',
}

# Prevent double colons in section headers
autodoc_typehints = 'description'
autodoc_typehints_description_target = 'documented'

# Autosummary settings
autosummary_generate = True

# Intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

# MyST parser settings
myst_enable_extensions = [
    'colon_fence',
    'deflist',
    'dollarmath',
    'fieldlist',
    'html_admonition',
    'html_image',
    'linkify',
    'replacements',
    'smartquotes',
    'strikethrough',
    'substitution',
    'tasklist',
]

# Linkcode configuration - make [source] buttons link to GitHub
def linkcode_resolve(domain, info):
    if domain != 'py':
        return None
    if not info['module']:
        return None
    
    import importlib
    import inspect
    
    filename = info['module'].replace('.', '/')
    base_url = f"https://github.com/llm4rocq/pytanque/blob/PetanqueV2/{filename}.py"
    
    try:
        # Import the module
        mod = importlib.import_module(info['module'])
        
        # Get the object by traversing the attribute path
        obj = mod
        parts = info['fullname'].split('.')
        
        # The fullname contains the class and method names, not the module name
        # So we don't skip any parts - we traverse the full path
        for attr_name in parts:
            if hasattr(obj, attr_name):
                obj = getattr(obj, attr_name)
            else:
                return base_url
        
        # Try to get the source lines and line number
        try:
            source_lines, start_lineno = inspect.getsourcelines(obj)
            # Only return a line number if it's actually useful (not 0)
            if start_lineno > 0:
                return f"{base_url}#L{start_lineno}"
            else:
                return base_url
        except (OSError, TypeError):
            # If we can't get source lines, try to get line number another way
            try:
                if hasattr(obj, '__code__'):
                    lineno = obj.__code__.co_firstlineno
                    if lineno > 0:
                        return f"{base_url}#L{lineno}"
            except:
                pass
            return base_url
            
    except (ImportError, AttributeError):
        return base_url