import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

# --- 서버 경로 설정 ---
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'amoc-2026-v3-secure'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'exhibition.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')

os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# --- 데이터베이스 모델 정의 ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Artwork(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    artist = db.Column(db.String(50), nullable=False)
    medium = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(100), nullable=False)
    room = db.Column(db.Integer, default=1)
    views = db.Column(db.Integer, default=0)
    comments = db.relationship('Comment', backref='artwork', cascade="all, delete-orphan")

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    artwork_id = db.Column(db.Integer, db.ForeignKey('artwork.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

# --- 아티스트 데이터 정의 (전달받은 정보 반영) ---
ROOM_ARTISTS = {
    1: [
        {"name": "이지윤", "color_name": "Periwinkle", "hex": "#ccccff"},
        {"name": "강유민", "color_name": "Yellow", "hex": "#ffde21"},
        {"name": "김세은", "color_name": "Purple", "hex": "#834094"}
    ],
    2: [
        {"name": "전지현", "color_name": "Red", "hex": "#ff0000"},
        {"name": "현수윤", "color_name": "Pea-Green", "hex": "#8eab12"}
    ],
    3: [
        {"name": "신은하", "color_name": "Black", "hex": "#1b0c0a"},
        {"name": "박희호", "color_name": "Blue", "hex": "#0000ff"}
    ],
    4: [
        {"name": "김재준", "color_name": "Marine Blue", "hex": "#01386a"},
        {"name": "양연재", "color_name": "White", "hex": "#000000"}
    ],
    5: [
        {"name": "이용준", "color_name": "Royal Blue", "hex": "#305cde"},
        {"name": "임승규", "color_name": "Green", "hex": "#008000"},
        {"name": "박서현", "color_name": "Rose", "hex": "#ff1d8d"}
    ]
}

ARTISTS = ["강유민", "김재준", "박희호", "박서현", "김세은", "신은하", "양연재", "이용준", "이지윤", "임승규", "전지현", "현수윤"]

# --- 로그인 권한 확인 데코레이터 ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("로그인이 필요한 페이지입니다.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- 경로 설정 (Routes) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/room/<int:room_num>')
def room_view(room_num):
    artworks = Artwork.query.filter_by(room=room_num).all()
    artists_info = ROOM_ARTISTS.get(room_num, [])
    return render_template('room.html', artworks=artworks, room_num=room_num, artists_info=artists_info)

@app.route('/experience')
def experience():
    return render_template('experience.html')

@app.route('/goods')
def goods():
    return render_template('goods.html')

@app.route('/search')
def search():
    q = request.args.get('q', '')
    room_filter = request.args.get('room', '')
    artist_filter = request.args.get('artist', '')

    query = Artwork.query
    if q:
        query = query.filter(or_(Artwork.title.like(f'%{q}%'), Artwork.artist.like(f'%{q}%')))
    if room_filter:
        query = query.filter_by(room=int(room_filter))
    if artist_filter:
        query = query.filter_by(artist=artist_filter)

    results = query.all()
    return render_template('search.html', results=results, query=q, 
                           current_room=room_filter, current_artist=artist_filter, artists=ARTISTS)

@app.route('/artwork/<int:artwork_id>')
def detail(artwork_id):
    artwork = Artwork.query.get_or_404(artwork_id)
    artwork.views += 1
    db.session.commit()
    comments = Comment.query.filter_by(artwork_id=artwork_id).order_by(Comment.created_at.desc()).all()
    
    artist_color_info = None
    for room_artists_list in ROOM_ARTISTS.values():
        for artist_data in room_artists_list:
            if artist_data["name"] == artwork.artist:
                artist_color_info = artist_data
                break
        if artist_color_info:
            break
    
    return render_template('detail.html', artwork=artwork, comments=comments, artist_color_info=artist_color_info)

@app.route('/artwork/<int:artwork_id>/comment', methods=['POST'])
def add_comment(artwork_id):
    content = request.form.get('content')
    if content:
        new_comment = Comment(artwork_id=artwork_id, content=content)
        db.session.add(new_comment)
        db.session.commit()
    return redirect(url_for('detail', artwork_id=artwork_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('admin_main'))
        flash("로그인 정보가 올바르지 않습니다.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_main():
    artworks = Artwork.query.all()
    comments = Comment.query.all()
    return render_template('admin.html', artworks=artworks, comments=comments, artists=ARTISTS)

@app.route('/admin/add', methods=['POST'])
@login_required
def add_artwork():
    file = request.files['image']
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        new_art = Artwork(
            title=request.form.get('title'),
            artist=request.form.get('artist'),
            medium=request.form.get('medium'),
            description=request.form.get('description'),
            image_file=filename,
            room=int(request.form.get('room'))
        )
        db.session.add(new_art)
        db.session.commit()
    return redirect(url_for('admin_main'))

@app.route('/admin/delete_art/<int:id>')
@login_required
def delete_artwork(id):
    art = Artwork.query.get_or_404(id)
    db.session.delete(art)
    db.session.commit()
    return redirect(url_for('admin_main'))

# --- 서버 실행 및 DB 생성 ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)




