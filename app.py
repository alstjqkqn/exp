import sqlite3
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='.')

DATABASE_FILE = 'experiment.db'
MAX_SLOTS_PER_GENDER = 11
TOTAL_SESSIONS = 10

def get_db_connection():
    """데이터베이스 연결을 생성하는 함수"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row # 결과를 딕셔너리처럼 사용할 수 있게 함
    return conn

def init_db():
    """'participants' 테이블이 없으면 새로 생성하는 함수"""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            gender TEXT NOT NULL,
            session_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/sessions', methods=['GET'])
def get_session_status():
    """DB에서 현재 세션별 인원을 집계하여 잔여 인원 반환"""
    conn = get_db_connection()
    # 세션별, 성별별로 참가자 수를 집계
    counts_query = conn.execute(
        'SELECT session_id, gender, COUNT(*) as count FROM participants GROUP BY session_id, gender'
    ).fetchall()
    conn.close()

    # 초기 상태 딕셔너리 생성
    participant_data = {
        f"session_{i}": {"male": 0, "female": 0} for i in range(1, TOTAL_SESSIONS + 1)
    }
    # DB에서 읽어온 값으로 업데이트
    for row in counts_query:
        participant_data[row['session_id']][row['gender']] = row['count']

    # 잔여 인원 계산
    remaining_slots = {}
    for session_id, counts in participant_data.items():
        remaining_slots[session_id] = {
            "male": MAX_SLOTS_PER_GENDER - counts["male"],
            "female": MAX_SLOTS_PER_GENDER - counts["female"]
        }
    return jsonify(remaining_slots)

@app.route('/api/apply', methods=['POST'])
def apply_for_session():
    """참가 신청 정보를 받아 DB에 저장"""
    data = request.json
    session_id = data.get('session_id')
    gender = data.get('gender')
    name = data.get('name')
    email = data.get('email')

    if not all([session_id, gender, name, email]):
        return jsonify({"success": False, "message": "모든 정보를 입력해주세요."}), 400

    conn = get_db_connection()

    # 1. 이미 신청한 이메일인지 확인
    existing = conn.execute('SELECT * FROM participants WHERE email = ?', (email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": False, "message": "이미 신청한 이메일입니다."}), 400

    # 2. 해당 세션, 성별의 정원이 찼는지 확인
    count = conn.execute(
        'SELECT COUNT(*) FROM participants WHERE session_id = ? AND gender = ?', 
        (session_id, gender)
    ).fetchone()[0]
    
    if count >= MAX_SLOTS_PER_GENDER:
        conn.close()
        return jsonify({"success": False, "message": "죄송합니다. 해당 세션의 정원이 마감되었습니다."}), 400

    # 3. 모든 확인 통과 시, DB에 참가자 정보 저장
    conn.execute(
        'INSERT INTO participants (name, email, gender, session_id) VALUES (?, ?, ?, ?)',
        (name, email, session_id, gender)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"{session_id.replace('_', ' ').title()}에 성공적으로 신청되었습니다!"})

# Flask 앱이 처음 실행될 때 init_db()를 호출하여 DB와 테이블을 준비
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)