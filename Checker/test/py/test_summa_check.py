import sys

with open("input.txt", "r") as fi:
    line = fi.read()
    s = line.split(" ")
    a = int(s[0])
    b = int(s[1])
    s0 = a + b

    with open("output.txt", "r") as fo:
        s1 = int(fo.read())

        if s0 == s1:
            sys.exit(0)
        else:
            sys.exit(1)
