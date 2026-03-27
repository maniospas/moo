🐮 moo.safe += str rm tests
🐮 moo.safe += str rm examples/
🐮 moo.safe += str {moo.python} moo.py examples/
🐮 schedule rm tests

🐮 print Running tests
🐮 system {moo.python} moo.py examples/hello.txt.moo --nocolor
🐮 str {for i=range 1 8: system {moo.python} moo.py examples/file{i}.txt.moo --nocolor}

🐮 print Cleanup 
🐮 system rm examples/hello.txt
🐮 str{for i=range 1 8: system rm examples/file{i}.txt}
