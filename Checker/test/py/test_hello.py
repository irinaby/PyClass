import random

print("hello")
with open("output.txt", "w") as f:
    f.write(input())
#print(input())

if random.randint(0, 10) == 0:
    raise Exception("Странная ошибка")