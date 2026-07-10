(pillow_block op10 -- broken: never cuts down to the target floor, WO-67 fixture)
G21 G90 G17
T1 M6 (6mm 4-flute end mill)
G0 X10 Y10 Z5
G1 Z-1 F200
G1 X40 Y10 F800
G1 X40 Y40
G1 X10 Y40
G1 X10 Y10
G0 Z5
M30
