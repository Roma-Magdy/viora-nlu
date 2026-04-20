// --- CONFIGURATION ---
const AZURE_KEY = "YOUR_AZURE_SPEECH_KEY_HERE";
const AZURE_REGION = "germanywestcentral";

// --- 1. SETUP SOCKET & UI ---
const socket = io();
const chatBox = document.getElementById("chat-box");
const micBtn = document.getElementById("mic-btn");

function addLog(sender, text) {
    const p = document.createElement("p");
    p.className = sender === "USER" ? "user-msg" : "ai-msg";
    p.innerText = `${sender}: ${text}`;
    chatBox.appendChild(p);
    chatBox.scrollTop = chatBox.scrollHeight;
}

socket.on('server_response', function(data) {
    addLog("VIORA", data.text);
});

// --- 2. CAMERA LOGIC ---
const videoImg = document.getElementById("video-feed");
const camBtn = document.getElementById("cam-btn");
const offlineText = document.getElementById("camera-offline-text");
let isCameraOn = false;

// Listen for AI Control (e.g. Llama starting/stopping camera)
socket.on('camera_status', function(data) {
    setCameraUI(data.status === 'on');
});

function setCameraUI(isOn) {
    isCameraOn = isOn;
    
    if (isOn) {
        // --- START ---
        // Add timestamp to prevent caching
        videoImg.src = "/video_feed?" + new Date().getTime(); 
        videoImg.style.display = "block";
        offlineText.style.display = "none";
        
        camBtn.innerText = "🛑 اقفل الكاميرا";
        camBtn.style.borderColor = "#ff0055";
        camBtn.style.color = "#ff0055";
    } else {
        // --- STOP ---
        // CRITICAL: Force browser to drop connection immediately
        videoImg.src = ""; 
        videoImg.removeAttribute("src");
        videoImg.style.display = "none";
        offlineText.style.display = "block";

        camBtn.innerText = "▶ افتح الكاميرا";
        camBtn.style.borderColor = "#00ff00";
        camBtn.style.color = "#00ff00";
    }
}

// Manual Button Click Logic
function toggleCamera() {
    camBtn.disabled = true; // Prevent double-clicking
    
    if (isCameraOn) {
        // REQUEST STOP
        camBtn.innerText = "⏳ جاري الإغلاق...";
        
        // 1. Cut the video feed FIRST manually (Frontend Fix)
        videoImg.src = "";
        videoImg.style.display = "none";
        
        // 2. Tell Server to kill hardware
        setTimeout(() => {
            fetch('/stop_cam').then(() => {
                camBtn.disabled = false;
                // Socket 'camera_status' will handle the final UI reset
            });
        }, 100);

    } else {
        // REQUEST START
        camBtn.innerText = "⏳ جاري التشغيل...";
        fetch('/start_cam').then(() => camBtn.disabled = false);
    }
}

// --- 3. MICROPHONE LOGIC (AZURE) ---
if (typeof SpeechSDK === "undefined") {
    addLog("SYSTEM", "❌ Error: Microsoft Speech SDK not loaded.");
} else {
    var speechConfig = SpeechSDK.SpeechConfig.fromSubscription(AZURE_KEY, AZURE_REGION);
    speechConfig.speechRecognitionLanguage = "ar-EG";
    var audioConfig = SpeechSDK.AudioConfig.fromDefaultMicrophoneInput();
    var recognizer = new SpeechSDK.SpeechRecognizer(speechConfig, audioConfig);
}

let isListening = false;

function toggleMic() {
    if (!isListening) startListening();
    else stopListening();
}

function startListening() {
    if (!recognizer) return;
    isListening = true;
    micBtn.innerText = "🛑 جاري الاستماع...";
    micBtn.classList.add("listening");
    
    recognizer.startContinuousRecognitionAsync();
    
    recognizer.recognizing = (s, e) => {
        // Optional: Log interim results
        // console.log(`Recognizing: ${e.result.text}`);
    };

    recognizer.recognized = (s, e) => {
        if (e.result.reason === SpeechSDK.ResultReason.RecognizedSpeech) {
            const text = e.result.text;
            addLog("USER", text);
            socket.emit('user_command', { text: text });
        }
    };
}

function stopListening() {
    if (!recognizer) return;
    isListening = false;
    micBtn.innerText = "🎤 اضغط للتحدث";
    micBtn.classList.remove("listening");
    recognizer.stopContinuousRecognitionAsync();
}