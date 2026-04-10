import os
import secrets
import requests as http_client
from flask import Flask, render_template, request, session, redirect, url_for, Response, stream_with_context, abort

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']

BACKEND = os.getenv('BACKEND_URL', 'http://backend:8000')
ADMIN_USERS = {'jame'}


@app.route('/')
def home():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return render_template('index.html', username=session.get('username'), csrf_token=session['csrf_token'])


@app.route('/login', methods=['POST'])
def login():
    if request.form.get('csrf_token') != session.get('csrf_token'):
        return "Forbidden", 403
    username = request.form.get('username')
    if username == 'jame':
        session['username'] = 'jame'
        try:
            http_client.post(
                f"{BACKEND}/internal/activity",
                json={'username': username, 'action': 'login'},
                timeout=2,
            )
        except Exception:
            pass  # never fail a login because of analytics
        return redirect(url_for('home'))
    return "Unauthorized", 401


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))


@app.route('/dashboard')
def dashboard():
    if not session.get('username'):
        return redirect(url_for('home'))
    return render_template('dashboard.html', username=session.get('username'))


@app.route('/group/<group_id>')
def group_page(group_id):
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return render_template('index.html', username=session.get('username'), group_id=group_id, csrf_token=session['csrf_token'])


@app.route('/admin')
def admin():
    if session.get('username') not in ADMIN_USERS:
        return redirect(url_for('home'))
    return render_template('admin.html', username=session.get('username'))


@app.route('/api/<path:path>', methods=['GET', 'POST', 'DELETE'])
def proxy(path):
    if path.startswith('internal/'):
        abort(404)
    url = f"{BACKEND}/{path}"
    headers = {'X-Username': session.get('username', '')}
    kwargs = dict(headers=headers, params=request.args, stream=True, timeout=30)
    if request.method == 'POST':
        kwargs['json'] = request.get_json(silent=True)
    resp = http_client.request(request.method, url, **kwargs)
    return Response(
        stream_with_context(resp.iter_content(chunk_size=512)),
        status=resp.status_code,
        content_type=resp.headers.get('Content-Type', 'application/json'),
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
