def createcounter():
    s = 0
    def counter():
        nonlocal s
        s += 1
        return s
    return counter

c1 = createCounter()
print(c1(), c1())
c2 = createCounter()
print(c2(), c2())
