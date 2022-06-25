import json
import random
import requests
import time

def make_samples() -> list:
    samples = []
    for i in range(1, 10):
        samples.append(str(random.randint(1, 1000)) + " " + str(random.randint(1, 1000)))
    return samples

def test(lang: str, filename: str) -> dict:
    data = {
        "language": lang,
        "timeout": 2,
        "mem_limit": "100m"
    }
    with open(filename, "r") as f:
        data["source"] = f.read()

    return data


def test_py(testee_filename: str, checker_filename: str) -> dict:
    return {
        "testee": test("py", testee_filename),
        "checker": test("py", checker_filename),
        "samples": make_samples()
    }

def test_cs(testee_filename: str, checker_filename: str) -> dict:
    return {
        "testee": test("C#", testee_filename),
        "checker": test("C#", checker_filename),
        "samples": make_samples()
    }

def test_c(testee_filename: str, checker_filename: str) -> dict:
    return {
        "testee": test("c", testee_filename),
        "checker": test("py", "py/test_summa_check.py"),
        "samples": make_samples()
    }

data = test_c("c/testee.c", "c/checker.c")
#data = test_py("py/test_summa_user.py", "py/test_summa_check.py")
#data = test_cs("cs/summa_user.cs", "cs/summa_check.cs")
# with open("data_cs.json", "w") as f:
#     json.dump(data, f)
payload = json.dumps(data)# + "--"
start = time.perf_counter()
#r = requests.post("http://192.168.0.22:3356", data=payload)
r = requests.post("http://localhost:3356", data=payload)
print(time.perf_counter() - start)
print(r.status_code, r.reason)
print(r.text)
try:
    d = json.loads(r.text)
    print(d["result"])
    print(d["output"])
except Exception as e:
    print(e)
