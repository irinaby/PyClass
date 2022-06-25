from globals import *

class CheckJsonException(ValueError):
    def __init__(self, message: str) -> None:
        self.message = message

def check_object(options: dict, name: str) -> None:
    if not options.get(name):
        raise CheckJsonException("Need " + name + " object, but not found")

def check_prop(options: dict, name: str) -> None:
    if not options.get(name):
        raise CheckJsonException("Need " + name + " property, but not found")

def check_source(options: dict, name: str) -> None:
    check_object(options, name)
    source = options[name]
    check_prop(source, LANGUAGE)
    check_prop(source, SOURCE)

def check(options: dict) -> None:
    check_source(options, TESTEE)
    check_source(options, CHECKER)
    check_object(options, SAMPLES)
