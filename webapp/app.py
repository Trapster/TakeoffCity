import os
import secrets
import requests as http_client
from flask import Flask, render_template, request, session, redirect, url_for, Response, stream_with_context, abort, flash

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']

BACKEND = os.getenv('BACKEND_URL', 'http://backend:8000')
ADMIN_USERS = {os.environ['WEB_ADMIN_USERNAME']}


@app.route('/')
def home():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return render_template('index.html', username=session.get('username'), csrf_token=session['csrf_token'])


@app.route('/login', methods=['POST'])
def login():
    if request.form.get('csrf_token') != session.get('csrf_token'):
        return "Forbidden", 403
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    try:
        resp = http_client.post(
            f"{BACKEND}/internal/auth",
            json={'username': username, 'password': password},
            timeout=5,
        )
    except Exception:
        flash('Service unavailable. Please try again.', 'error')
        return redirect(url_for('home'))
    if resp.status_code != 200:
        flash('Invalid username or password.', 'error')
        return redirect(url_for('home'))
    session['username'] = username
    try:
        http_client.post(
            f"{BACKEND}/internal/activity",
            json={'username': username, 'action': 'login'},
            timeout=2,
        )
    except Exception:
        pass
    return redirect(_safe_redirect(request.form.get('return_to', '')))


def _safe_redirect(return_to: str) -> str:
    """Return a safe redirect path after auth, defaulting to home."""
    path = return_to.strip()
    if path and path.startswith('/') and not path.startswith('//'):
        return path + '?authed=1'
    return url_for('home')


@app.route('/signup', methods=['POST'])
def signup():
    if request.form.get('csrf_token') != session.get('csrf_token'):
        return "Forbidden", 403
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm = request.form.get('confirm_password', '')
    if password != confirm:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('home'))
    try:
        resp = http_client.post(
            f"{BACKEND}/internal/users",
            json={'username': username, 'email': email, 'password': password},
            timeout=5,
        )
    except Exception:
        flash('Service unavailable. Please try again.', 'error')
        return redirect(url_for('home'))
    if resp.status_code == 409:
        flash(resp.json().get('detail', 'Username or email already taken.'), 'error')
        return redirect(url_for('home'))
    if resp.status_code != 201:
        flash('Signup failed. Please try again.', 'error')
        return redirect(url_for('home'))
    session['username'] = username
    try:
        http_client.post(
            f"{BACKEND}/internal/activity",
            json={'username': username, 'action': 'signup'},
            timeout=2,
        )
    except Exception:
        pass
    return redirect(_safe_redirect(request.form.get('return_to', '')))


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))


@app.route('/dashboard')
def dashboard():
    if not session.get('username'):
        return redirect(url_for('home'))
    return render_template('dashboard.html', username=session.get('username'))


@app.route('/settings')
def settings():
    if not session.get('username'):
        return redirect(url_for('home'))
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    user_data = {}
    try:
        resp = http_client.get(
            f"{BACKEND}/internal/users/me",
            params={'username': session['username']},
            timeout=5,
        )
        if resp.status_code == 200:
            user_data = resp.json()
    except Exception:
        pass
    return render_template('settings.html', username=session.get('username'), csrf_token=session['csrf_token'], user_data=user_data)


@app.route('/settings/password', methods=['POST'])
def settings_password():
    if not session.get('username'):
        return redirect(url_for('home'))
    if request.form.get('csrf_token') != session.get('csrf_token'):
        return "Forbidden", 403
    current = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    if new_pw != confirm:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('settings'))
    try:
        resp = http_client.put(
            f"{BACKEND}/internal/users/me/password",
            json={'username': session['username'], 'current_password': current, 'new_password': new_pw},
            timeout=5,
        )
    except Exception:
        flash('Service unavailable.', 'error')
        return redirect(url_for('settings'))
    if resp.status_code == 403:
        flash('Current password is incorrect.', 'error')
    elif resp.status_code == 200:
        flash('Password updated successfully.', 'success')
    else:
        flash('Failed to update password.', 'error')
    return redirect(url_for('settings'))


@app.route('/settings/email', methods=['POST'])
def settings_email():
    if not session.get('username'):
        return redirect(url_for('home'))
    if request.form.get('csrf_token') != session.get('csrf_token'):
        return "Forbidden", 403
    password = request.form.get('password', '')
    new_email = request.form.get('new_email', '').strip()
    try:
        resp = http_client.put(
            f"{BACKEND}/internal/users/me/email",
            json={'username': session['username'], 'password': password, 'new_email': new_email},
            timeout=5,
        )
    except Exception:
        flash('Service unavailable.', 'error')
        return redirect(url_for('settings'))
    if resp.status_code == 403:
        flash('Incorrect password.', 'error')
    elif resp.status_code == 409:
        flash('That email is already in use.', 'error')
    elif resp.status_code == 200:
        flash('Email updated successfully.', 'success')
    else:
        flash('Failed to update email.', 'error')
    return redirect(url_for('settings'))


@app.route('/settings/delete', methods=['POST'])
def settings_delete():
    if not session.get('username'):
        return redirect(url_for('home'))
    if request.form.get('csrf_token') != session.get('csrf_token'):
        return "Forbidden", 403
    password = request.form.get('password', '')
    try:
        resp = http_client.delete(
            f"{BACKEND}/internal/users/me",
            json={'username': session['username'], 'password': password},
            timeout=5,
        )
    except Exception:
        flash('Service unavailable.', 'error')
        return redirect(url_for('settings'))
    if resp.status_code == 403:
        flash('Incorrect password.', 'error')
        return redirect(url_for('settings'))
    session.pop('username', None)
    return redirect(url_for('home'))


@app.route('/group/<group_id>')
def group_page(group_id):
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return render_template('group.html', username=session.get('username'), group_id=group_id, csrf_token=session['csrf_token'])


@app.route('/admin')
def admin():
    if session.get('username') not in ADMIN_USERS:
        return redirect(url_for('home'))
    return render_template('admin.html', username=session.get('username'))


@app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
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
