import os
import json
import time
from kafka import KafkaConsumer, KafkaProducer

# Local Import for your NLU model
from fanar_nlu import fanar_nlu

# --- CONFIGURATION ---
KAFKA_BROKER = "localhost:9092"

print("Attempting to connect to Kafka...")

try:
    consumer = KafkaConsumer(
        'user-commands', 
        'vision-response', 
        bootstrap_servers=KAFKA_BROKER,
        group_id='viora-logic-group-v5', # Fresh group ID
        auto_offset_reset='earliest', 
        enable_auto_commit=True
    )
    producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER)
    print("Viora Logic Worker is Active...")
except Exception as e:
    print(f"❌ Connection Error: {e}")
    exit(1)

pending_requests = {}

# --- HELPER: JSON EXTRACTION ---
def extract_full_payload(nlu_object):
    if hasattr(nlu_object, 'model_dump'): return nlu_object.model_dump()
    if hasattr(nlu_object, 'dict'): return nlu_object.dict()
    if isinstance(nlu_object, dict): return nlu_object.copy()
    return vars(nlu_object).copy()

# --- MAIN LOOP (ROBUST POLLING FOR ML PIPELINES) ---
print("Waiting for messages...")

while True:
    # 1. Manually poll for messages every 1 second (1000ms)
    # This keeps the Windows network socket healthy and active.
    raw_messages = consumer.poll(timeout_ms=1000)

    for topic_partition, messages in raw_messages.items():
        for message in messages:
            try:
                data = json.loads(message.value.decode('utf-8'))
                topic = message.topic

                # --- STAGE 1: NLU Intent Classification ---
                if topic == 'user-commands':
                    user_text = data.get('text', '')
                    image_file = data.get('image_file')
                    request_id = data.get('timestamp')
                    
                    # Ask Fanar & extract the FULL JSON
                    nlu_result = fanar_nlu(user_text)
                    full_payload = extract_full_payload(nlu_result)
                    
                    intent = full_payload.get('intent', 'unknown')
                    print(f"Intent: {intent} | Full Payload Captured.")

                    # AI Pipeline Routing 
                    if intent in ["scene_description", "object_detection"]:
                        if image_file:
                            pending_requests[request_id] = user_text
                            print(f"Forwarding to Florence-2: {image_file}")
                            producer.send('vision-request', json.dumps({
                                'file': image_file,
                                'request_id': request_id,
                                'intent': intent
                            }).encode('utf-8'))
                        else:
                            # Inject hardware error into the payload but keep the original NLU data
                            full_payload['intent'] = 'hardware_error'
                            full_payload['viora_response'] = "عذراً، الكاميرا مقفولة. افتحها عشان أقدر أساعدك."
                            full_payload['entities']['error_type'] = 'camera_missing'
                            producer.send('final-action-ar', json.dumps(full_payload).encode('utf-8'))
                    
                    else:
                        producer.send('final-action-ar', json.dumps(full_payload).encode('utf-8'))

                # --- STAGE 2: Vision Response Handling ---
                elif topic == 'vision-response':
                    description_en = data.get('description')
                    req_id = data.get('request_id')
                    original_query = pending_requests.pop(req_id, "إيه اللي قدامي؟")
                    
                    synthesis_prompt = f"User asked: '{original_query}'. Vision model saw: '{description_en}'. Respond in Educated Egyptian Amia."
                    final_nlu = fanar_nlu(synthesis_prompt)
                    
                    final_payload = extract_full_payload(final_nlu)
                    final_payload['intent'] = 'FINISH_VISION_TASK'
                    
                    if 'entities' not in final_payload or not final_payload['entities']:
                        final_payload['entities'] = {}
                    final_payload['entities']['english_description'] = description_en
                    
                    producer.send('final-action-ar', json.dumps(final_payload).encode('utf-8'))

            except Exception as e:
                print(f"Loop Error processing message: {e}")