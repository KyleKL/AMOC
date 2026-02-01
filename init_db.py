from app import app, db, Artwork

# 테스트용 데이터 리스트
test_artworks = [
    {
        "title": "푸른 새의 연작 - 1",
        "artist": "이용준",
        "medium": "아크릴",
        "description": "22cm 정사각 캔버스에 작업한 푸른 새 시리즈의 첫 번째 작품입니다.",
        "image_file": "test1.jpg" # 실제 static/uploads 폴더에 있는 파일명과 같아야 함
    },
    {
        "title": "기하학적 추상",
        "artist": "김철수",
        "medium": "유화",
        "description": "다양한 도형을 활용하여 현대인의 고독을 표현했습니다.",
        "image_file": "test2.jpg"
    },
    {
        "title": "디지털 정원",
        "artist": "이영희",
        "medium": "디지털",
        "description": "아이패드를 사용하여 작업한 디지털 아트웍입니다.",
        "image_file": "test3.jpg"
    }
]

with app.app_context():
    # 기존 데이터 삭제 (깔끔하게 새로 시작하고 싶을 때)
    db.drop_all()
    db.create_all()
    
    # 데이터 추가
    for data in test_artworks:
        new_art = Artwork(
            title=data['title'],
            artist=data['artist'],
            medium=data['medium'],
            description=data['description'],
            image_file=data['image_file']
        )
        db.session.add(new_art)
    
    db.session.commit()
    print("✅ 테스트 데이터가 성공적으로 추가되었습니다!")