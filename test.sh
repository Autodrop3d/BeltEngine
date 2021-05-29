rm output.gcode
#rm output1.gcode

python3 -m belt_engine.BeltEngine -x belt_engine/bin/armLinux/CuraEngine -o output.gcode model.stl -c belt_engine/settings/CR30.cfg.ini  -s support_enable=True 
#cat settings/start.gcode output.gcode settings/end.gcode > output1.gcode

#diff output1.gcode output4.gcode 
