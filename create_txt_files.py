import json
import os

with open(r'D:\图书管理\mapping.json', 'r', encoding='utf-8') as f:
    mapping = json.load(f)

dest_dir = r'G:\待整理'
os.makedirs(dest_dir, exist_ok=True)

targets = sorted(list(set(item['clean_name'] for item in mapping)))
print(f'Starting to create {len(targets)} blank TXT files in {dest_dir}...')

created = 0
for target in targets:
    # Target file format specified by user: e.g. MUH-011.mp4.txt
    txt_filename = f'{target}.txt'
    txt_path = os.path.join(dest_dir, txt_filename)
    # Create empty file
    with open(txt_path, 'wb') as f_out:
        pass
    created += 1

print(f'Successfully created {created} blank TXT files in {dest_dir}.')
