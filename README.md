# Kattis Problem Solving Script
This is a simple script useful when solving Kattis problems.

`ct new blah` creates a new folder named `blah` containing your template, downloads the Kattis samples for the problem, and opens the template in Vim.

`ct test` tests your submission on the samples.

`ct submit` submits the code, and shows you its progress.

To install, copy the `contestrc` file to `~/.contestrc`, and configure it with your settings.
Then, add `source path/to/contest_tools/ctalias` in one of your shell startup files.
The Python script may require a bunch of dependencies you don't have installed.
