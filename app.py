from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///forum.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    profile_picture = db.Column(db.String(150), nullable=True)

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('User', backref='topics', lazy=True)
    posts = db.relationship('Post', backref='topic', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)
    author = db.relationship('User', backref='posts', lazy=True)
    likes_rel = db.relationship('Like', backref='post', lazy=True)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', backref='chat_messages', lazy=True)

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    topics = Topic.query.all()
    return render_template('index.html', topics=topics)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/topic/<int:topic_id>')
def topic(topic_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    topic = Topic.query.get_or_404(topic_id)
    posts = Post.query.filter_by(topic_id=topic_id).all()
    return render_template('topic.html', topic=topic, posts=posts)

@app.route('/create_topic', methods=['GET', 'POST'])
def create_topic():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        new_topic = Topic(title=title, creator_id=session['user_id'])
        db.session.add(new_topic)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('create_topic.html')

@app.route('/create_post/<int:topic_id>', methods=['POST'])
def create_post(topic_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    content = request.form['content']
    new_post = Post(content=content, author_id=session['user_id'], topic_id=topic_id)
    db.session.add(new_post)
    db.session.commit()
    return redirect(url_for('topic', topic_id=topic_id))

@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    existing_like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
    if existing_like:
        db.session.delete(existing_like)
        post = Post.query.get(post_id)
        post.likes -= 1
    else:
        new_like = Like(user_id=user_id, post_id=post_id)
        db.session.add(new_like)
        post = Post.query.get(post_id)
        post.likes += 1
    db.session.commit()
    return redirect(request.referrer)

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        content = request.form['content']
        new_message = ChatMessage(content=content, author_id=session['user_id'])
        db.session.add(new_message)
        db.session.commit()
        return redirect(url_for('chat'))
    messages = ChatMessage.query.order_by(ChatMessage.timestamp).all()
    last_id = messages[-1].id if messages else 0
    return render_template('chat.html', messages=messages, last_id=last_id)

@app.route('/get_new_messages/<int:last_id>')
def get_new_messages(last_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    new_messages = ChatMessage.query.filter(ChatMessage.id > last_id).order_by(ChatMessage.timestamp).all()
    messages_list = []
    for msg in new_messages:
        messages_list.append({
            'id': msg.id,
            'author_username': msg.author.username,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify(messages_list)

@app.route('/get_new_topics/<int:last_topic_id>')
def get_new_topics(last_topic_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    new_topics = Topic.query.filter(Topic.id > last_topic_id).order_by(Topic.timestamp).all()
    topics_list = []
    for topic in new_topics:
        topics_list.append({
            'id': topic.id,
            'title': topic.title,
            'creator_username': topic.creator.username,
            'timestamp': topic.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify(topics_list)

@app.route('/get_new_posts/<int:topic_id>/<int:last_post_id>')
def get_new_posts(topic_id, last_post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    new_posts = Post.query.filter(Post.topic_id == topic_id, Post.id > last_post_id).order_by(Post.timestamp).all()
    posts_list = []
    for post in new_posts:
        posts_list.append({
            'id': post.id,
            'content': post.content,
            'author_username': post.author.username,
            'timestamp': post.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'likes': post.likes
        })
    return jsonify(posts_list)

@app.route('/get_post_likes/<int:topic_id>')
def get_post_likes(topic_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    posts = Post.query.filter_by(topic_id=topic_id).all()
    likes_dict = {post.id: post.likes for post in posts}
    return jsonify(likes_dict)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
