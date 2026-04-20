import os
import json
import time 
import requests
import urllib3
from kafka import KafkaConsumer, KafkaProducer

# --- SECURITY & LOGGING ---
# Disable SSL warnings for the Lightning AI cloud link
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- PATHS & CONFIG (TEAM-FRIENDLY) ---
# 1. Get the folder worker.py is in (viora/services/vision)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Go up one level to the services folder (viora/services)
SERVICES_DIR = os.path.dirname(CURRENT_DIR)

# 3. Create the exact path to viora/services/shared_data
# This ensures it works on every teammate's computer
SHARED_DATA = os.path.join(SERVICES_DIR, "shared_data")

# Cloud Endpoint
LIGHTNING_API_URL = "https://8080-01kpnz3jqdqvks5m41g07db8g5.cloudspaces.litng.ai/analyze"

# Kafka Broker
KAFKA_BROKER = "localhost:9092"

print("🚀 Connecting to Kafka...")
try:
    # We use a specific group_id to keep this worker's offset separate
    consumer = KafkaConsumer(
        'vision-request', 
        bootstrap_servers=KAFKA_BROKER,
        group_id='viora-vision-relay-group',
        auto_offset_reset='latest',
        enable_auto_commit=True
    )
    producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER)
    print("👁️ Local Vision Relay is ready. Forwarding images to Cloud...")
except Exception as e:
    print(f"❌ Kafka Connection Error: {e}")
    exit(1)

# --- PROCESSING LOOP (Robust Polling) ---
# We use .poll() to prevent 'Invalid file descriptor' errors on Windows
while True:
    raw_messages = consumer.poll(timeout_ms=1000)

    for topic_partition, messages in raw_messages.items():
        for message in messages:
            try:
                data = json.loads(message.value.decode('utf-8'))
                filename = data.get('file')
                req_id = data.get('request_id')
                
                image_path = os.path.join(SHARED_DATA, filename)
                
                # Wait for Windows to finish writing the file to the SSD
                if not os.path.exists(image_path):
                    time.sleep(0.5) 
                    if not os.path.exists(image_path):
                        print(f"⚠️ Warning: Image {filename} not found in {SHARED_DATA}")
                        continue

                print(f"☁️ Sending {filename} to Cloud API...")
                
                # 1. POST image to Lightning AI (bypassing strict SSL)
                with open(image_path, "rb") as img_file:
                    response = requests.post(
                        LIGHTNING_API_URL, 
                        files={"file": img_file},
                        verify=False,
                        timeout=45 # Increased timeout for heavy vision tasks
                    )
                    
                result = response.json()
                
                if result.get("status") == "success":
                    description = result["description"]
                    print(f"✅ Cloud Responded: {description}")
                    
                    # 2. Push result back to Kafka for the Logic Worker
                    producer.send('vision-response', json.dumps({
                        'description': description,
                        'request_id': req_id
                    }).encode('utf-8'))
                    
                    # Force the message out of the buffer immediately
                    producer.flush() 
                else:
                    print(f"❌ Cloud Error: {result.get('message')}")

            except Exception as e:
                print(f"❌ Relay Error: {e}")