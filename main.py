from flask import Flask, request, send_file, render_template_string
from werkzeug.utils import secure_filename
import os, time

app = Flask(__name__)
BASE_FOLDER = 'users'
os.makedirs(BASE_FOLDER, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024
FILE_LIFETIME = 5 * 60

# Tyylikäs HTML-template
TEMPLATE = '''
<!DOCTYPE html>
<html lang="fi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tiedostonjakopalvelu</title>
<style>
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
       background: #f0f2f5; margin:0; display:flex; justify-content:center; align-items:center; height:100vh; }
.container { background:white; padding:30px; border-radius:12px; box-shadow:0 8px 20px rgba(0,0,0,0.1); width:100%; max-width:400px; text-align:center; }
h1 { color:#333; margin-bottom:20px; }
input[type=text], input[type=file] { width:90%; padding:10px; margin:10px 0; border-radius:6px; border:1px solid #ccc; }
button { background:#4CAF50; color:white; border:none; padding:12px 20px; border-radius:8px; cursor:pointer; font-size:16px; margin-top:10px; transition:0.3s; }
button:hover { background:#45a049; }
.file-card { background:#f9f9f9; padding:10px; margin:5px 0; border-radius:8px; box-shadow:0 2px 5px rgba(0,0,0,0.1); }
a { text-decoration:none; color:#4CAF50; font-weight:bold; }
a:hover { text-decoration:underline; }
</style>
</head>
<body>
<div class="container">
    {% if stage == 'login' %}
        <h1>Kirjaudu</h1>
        <form action="/menu" method="post">
            Käyttäjänimi:<br><input type="text" name="username" required><br>
            <button type="submit">Jatka</button>
        </form>
    {% elif stage == 'menu' %}
        <h1>Hei {{ username }}!</h1>
        <form action="/send" method="get" style="margin-bottom:10px;">
            <button type="submit" name="username" value="{{ username }}">Lähetä tiedosto</button>
        </form>
        <form action="/receive" method="get">
            <button type="submit" name="username" value="{{ username }}">Nouda tiedostoja</button>
        </form>
    {% elif stage == 'send' %}
        <h1>Lähetä tiedosto</h1>
        <form action="/send_file" method="post" enctype="multipart/form-data">
            Lähettäjä:<br><input type="text" name="sender" value="{{ username }}" readonly><br>
            Vastaanottaja:<br><input type="text" name="receiver" required><br>
            Valitse tiedosto:<br><input type="file" name="file" required><br>
            <button type="submit">Lähetä</button>
        </form>
    {% elif stage == 'receive' %}
        <h1>Tiedostot sinulle, {{ username }}</h1>
        {% if files %}
            {% for file in files %}
                <div class="file-card"><a href="/download/{{ username }}/{{ file }}">{{ file }}</a></div>
            {% endfor %}
        {% else %}
            <p>Ei uusia tiedostoja.</p>
        {% endif %}
    {% elif stage == 'sent' %}
        <h1>Tiedosto lähetetty käyttäjälle {{ receiver }}!</h1>
        <a href="/menu_redirect/{{ sender }}">Takaisin valikkoon</a>
    {% endif %}
</div>
</body>
</html>
'''


def cleanup_old_files(folder):
    now = time.time()
    for filename in os.listdir(folder):
        path = os.path.join(folder, filename)
        if os.path.isfile(
                path) and now - os.path.getmtime(path) > FILE_LIFETIME:
            os.remove(path)


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


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000)
