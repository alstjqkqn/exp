import sqlite3
from flask import Flask, render_template, request, jsonify, Response
import io
import csv

app = Flask(__name__, template_folder='.')

DATABASE_FILE = 'experiment.db'
MAX_SLOTS_PER_GENDER = 11
TOTAL_SESSIONS = 10

# --- (get_db_connection, init_db 함수는 이전과 동일) ---
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

# --- (메인 페이지, 세션 정보 API, 신청 API는 이전과 동일) ---
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
    participant_data = { f"session_{i}": {"male": 0, "female": 0} for i in range(1, TOTAL_SESSIONS + 1) }
    for row in counts_query:
        if row['gender'] in ['male', 'female']:
            participant_data[row['session_id']][row['gender']] = row['count']
    remaining_slots = {}
    for session_id, counts in participant_data.items():
        remaining_slots[session_id] = { "male": MAX_SLOTS_PER_GENDER - counts["male"], "female": MAX_SLOTS_PER_GENDER - counts["female"] }
    return jsonify(remaining_slots)

@app.route('/api/apply', methods=['POST'])
def apply_for_session():
    data = request.json
    session_id, gender, name, email = data.get('session_id'), data.get('gender'), data.get('name'), data.get('email')
    if not all([session_id, gender, name, email]):
        return jsonify({"success": False, "message": "모든 정보를 입력해주세요."}), 400
    conn = get_db_connection()
    existing = conn.execute('SELECT * FROM participants WHERE email = ?', (email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": False, "message": "이미 신청한 이메일입니다."}), 400
    count = conn.execute('SELECT COUNT(*) FROM participants WHERE session_id = ? AND gender = ?', (session_id, gender)).fetchone()[0]
    if count >= MAX_SLOTS_PER_GENDER:
        conn.close()
        return jsonify({"success": False, "message": "죄송합니다. 해당 세션의 정원이 마감되었습니다."}), 400
    conn.execute('INSERT INTO participants (name, email, gender, session_id) VALUES (?, ?, ?, ?)', (name, email, gender, session_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"{session_id.replace('_', ' ').title()}에 성공적으로 신청되었습니다!"})


# ▼▼▼ 관리자 페이지 기능 추가 ▼▼▼

@app.route('/admin')
def admin_page():
    """관리자 페이지: 모든 참가자 목록을 보여주는 HTML 페이지를 렌더링"""
    conn = get_db_connection()
    # 신청 시간 순으로 정렬하여 모든 참가자 정보를 가져옴
    participants = conn.execute('SELECT * FROM participants ORDER BY timestamp DESC').fetchall()
    conn.close()
    return render_template('admin.html', participants=participants)

@app.route('/download_csv')
def download_csv():
    """참가자 목록을 CSV 파일로 다운로드하는 기능"""
    conn = get_db_connection()
    participants = conn.execute('SELECT id, name, email, gender, session_id, timestamp FROM participants ORDER BY timestamp ASC').fetchall()
    conn.close()
    
    # CSV 데이터를 메모리에서 생성
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 헤더(열 이름) 작성
    writer.writerow(['ID', 'Name', 'Email', 'Gender', 'Session_ID', 'Timestamp'])
    
    # 데이터 작성
    for participant in participants:
        writer.writerow(participant)
    
    output.seek(0)
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=participants.csv"}
    )

# ▲▲▲ 여기까지 추가 ▲▲▲


with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
