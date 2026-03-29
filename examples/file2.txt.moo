/*** moo.safe += pattern {moo.python} scripts/* ***/
/*** b64 = str system {moo.python} scripts/b64.py ***/
/*** b64 ***/

Encoding with python
/*** do {b64} examples/file1.txt.moo ***/

Encoding with self
/*** base64.encode {file.read examples/file1.txt.moo} ***/

Encoding with curry pattern
/*** base64.encode {...} file.read examples/file1.txt.moo ***/

Encoding raw
/*** base64.encode {...} file.raw examples/file1.txt.moo ***/