import os
from datetime import datetime, timedelta, date
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

# --- 서버 경로 설정 ---
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# --- 한국 시간 변환 필터 (UTC + 9시간) ---
@app.template_filter('kst')
def datetime_kst(value):
    if value is None:
        return ""
    # 서버 시간(UTC)에 9시간을 더해 한국 시간으로 변환
    kst_time = value + timedelta(hours=9)
    return kst_time.strftime('%Y-%m-%d %H:%M')

app.config['SECRET_KEY'] = 'amoc-2026-v3-secure'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'exhibition.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')

os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

@app.before_request
def count_visitor():
    # 세션에 'visited' 표시가 없으면 (오늘 처음 온 사람)
    if 'visited_site' not in session:
        # 한국 시간 기준 '오늘' 날짜 구하기
        kst_today = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y-%m-%d')
        
        stat = DailyStat.query.get(kst_today)
        if not stat:
            stat = DailyStat(date_str=kst_today, visitor_count=0, total_view_count=0)
            db.session.add(stat)
        
        stat.visitor_count += 1
        db.session.commit()
        
        # 세션에 방문 기록 남김 (브라우저 닫기 전까지 유지)
        session['visited_site'] = True

# --- 데이터베이스 모델 정의 ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# --- 일별 통계 모델  ---
class DailyStat(db.Model):
    date_str = db.Column(db.String(10), primary_key=True)  # 날짜 (2026-02-12)
    visitor_count = db.Column(db.Integer, default=0)       # 사이트 방문자 수
    total_view_count = db.Column(db.Integer, default=0)    # 작품 총 조회수

class Artwork(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    artist = db.Column(db.String(50), nullable=False)
    medium = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(100), nullable=False)
    room = db.Column(db.Integer, default=1)
    display_order = db.Column(db.Integer, default=0)
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
        {"name": "양연재", "color_name": "White", "hex": "#ffffff"}
    ],
    5: [
        {"name": "이용준", "color_name": "Royal Blue", "hex": "#002366"},
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
    artworks = Artwork.query.filter_by(room=room_num).order_by(Artwork.display_order, Artwork.artist).all()
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
    # URL에 검색 파라미터가 있는지 확인
    # q, room, artist 중 하나라도 파라미터로 넘어왔다면 검색을 시도한 것으로 간주
    # 그냥 /search로 들어오면 request.args가 비어있으므로 searched = False
    searched = bool(request.args)
    
    q = request.args.get('q', '')
    room_filter = request.args.get('room', '')
    artist_filter = request.args.get('artist', '')

    results = []
    
    # 검색 버튼을 눌렀을 때만(파라미터가 있을 때만) DB 조회를 실행
    if searched:
        query = Artwork.query
        if q:
            query = query.filter(or_(Artwork.title.like(f'%{q}%'), Artwork.artist.like(f'%{q}%')))
        if room_filter:
            query = query.filter_by(room=int(room_filter))
        if artist_filter:
            query = query.filter_by(artist=artist_filter)
        
        results = query.all()

    # searched 변수를 템플릿으로
    return render_template('search.html', results=results, query=q, 
                           current_room=room_filter, current_artist=artist_filter, artists=ARTISTS,
                           searched=searched)

@app.route('/artwork/<int:artwork_id>')
def detail(artwork_id):
    artwork = Artwork.query.get_or_404(artwork_id)
    
    # --- [수정됨] 조회수 증가 로직 (새로고침 방지) ---
    # 세션에 'viewed_artworks' 리스트가 없으면 생성
    if 'viewed_artworks' not in session:
        session['viewed_artworks'] = []
    
    # 이 작품을 본 적이 없으면 조회수 증가
    if artwork_id not in session['viewed_artworks']:
        artwork.views += 1
        session['viewed_artworks'].append(artwork_id)
        session.modified = True  # 세션 변경 사항 저장 알림
        
        # 일별 통계에도 작품 조회수 +1
        kst_today = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y-%m-%d')
        stat = DailyStat.query.get(kst_today)
        if not stat:
            stat = DailyStat(date_str=kst_today, visitor_count=0, total_view_count=0)
            db.session.add(stat)
        stat.total_view_count += 1
        
        db.session.commit()
    # ---------------------------------------------

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
    comments = Comment.query.order_by(Comment.created_at.desc()).limit(10).all()
    stats = DailyStat.query.order_by(DailyStat.date_str.desc()).all()
    
    # 조회수 높은 순으로 상위 5개 가져오기 
    popular_artworks = Artwork.query.order_by(Artwork.views.desc()).limit(5).all()
    
    return render_template('admin.html', 
                           artworks=artworks, 
                           comments=comments, 
                           artists=ARTISTS, 
                           stats=stats, 
                           popular_artworks=popular_artworks)

# --- [추가] 작품 조회수 전체 초기화 ---
@app.route('/admin/reset_views')
@login_required
def reset_views():
    # 모든 작품의 조회수를 0으로 변경
    # 방법: DB를 직접 업데이트
    db.session.query(Artwork).update({Artwork.views: 0})
    db.session.commit()
    flash("모든 작품의 조회수가 초기화되었습니다.")
    return redirect(url_for('admin_main'))

@app.route('/admin/add', methods=['POST'])
@login_required
def add_artwork():
    # 파일 업로드 대신 텍스트로 된 파일명을 가져옵니다.
    filename = request.form.get('image_filename')
    
    if filename:
        new_art = Artwork(
            title=request.form.get('title'),
            artist=request.form.get('artist'),
            medium=request.form.get('medium'),
            description=request.form.get('description'),
            image_file=filename,  # 입력한 파일명을 그대로 DB에 저장
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

@app.route('/comment/delete/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    artwork_id = comment.artwork_id 
    
    db.session.delete(comment)
    db.session.commit()
    
    return redirect(url_for('detail', artwork_id=artwork_id))

# [app.py] 맨 아래쪽에 추가

@app.route('/admin/update_order/<int:artwork_id>', methods=['POST'])
@login_required
def update_artwork_order(artwork_id):
    art = Artwork.query.get_or_404(artwork_id)
    # 폼에서 입력받은 숫자로 순서 업데이트
    new_order = request.form.get('display_order', type=int)
    art.display_order = new_order
    db.session.commit()
    return redirect(url_for('admin_main'))
    
# --- 서버 실행 및 DB 생성 ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)















