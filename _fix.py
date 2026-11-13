import os

path = os.path.join('D:', os.sep, chr(22270)+chr(20070)+chr(31649)+chr(29702), 'web_app.py')
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if 'STANDALONE_READER_HTML' in line and '= ' in line and start_idx is None:
        start_idx = i
    if start_idx is not None and i > start_idx and line.strip() == chr(34)*3:
        end_idx = i
        break

print('Reader block:', start_idx+1, 'to', end_idx+1)

new_reader = []
new_reader.append('STANDALONE_READER_HTML = ' + chr(34)*3 + '<!DOCTYPE html>' + chr(10))
new_reader.append('<html><head><meta charset=' + chr(34) + 'UTF-8' + chr(34) + '><title>Koodo Reader</title></head>' + chr(10))
new_reader.append('<body><script>' + chr(10))
new_reader.append('var bookId = {{ book_id }};' + chr(10))
new_reader.append('var bookUrl = window.location.origin + ' + chr(34) + '/api/download/' + chr(34) + ' + bookId;' + chr(10))
new_reader.append('window.location.href = ' + chr(34) + '/koodo/index.html' + chr(34) + ';' + chr(10))
new_reader.append('</script></body></html>' + chr(10))
new_reader.append(chr(34)*3 + chr(10))

lines[start_idx:end_idx+1] = new_reader

for i, line in enumerate(lines):
    if 'render_template_string(STANDALONE_READER_HTML, book_id=book_idx, app_version' in line:
        lines[i] = '    return render_template_string(STANDALONE_READER_HTML, book_id=book_idx)' + chr(10)
        print('Fixed read route at line', i+1)
        break

insert_idx = None
for i, line in enumerate(lines):
    if 'app.route' in line and '/read/<int:book_idx>' in line:
        insert_idx = i
        break

print('Insert point:', insert_idx+1)

nr = []
Q = chr(34)
S = chr(39)
N = chr(10)
nr.append(N)
nr.append('# ---- Koodo Reader static files ----' + N)
nr.append('KOODO_DIR = os.path.join(APP_DIR, ' + S + 'koodo_reader' + S + ')' + N)
nr.append(N)
nr.append('@app.route(' + S + '/koodo/' + S + ')' + N)
nr.append('def koodo_index():' + N)
nr.append('    return send_file(os.path.join(KOODO_DIR, ' + S + 'index.html' + S + '))' + N)
nr.append(N)
nr.append('@app.route(' + S + '/koodo/<path:filename>' + S + ')' + N)
nr.append('def koodo_static(filename):' + N)
nr.append('    fpath = os.path.join(KOODO_DIR, filename)' + N)
nr.append('    if os.path.isfile(fpath):' + N)
nr.append('        mt, _ = mimetypes.guess_type(fpath)' + N)
nr.append('        return send_file(fpath, mimetype=mt or ' + S + 'application/octet-stream' + S + ')' + N)
nr.append('    idx_p = os.path.join(fpath, ' + S + 'index.html' + S + ')' + N)
nr.append('    if os.path.isfile(idx_p):' + N)
nr.append('        return send_file(idx_p)' + N)
nr.append('    return ' + S + 'Not Found' + S + ', 404' + N)
nr.append(N)
nr.append('# ---- Version and Hot-Update APIs ----' + N)
nr.append('@app.route(' + S + '/api/version' + S + ')' + N)
nr.append('def api_version():' + N)
nr.append('    return jsonify({' + N)
nr.append('        ' + Q + 'version' + Q + ': APP_VERSION,' + N)
nr.append('        ' + Q + 'build_date' + Q + ': BUILD_DATE,' + N)
nr.append('        ' + Q + 'git_commit' + Q + ': os.getenv(' + S + 'GIT_COMMIT' + S + ', ' + S + S + '),' + N)
nr.append('        ' + Q + 'features' + Q + ': FEATURES' + N)
nr.append('    })' + N)
nr.append(N)
nr.append('@app.route(' + S + '/api/system/check_update' + S + ')' + N)
nr.append('def api_check_update():' + N)
nr.append('    import subprocess as _sp' + N)
nr.append('    try:' + N)
nr.append('        r = _sp.run([' + S + 'git' + S + ', ' + S + 'ls-remote' + S + ', ' + S + 'https://github.com/a1139036147/book-organizer.git' + S + ', ' + S + 'HEAD' + S + '],' + N)
nr.append('                    capture_output=True, text=True, timeout=10)' + N)
nr.append('        remote_sha = r.stdout.strip().split()[0][:7] if r.stdout.strip() else ' + S + S + N)
nr.append('        local_sha = os.getenv(' + S + 'GIT_COMMIT' + S + ', ' + S + S + ')' + N)
nr.append('        has_update = bool(remote_sha and local_sha and remote_sha != local_sha)' + N)
nr.append('        return jsonify({' + Q + 'has_update' + Q + ': has_update, ' + Q + 'local_commit' + Q + ': local_sha, ' + Q + 'remote_commit' + Q + ': remote_sha, ' + Q + 'current_version' + Q + ': APP_VERSION})' + N)
nr.append('    except Exception as ex:' + N)
nr.append('        return jsonify({' + Q + 'has_update' + Q + ': False, ' + Q + 'error' + Q + ': str(ex)})' + N)
nr.append(N)
nr.append('@app.route(' + S + '/api/system/hot_update' + S + ', methods=[' + S + 'POST' + S + '])' + N)
nr.append('def api_hot_update():' + N)
nr.append('    import subprocess as _sp' + N)
nr.append('    try:' + N)
nr.append('        r = _sp.run([' + S + 'git' + S + ', ' + S + 'pull' + S + ', ' + S + '--ff-only' + S + ', ' + S + 'origin' + S + ', ' + S + 'main' + S + '],' + N)
nr.append('                    capture_output=True, text=True, timeout=60, cwd=APP_DIR)' + N)
nr.append('        if r.returncode == 0:' + N)
nr.append('            os._exit(0)' + N)
nr.append('        return jsonify({' + Q + 'success' + Q + ': False, ' + Q + 'error' + Q + ': r.stderr})' + N)
nr.append('    except Exception as ex:' + N)
nr.append('        return jsonify({' + Q + 'success' + Q + ': False, ' + Q + 'error' + Q + ': str(ex)})' + N)
nr.append(N)

lines[insert_idx:insert_idx] = nr
print('Inserted', len(nr), 'route lines')

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Done! Total lines:', len(lines))
