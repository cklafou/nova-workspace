TOOL={"name":"zzmeasure","description":"count lines in a file","params":{"path":"file"}}
def run(**a):
    import pathlib
    p=pathlib.Path(a.get("path",""))
    return f"{len(p.read_text(errors='replace').splitlines())} lines" if p.exists() else "ERROR: no such file"
