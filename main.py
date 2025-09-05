from flask import Flask, request, send_file, render_template_string
from werkzeug.utils import secure_filename
import os, time, threading

app = Flask(__name__)
BASE_FOLDER = 'users'
os.makedirs(BASE_FOLDER, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024
FILE_LIFETIME = 5 * 60  # 5 minuuttia

# Uusi moderni HTML-template
TEMPLATE = '''
<!DOCTYPE html>
<html lang="fi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tiedostonjakopalvelu</title>
<style>
body {
  font-family: 'Segoe UI', sans-serif;
  margin: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  transition: background 0.5s, color 0.5s;
}
.container {
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(15px);
  padding: 40px;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
  width: 100%;
  max-width: 420px;
  text-align: center;
}
h1 { margin-bottom: 20px; font-size: 1.8em; }
input[type=text], input[type=file] {
  width: 90%;
  padding: 12px;
  margin: 10px 0;
  border-radius: 8px;
  border: none;
  outline: none;
}
button {
  background: #4CAF50;
  color: white;
  border: none;
  padding: 12px 20px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 16px;
  margin-top: 10px;
  transition: all 0.3s ease;
}
button:hover { background: #45a049; transform: scale(1.05); }
.file-card {
  background: rgba(255, 255, 255, 0.1);
  padding: 12px;
  margin: 8px 0;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
a { text-decoration: none; color: #ffeb3b; font-weight: bold; }
a:hover { text-decoration: underline; }
.back-btn {
  position: absolute;
  top: 15px;
  left: 15px;
  background: #333;
  color: white;
  padding: 8px 14px;
  border-radius: 8px;
  text-decoration: none;
  font-size: 14px;
}
.back-btn:hover { background: #555; }
.light-theme {
  background: linear-gradient(135deg, #74ebd5 0%, #ACB6E5 100%);
  color: #000;
}
.dark-theme {
  background: linear-gradient(135deg, #232526 0%, #414345 100%);
  color: #fff;
}
</style>
<script>
function toggleTheme() {
    let current = localStorage.getItem("theme") || "light";
    let newTheme = current === "light" ? "dark" : "light";
    localStorage.setItem("theme", newTheme);
    applyTheme();
}
function applyTheme() {
    let theme = localStorage.getItem("theme") || "light";
    document.body.className = theme + "-theme";
}
function saveLogin(username) {
    localStorage.setItem("username", username);
}
function checkLogin() {
    let savedUser = localStorage.getItem("username");
    if (savedUser && window.location.pathname === "/") {
        window.location.href = "/menu_redirect/" + savedUser;
    }
}
function logout() {
    localStorage.removeItem("username");
    window.location.href = "/";
}
window.onload = function() {
    applyTheme();
    checkLogin();
}
</script>
</head>
<body>
<a href="/menu_redirect/{{ username }}" class="back-btn" {% if stage == 'login' or stage == 'menu' %}style="display:none;"{% endif %}>⬅ Takaisin</a>
<div class="container">
    {% if stage == 'login' %}
        <h1>Kirjaudu</h1>
        <form action="/menu" method="post" onsubmit="saveLogin(document.getElementById('username').value)">
            <input type="text" id="username" name="username" placeholder="Käyttäjänimi" required><br>
            <button type="submit">Jatka</button>
        </form>
    {% elif stage == 'menu' %}
        <h1>Hei {{ username }}!</h1>
        <form action="/send" method="get" style="margin-bottom:10px;">
            <button type="submit" name="username" value="{{ username }}">📤 Lähetä tiedosto</button>
        </form>
        <form action="/receive" method="get" style="margin-bottom:10px;">
            <button type="submit" name="username" value="{{ username }}">📥 Nouda tiedostoja</button>
        </form>
        <form action="/settings" method="get">
            <button type="submit" name="username" value="{{ username }}">⚙️ Asetukset</button>
        </form>
    {% elif stage == 'send' %}
        <h1>📤 Lähetä tiedosto</h1>
        <form action="/send_file" method="post" enctype="multipart/form-data">
            <input type="text" name="sender" value="{{ username }}" readonly><br>
            <input type="text" name="receiver" placeholder="Vastaanottaja" required><br>
            <input type="file" name="file" required><br>
            <button type="submit">Lähetä</button>
        </form>
    {% elif stage == 'receive' %}
        <h1>📥 Tiedostot sinulle, {{ username }}</h1>
        {% if files %}
            {% for file in files %}
                <div class="file-card"><a href="/download/{{ username }}/{{ file }}">{{ file }}</a></div>
            {% endfor %}
        {% else %}
            <p>Ei uusia tiedostoja.</p>
        {% endif %}
    {% elif stage == 'settings' %}
        <h1>⚙️ Asetukset</h1>
        <button onclick="toggleTheme()">🎨 Vaihda teema</button><br><br>
        <button onclick="logout()" style="background:#f44336;">🚪 Kirjaudu ulos</button>
    {% elif stage == 'sent' %}
        <h1>✅ Tiedosto lähetetty käyttäjälle {{ receiver }}!</h1>
        <a href="/menu_redirect/{{ sender }}">⬅ Takaisin valikkoon</a>
    {% endif %}
</div>
</body>
</html>
'''


def cleanup_old_files(folder):
    now = time.time()
    for filename in os.listdir(folder):
        path = os.path.join(folder, filename)
        if os.path.isfile(path) and now - os.path.getmtime(path) > FILE_LIFETIME:
            os.remove(path)


def background_cleanup():
    """Siivoa kaikki vanhat tiedostot taustalla minuutin välein"""
    while True:
        for user in os.listdir(BASE_FOLDER):
            folder = os.path.join(BASE_FOLDER, user)
            if os.path.isdir(folder):
                cleanup_old_files(folder)
        time.sleep(60)  # odota minuutti


@app.route('/')
def login():
    return render_template_string(TEMPLATE, stage='login')


@app.route('/menu', methods=['POST'])
def menu():
    username = request.form['username']
    user_folder = os.path.join(BASE_FOLDER, username)
    os.makedirs(user_folder, exist_ok=True)
    cleanup_old_files(user_folder)
    return render_template_string(TEMPLATE, stage='menu', username=username)


@app.route('/menu_redirect/<username>')
def menu_redirect(username):
    user_folder = os.path.join(BASE_FOLDER, username)
    os.makedirs(user_folder, exist_ok=True)
    cleanup_old_files(user_folder)
    return render_template_string(TEMPLATE, stage='menu', username=username)


@app.route('/send')
def send():
    username = request.args.get('username')
    return render_template_string(TEMPLATE, stage='send', username=username)


@app.route('/send_file', methods=['POST'])
def send_file_route():
    sender = request.form['sender']
    receiver = request.form['receiver']
    f = request.files['file']

    if f.filename == '':
        return "Ei tiedostoa valittu!"

    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(0)
    if size > MAX_FILE_SIZE:
        return "Tiedosto on liian suuri (max 50MB)!"

    receiver_folder = os.path.join(BASE_FOLDER, receiver)
    os.makedirs(receiver_folder, exist_ok=True)
    cleanup_old_files(receiver_folder)

    filename = secure_filename(f.filename)
    path = os.path.join(receiver_folder, f"{sender}_{filename}")
    f.save(path)

    return render_template_string(TEMPLATE,
                                  stage='sent',
                                  sender=sender,
                                  receiver=receiver)


@app.route('/receive')
def receive():
    username = request.args.get('username')
    user_folder = os.path.join(BASE_FOLDER, username)
    os.makedirs(user_folder, exist_ok=True)
    cleanup_old_files(user_folder)
    files = os.listdir(user_folder)
    return render_template_string(TEMPLATE,
                                  stage='receive',
                                  username=username,
                                  files=files)


@app.route('/download/<username>/<filename>')
def download(username, filename):
    path = os.path.join(BASE_FOLDER, username, secure_filename(filename))
    if not os.path.exists(path):
        return "Tiedostoa ei löytynyt!"
    return send_file(path, as_attachment=True)


@app.route('/settings')
def settings():
    username = request.args.get('username')
    return render_template_string(TEMPLATE, stage='settings', username=username)


if __name__ == "__main__":
    # Käynnistetään taustasiivous säikeessä
    cleanup_thread = threading.Thread(target=background_cleanup, daemon=True)
    cleanup_thread.start()

    app.run(host='0.0.0.0', port=3000)
