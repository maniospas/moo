/**/ print Preparing tests
/**/ moo.safe += str rm tests
/**/ moo.safe += pattern rm examples/*
/**/ moo.safe += pattern {moo.run} examples/*
/**/ moo.safe += pattern {moo.run} docs/*
/**/ schedule rm tests

/**/ print Running tests
/**/ system {moo.run} examples/hello.txt.moo --nocolor
/**/ for i = range 1 9: system {moo.run} examples/file{i}.txt.moo --nocolor

/**/ print Building docs
/**/ system {moo.run} docs/index.html.moo

/**/ print Cleanup
/**/ system rm examples/hello.txt
/**/ for i = range 1 9: system rm examples/file{i}.txt