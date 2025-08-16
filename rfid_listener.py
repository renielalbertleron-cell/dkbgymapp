from pynput import keyboard
import threading
import requests
import time

rfid_buffer = ''
last_time = time.time()

def send_rfid(rfid):
    try:
        res = requests.post('http://127.0.0.1:5000/process_rfid', json={'rfid': rfid})
        print(res.json()['message'])
    except Exception as e:
        print("❌ Server error:", e)

def on_press(key):
    global rfid_buffer, last_time

    try:
        char = key.char
        if time.time() - last_time > 1:
            rfid_buffer = ''
        rfid_buffer += char
        last_time = time.time()

    except AttributeError:
        if key == keyboard.Key.enter and rfid_buffer:
            threading.Thread(target=send_rfid, args=(rfid_buffer,)).start()
            print("📡 Sent:", rfid_buffer)
            rfid_buffer = ''

listener = keyboard.Listener(on_press=on_press)
listener.start()

print("✅ RFID keyboard listener started. Scan your tag...")
listener.join()
