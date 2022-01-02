# BeltEngine
A commandline slicer for belt-style printers utilising CuraEngine.

Ported code from blackbelt slicer by FieldOfView

## Installation

### Raspbian/Ubuntu/Debian

```bash
sudo apt update
sudo apt install \
  libgeos-dev \
  libblas-dev \
  liblapack-dev \
  gfortran \
  libjpeg-dev \
  zlib1g-dev

wget https://github.com/Autodrop3d/BeltEngine/raw/main/dist/belt-engine-0.1.3.tar.gz
pip3 install ./belt-engine-0.1.3.tar.gz
```

### Other OSs

The suggested way to install BeltEngine is via Pip however you may need to install additional dependencies in order to get the pip install to succeed.

```bash
wget https://github.com/Autodrop3d/BeltEngine/raw/main/dist/belt-engine-0.1.3.tar.gz
pip3 install ./belt-engine-0.1.3.tar.gz
```

**Help Wanted:**  Please submit a pull request to update these docs if you install BeltEngine on an OS that is not yet documented!


## Building the Pip Package

**Warning:**  This is for developers only. Normally you will not need to do this.

1) Install poetry in system,
2) cd into the project directly and create venv using `python3 -m venv venv`
3) Activate virtualenv with `source venv/bin/activate`
4) Run poetry install (this will install development version as executable in the virtualenv. That means you can just change the code and run `belt-engine` and changes will take effect. Usefull for development). I did not test this in rpi (YMMV)
5) Change the version in pyproject file.
6) Run `poetry build`. This will create packages inside `dist` folder.
  ```bash
  curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3 -
  source $HOME/.poetry/env
  python3 -m venv venv
  source venv/bin/activate
  poetry build
  cd dist
  ```


## Usage
It is recommended to use the script from a python virtual environment. The virtual environment can be created like this:
```
python3 -m virtualenv ./venv
venv/scripts/activate
```
On Windows, use the following:
```
python -m virtualenv ./venv
venv\Scripts\activate
```

To install the dependencies on Linux, you may need to install libspatialindex with `sudo apt install libspatialindex-dev`. Once that is available, the Python requirements can be installed directly using pip.
```
(venv) pip install -r requirements.txt
```

On Windows, it is easier to install some python wheels manually from https://www.lfd.uci.edu/~gohlke/pythonlibs/:
numpy, scipy, Rtree, Shapely, Pillow, lxxml
The rest of the python dependencies can be installed using the same pip command as above.

The basic usage of the script is as follows:
```
(venv) python3 -m belt_engine.BeltEngine -o output.gcode model.stl
```
This uses the settings defined in the .def.json files in the `resources/definitions` folder.

Setting values can be specified in configuration files, or directly on the command-line.

### Configuration files
Basic syntax:
```
(venv) python BeltEngine.py -o output.gcode model.stl -c default.ini
```

Contents of `default.ini`:
```
machine_width = 300
machine_depth = 300
layer_height = 0.15
```

Multiple configuration files can be specified, eg:
```
(venv) python BeltEngine.py -o output.gcode model.stl -c default.ini -c petg.ini
```
This way a default profile for a a certain printer type can be created with a smaller profile with just the changes to that printer type needed to print with a certain material.

Configuration files are read "in order", so setting for which values are specified both in default.ini and in petg.ini use the value from petg.ini

### Command-line values:
Basic syntax:
```
(venv) python BeltEngine.py -o output.gcode model.stl -s infill_sparse_density=25 -s support_enable=True
```

Setting values specified on the command line always override what is set in configuration files, even if those configuration files are specified after the command-line value.

## Example for Blackbelt 3D printer
```
(venv) python BeltEngine.py -o output.gcode model.stl -c settings/blackbelt.cfg.ini -c settings/bb_04mm.cfg.ini -s beltengine_gantry_angle=35 -s support_enable=True
```

### CR30 Example
```angular2html
python3 -m belt_engine.BeltEngine -o ./output.gcode model.stl -c ./belt_engine/settings/CR30.cfg.ini -s support_enable=True -v
```
### normal printer Example
```angular2html
python3 -m belt_engine.BeltEngine -o ./output.gcode model.stl -c ./belt_engine/settings/CR30-verttest.cfg.ini -s support_enable=True -v
```




Development effort sponsored by:
Autodrop3d
Polar3d
