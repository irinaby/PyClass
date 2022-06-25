import json
import random
import requests
import time

def make_samples() -> list:
    samples = []
    for i in range(1, 10):
        samples.append(str(random.randint(1, 1000)) + " " + str(random.randint(1, 1000)))
    return samples

def test(lang: str, testee_filename: str, checker_filename: str) -> dict:
    data = {
        "language": lang
    }

    data["timeout"] = 2
    data["checker_timeout"] = 4
    data["mem_limit"] = "100m"

    with open(testee_filename, "r") as f:
        data["testee"] = f.read()
    with open(checker_filename, "r") as f:
        data["checker"] = f.read()
    data["samples"] = make_samples()

    return data


def test_py(testee_filename: str, checker_filename: str) -> dict:
    return test("py", testee_filename, checker_filename)

def test_cs(testee_filename: str, checker_filename: str) -> dict:
    return test("cs", testee_filename, checker_filename)

#data = test_py("test_summa_user.py", "test_summa_check.py")
data = test_cs("cs/summa_user.cs", "cs/summa_check.cs")
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
