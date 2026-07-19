TOOL={"name":"zztest","description":"adds two numbers","params":{"a":"int","b":"int"}}
def run(**a): return "sum="+str(int(a.get("a",0))+int(a.get("b",0)))
