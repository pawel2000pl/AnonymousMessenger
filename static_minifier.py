import re
from sys import argv

filename = argv[1]

with open(filename, 'r') as f: content = f.read()

content = re.sub('(\s+)$', ' ', content)
content = re.sub('^(\s+)', ' ', content)
content = re.sub('\s{2,}', ' ', content)
while "\n\n" in content:
    content = content.replace("\n\n", "\n")
    
with open(filename, 'w') as f: f.write(content)
