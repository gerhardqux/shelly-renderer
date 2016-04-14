from distutils.core import setup
setup(name='shelly',
      description='Render shell-like scripts into salt states',
      author='Gerhard Muntingh',
      version='0.1',
      package_dir={'': '_renderers'},
      py_modules=['shelly'],
      )
