def f():
    try:
        risky()
    except Exception:
        pass
def g():
    try:
        risky()
    except:
        pass
def h():
    try:
        risky()
    except Exception as e:
        print("handled", e)
