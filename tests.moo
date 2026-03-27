🐮 moo.safe += str rm tests
🐮 moo.safe += pattern rm examples/*
🐮 moo.safe += pattern {moo.python} moo.py examples/*
🐮 schedule rm tests

🐮 print Running tests
🐮 system {moo.python} moo.py examples/hello.txt.moo --nocolor
🐮 for i=range 1 9: system {moo.python} moo.py examples/file{i}.txt.moo --nocolor

🐮 print Cleanup 
🐮 system rm examples/hello.txt
🐮 for i=range 1 9: system rm examples/file{i}.txt
