import base64
with open('b64.txt') as f:
    data = base64.b64decode(f.read().strip())
with open('run_patch.py', 'wb') as f:
    f.write(data)
