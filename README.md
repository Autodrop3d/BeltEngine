# BeltEngine
A commandline slicer for belt-style printers utilising CuraEngine

## Usage
Use the script from a python virtual environment
```
python -m virtualenv ./venv
venv/scripts/activate

(venv) pip install -r requirements.txt
(venv) python BeltEngine.py -o output.gcode model.stl
```