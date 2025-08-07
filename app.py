import sqlite3
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='.')

DATABASE_FILE = 'experiment.db'
MAX_SLOTS_PER_GENDER = 11
TOTAL_SESSIONS = 10

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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
    conn = get_db_connection()
    counts_query = conn.execute(
        'SELECT session_id, gender, COUNT(*) as count FROM participants GROUP BY session_id, gender'
    ).fetchall()
    conn.close()

    participant_data = {
        f"session_{i}": {"male": 0, "female": 0} for i in range(1, TOTAL_SESSIONS + 1)
    }
    for row in counts_query:
        # DB에 혹시라도 잘못된 gender 값이 있어도 오류가 나지 않도록 방어 코드 추가
        if row['gender'] in ['male', 'female']:
            participant_data[row['session_id']][row['gender']] = row['count']

    remaining_slots = {}
    for session_id, counts in participant_data.items():
        remaining_slots[session_id] = {
            "male": MAX_SLOTS_PER_GENDER - counts["male"],
            "female": MAX_SLOTS_PER_GENDER - counts["female"]
        }
    return jsonify(remaining_slots)

@app.route('/api/apply', methods=['POST'])
def apply_for_session():
    data = request.json
    session_id = data.get('session_id')
    gender = data.get('gender')
    name = data.get('name')
    email = data.get('email')

    if not all([session_id, gender, name, email]):
        return jsonify({"success": False, "message": "모든 정보를 입력해주세요."}), 400

    conn = get_db_connection()

    existing = conn.execute('SELECT * FROM participants WHERE email = ?', (email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": False, "message": "이미 신청한 이메일입니다."}), 400

    count = conn.execute(
        'SELECT COUNT(*) FROM participants WHERE session_id = ? AND gender = ?', 
        (session_id, gender)
    ).fetchone()[0]
    
    if count >= MAX_SLOTS_PER_GENDER:
        conn.close()
        return jsonify({"success": False, "message": "죄송합니다. 해당 세션의 정원이 마감되었습니다."}), 400

    # ▼▼▼ 바로 이 부분의 변수 순서가 잘못되어 있었습니다. 수정했습니다. ▼▼▼
    conn.execute(
        'INSERT INTO participants (name, email, gender, session_id) VALUES (?, ?, ?, ?)',
        (name, email, gender, session_id)
    )
    # ▲▲▲ 여기까지 수정 ▲▲▲
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"{session_id.replace('_', ' ').title()}에 성공적으로 신청되었습니다!"})

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
