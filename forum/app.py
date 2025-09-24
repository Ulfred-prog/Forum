from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'  

DATABASE = 'forum.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        creator_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (creator_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        topic_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (topic_id) REFERENCES topics(id)
    );
    ''')
    conn.commit()
    conn.close()

def add_default_users():
    users = [
        ('holros', 'foo', 'Holros'),
        ('manfol', 'bar', 'Manfol'),
        ('goskor', 'baz', 'Goskor')
    ]
    conn = get_db()
    c = conn.cursor()
    for username, password, name in users:
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        if c.fetchone() is None:
            pw_hash = generate_password_hash(password)
            c.execute("INSERT INTO users (username, password_hash, name) VALUES (?, ?, ?)",
                      (username, pw_hash, name))
    conn.commit()
    conn.close()

setup_done = False

@app.before_request
def setup():
    global setup_done
    if not setup_done:
        init_db()
        add_default_users()
        setup_done = True

def get_user_by_username(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def logged_in():
    return 'user_id' in session

def current_user():
    if logged_in():
        return get_user_by_id(session['user_id'])
    return None


@app.route('/')
def index():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT topics.id, topics.title, topics.created_at, users.username, users.name
        FROM topics JOIN users ON topics.creator_id = users.id
        ORDER BY topics.created_at DESC
    ''')
    topics = c.fetchall()
    conn.close()
    return render_template('index.html', topics=topics, user=current_user())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if logged_in():
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            flash('Inloggning lyckades!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Felaktigt användarnamn eller lösenord', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Du är utloggad', 'info')
    return redirect(url_for('index'))

@app.route('/topic/new', methods=['GET', 'POST'])
def new_topic():
    if not logged_in():
        flash('Du måste vara inloggad för att skapa ny tråd', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        if not title or not content:
            flash('Titel och innehåll krävs', 'danger')
            return render_template('new_topic.html')

        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO topics (title, creator_id, created_at) VALUES (?, ?, ?)",
                  (title, session['user_id'], datetime.utcnow().isoformat()))
        topic_id = c.lastrowid
        c.execute("INSERT INTO posts (content, created_at, user_id, topic_id) VALUES (?, ?, ?, ?)",
                  (content, datetime.utcnow().isoformat(), session['user_id'], topic_id))
        conn.commit()
        conn.close()
        flash('Ny tråd skapad!', 'success')
        return redirect(url_for('topic', topic_id=topic_id))

    return render_template('new_topic.html')

@app.route('/topic/<int:topic_id>', methods=['GET', 'POST'])
def topic(topic_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT topics.id, topics.title, topics.created_at, users.username, users.name
        FROM topics JOIN users ON topics.creator_id = users.id
        WHERE topics.id = ?
    ''', (topic_id,))
    topic = c.fetchone()
    if topic is None:
        conn.close()
        flash('Tråden finns inte', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        if not logged_in():
            flash('Du måste vara inloggad för att skriva inlägg', 'warning')
            return redirect(url_for('login'))

        content = request.form['content'].strip()
        if not content:
            flash('Innehåll kan inte vara tomt', 'danger')
        else:
            c.execute("INSERT INTO posts (content, created_at, user_id, topic_id) VALUES (?, ?, ?, ?)",
                      (content, datetime.utcnow().isoformat(), session['user_id'], topic_id))
            conn.commit()
            flash('Inlägg tillagt!', 'success')
            conn.close()
            return redirect(url_for('topic', topic_id=topic_id))

    c.execute('''
        SELECT posts.id, posts.content, posts.created_at, users.username, users.name
        FROM posts JOIN users ON posts.user_id = users.id
        WHERE posts.topic_id = ?
        ORDER BY posts.created_at ASC
    ''', (topic_id,))
    posts = c.fetchall()
    conn.close()

    return render_template('topic.html', topic=topic, posts=posts, user=current_user())

if __name__ == '__main__':
    app.run(debug=True)
