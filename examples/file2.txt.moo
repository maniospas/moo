/*** moo.safe += pattern {moo.python} scripts/* ***/
/*** b64 = str system {moo.python} scripts/b64.py ***/
/*** b64 ***/

Encoding with python (mime version
/*** do {b64} examples/lettuce.png ***/

Encoding with self
/*** base64.encode.text {file.read examples/lettuce.png} ***/

Encoding with curry pattern
/*** base64.encode.text {...} file.read examples/lettuce.png ***/

Encoding with curry and mime
/*** base64.encode.mime {...} file.read examples/lettuce.png ***/

Encoding raw
/*** base64.encode.text {...} file.raw examples/lettuce.png ***/
