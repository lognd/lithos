; flagship-1 FDM print plan (marlin dialect), WO-67 fixture
; envelope-checks against a printer machine record
G21
G90
G28
G0 X10 Y10 Z0.2 F3000
G1 X10 Y10 Z0.2 E0 F1500
G1 X100 Y10 E5.2 F1200
G1 X100 Y100 E10.4
G1 X10 Y100 E15.6
G1 X10 Y10 E20.8
G0 Z1 F3000
M104 S0
M84
