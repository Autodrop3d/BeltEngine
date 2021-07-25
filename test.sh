rm output.gcode
ls
belt-engine -o ./output.gcode model.stl -c ./belt_engine/settings/CR30.cfg.ini  -s support_enable=True -v
ls

