from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        hashed_pw = generate_password_hash('060921')
        new_admin = User(username='admin', password=hashed_pw)
        db.session.add(new_admin)
        db.session.commit()
        print("✅ 관리자 계정이 생성되었습니다! (admin / 060921)")
    else:

        print("⚠️ 이미 계정이 존재합니다.")
