/**/ moo.safe += const rm tests
/**/ moo.safe += const rm examples/
/**/ moo.safe += const {moo.python} moo.py examples/
/**/ schedule rm tests

/**/ system {moo.python} moo.py examples/hello.txt.moo --nocolor
/**/ system {moo.python} moo.py examples/file1.txt.moo --nocolor
/**/ system {moo.python} moo.py examples/file2.txt.moo --nocolor
/**/ system {moo.python} moo.py examples/file3.txt.moo --nocolor
/**/ system {moo.python} moo.py examples/file4.txt.moo --nocolor
/**/ system {moo.python} moo.py examples/file5.txt.moo --nocolor
/**/ system {moo.python} moo.py examples/file6.txt.moo --nocolor

/**/ system rm examples/hello.txt
/**/ system rm examples/file1.txt
/**/ system rm examples/file2.txt
/**/ system rm examples/file3.txt
/**/ system rm examples/file4.txt
/**/ system rm examples/file5.txt
/**/ system rm examples/file6.txt
