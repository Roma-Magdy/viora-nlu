import os
import json
import time
import threading
import cv2
from flask import Flask, render_template, Response, jsonify
from flask_socketio import SocketIO, emit
from kafka import KafkaProducer, KafkaConsumer

# --- ARABIC RENDERING FOR TERMINAL ---
import arabic_reshaper
from bidi.algorithm import get_display

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# --- DYNAMIC PATH CONFIGURATION (TEAM-FRIENDLY) ---
import os

# 1. Get the folder app.py is in (viora/dashboard)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Go up one level to the main folder (viora)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

# 3. Create the exact path to viora/services/shared_data
SHARED_DATA = os.path.join(PROJECT_ROOT, "services", "shared_data")

if not os.path.exists(SHARED_DATA):
    os.makedirs(SHARED_DATA)

# --- KAFKA CONFIGURATION ---
KAFKA_BROKER = "localhost:9092"
# Increased timeout to ensure connection is solid
producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, acks='all')

# --- GLOBAL STATE ---
outputFrame = None
frame_lock = threading.Lock()
hardware_lock = threading.Lock()
camera_thread = None
stop_event = threading.Event()

def fix_text(text: str) -> str:
    """Fixes Arabic text rendering for terminal logs."""
    if not text: return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except:
        return str(text)

# --- THE UI BRAIN: KAFKA RESULT LISTENER ---
def result_listener():
    """
    Listens for the full AI JSON payloads from 'final-action-ar'
    and uses the 'intent' and 'entities' to control the UI/Hardware.
    """
    consumer = KafkaConsumer(
        'final-action-ar', 
        bootstrap_servers=KAFKA_BROKER,
        group_id='dashboard-ui-group'
    )
    print(" Waiting for JSON payloads...")
    
    for message in consumer:
        try:
            full_payload = json.loads(message.value.decode('utf-8'))
            
            # 1. Extract the standard fields your team agreed on
            intent = full_payload.get('intent', 'unknown')
            viora_reply = full_payload.get('viora_response', 'حاضر، تم تنفيذ طلبك.')
            entities = full_payload.get('entities', {})

            # 2. Update the dashboard UI chat bubble
            socketio.emit('server_response', {'text': f"🗣️ {viora_reply}"})
            print(f"processed [{intent}] | Entities: {entities}")

            # ==========================================
            # FRONTEND/HARDWARE ROUTING LOGIC
            # ==========================================
            
            # --- Hardware Control ---
            if intent == "camera_control":
                # Use the entity Fanar extracted to decide start vs stop
                action = entities.get("camera_action", "start").lower()
                if action == "start":
                    if not camera_thread or not camera_thread.is_alive():
                        print("Hardware Action: Starting camera...")
                        start_camera_system()
                        socketio.emit('camera_status', {'status': 'on'})
                elif action == "stop":
                    print("Hardware Action: Stopping camera...")
                    stop_camera_system()
                    socketio.emit('camera_status', {'status': 'off'})
                    
            # --- Vision Tasks (Force Camera On) ---
            elif intent in ["scene_description", "object_detection"]:
                if not camera_thread or not camera_thread.is_alive():
                    print("Vision Task: Auto-starting camera...")
                    start_camera_system()
                    socketio.emit('camera_status', {'status': 'on'})

            # --- Software & Node.js Ready Placeholders ---
            elif intent == "open_document":
                doc_name = entities.get("document_name", "Unknown File")
                print(f"App Action: Frontend should open -> {doc_name}")
                # Example: socketio.emit('open_file', {'filename': doc_name})

            elif intent == "navigate_document":
                page = entities.get("page_number", 1)
                direction = entities.get("navigation_direction", "to")
                print(f"App Action: Scroll document {direction} page {page}")
                
            elif intent == "ocr_request":
                print("App Action: trigger OCR module.")

            elif intent == "hardware_error":
                # If the Logic worker tells us the camera was off when it shouldn't be
                print(f"Hardware Error: {entities.get('error_type')}")
                socketio.emit('camera_status', {'status': 'error', 'message': viora_reply})

        except Exception as e:
            print(f"UI Listener Error: {e}")

# Launch the listener in a background thread
threading.Thread(target=result_listener, daemon=True).start()

# --- CAMERA ENGINE (DroidCam) ---
def camera_engine():
    global outputFrame
    DROIDCAM_URL = "http://192.168.1.15:4747/video" 
    cap = cv2.VideoCapture(DROIDCAM_URL)
    
    if not cap.isOpened():
        print(f"❌ Connection to {DROIDCAM_URL} failed.")
        return

    print("✅ Camera link active.")
    while not stop_event.is_set():
        success, frame = cap.read()
        if success:
            frame = cv2.resize(frame, (1024, 768)) 
            with frame_lock: outputFrame = frame.copy()
            time.sleep(0.01) 
        else:
            time.sleep(0.5)
    cap.release()

# --- THE COMMAND HANDLER: TIMESTAMPED PRODUCER ---
@socketio.on('user_command')
def handle_message(data):
    user_text = data['text']
    print(f"🎤 User Command: {fix_text(user_text)}")
    timestamp = int(time.time())
    filename = f"capture_{timestamp}.jpg"
    
    # Capture Frame
    with frame_lock:
        if outputFrame is not None:
            save_path = os.path.join(SHARED_DATA, filename)
            cv2.imwrite(save_path, outputFrame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            print(f"📸 Image captured: {filename}")

    # Prepare Payload
    payload = {
        "text": user_text,
        "image_file": filename,
        "source": "dashboard",
        "timestamp": timestamp
    }
    
    # 2. Push to Kafka AND FORCE SEND
    try:
        print(f"Sending to Logic Worker...")
        producer.send('user-commands', json.dumps(payload).encode('utf-8'))
        producer.flush() # <--- THIS FORCES THE MESSAGE OUT NOW
        print(f"Message successfully flushed to Kafka.")
    except Exception as e:
        print(f"Producer Error: {e}")

# --- FLASK WEB ROUTES ---
@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/start_cam')
def start_cam():
    start_camera_system()
    socketio.emit('camera_status', {'status': 'on'})
    return jsonify({"status": "started"})

@app.route('/stop_cam')
def stop_cam():
    stop_camera_system()
    socketio.emit('camera_status', {'status': 'off'})
    return jsonify({"status": "stopped"})

@app.route('/video_feed')
def video_feed():
    def gen():
        while True:
            if stop_event.is_set(): break
            with frame_lock:
                if outputFrame is None:
                    time.sleep(0.05); continue
                (flag, encodedImage) = cv2.imencode(".jpg", outputFrame)
            if not flag: continue
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + encodedImage.tobytes() + b'\r\n\r\n')
            time.sleep(0.05) 
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- HARDWARE HELPERS ---
def start_camera_system():
    global camera_thread
    with hardware_lock:
        if camera_thread and camera_thread.is_alive(): return
        stop_event.clear()
        camera_thread = threading.Thread(target=camera_engine, daemon=True)
        camera_thread.start()

def stop_camera_system():
    global camera_thread
    with hardware_lock:
        if camera_thread and camera_thread.is_alive():
            stop_event.set()
            camera_thread.join(timeout=1.0)
            camera_thread = None

if __name__ == '__main__':
    socketio.run(app, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)