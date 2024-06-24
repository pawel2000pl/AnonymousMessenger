"use strict";

function constrain(x, min, max) {
    return x < min ? min : x > max ? max : x;
}

function arrayAbsMax(array) {
    let max = 0;
    for (let i=0;i<array.length;i++) {
        const abs = Math.abs(array[i]);
        if (abs > max)
            max = abs;
    }
    return max;
}

function resample(array, srcSample, dstSample) { 
    const arrayTime = array.length / srcSample;
    const newLength = Math.round(arrayTime * dstSample);
    let newArray = new Array(newLength);
    let j = 0;
    let increment = array.length / newLength;
    for (let i=0;i<newArray.length;i++)
        newArray[i] = array[Math.floor(increment * j++)];
    return newArray;
}

async function startAudioStream() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    let audioContext = new AudioContext();
    let audioSource = audioContext.createMediaStreamSource(stream);
    await audioContext.audioWorklet.addModule('/audio_processor.js');
    const audioProcessorNode = new AudioWorkletNode(audioContext, 'audio-processor');

    const gainNode = audioContext.createGain();
    const biquadFilter = new BiquadFilterNode(audioContext, {
        type: "lowpass",
        frequency: 8000
    });

    audioSource.connect(audioProcessorNode);  

    var stopStreamEvent = ()=>{};
    var muted = false;
    
    const stopStream = function() {
        stopStreamEvent();
        audioSource.disconnect();
        audioProcessorNode.disconnect();
    };


    const playAudioFragment = function(audioData) {
        if (audioContext === null)
            return;    

        const audioBufferSource = audioContext.createBufferSource(); 
        audioBufferSource.connect(gainNode); 
        gainNode.connect(biquadFilter);
        biquadFilter.connect(audioContext.destination);

        const audioBuffer = audioContext.createBuffer(1, audioData.length, audioContext.sampleRate);
        audioBuffer.getChannelData(0).set(audioData.map(value=>value/127));
        audioBufferSource.buffer = audioBuffer;
        audioBufferSource.start();
    };

    const protocol = window.location.protocol == "http:" ? "ws:" : "wss:";
    let ws_audio = new WebSocket(protocol + "//"+window.location.host+"/audio");
    var SERVER_SAMPLE_RATE = 8000;

    ws_audio.onopen = ()=>{
        ws_audio.send(JSON.stringify({"action": "subscribe", "userhash": userhash, token: localStorage.token??""}));
        ws_audio.onmessage = async (message)=>{
            if (!(message.data instanceof ArrayBuffer || message.data instanceof Blob)) {
                const settings = JSON.parse(message.data);
                if (settings.sample_rate != undefined) SERVER_SAMPLE_RATE = settings.sample_rate;
            } else {
                playAudioFragment(resample(new Int8Array(await message.data.arrayBuffer()), SERVER_SAMPLE_RATE, audioContext.sampleRate));
            }
        };
        ws_audio.onclose = stopStream;

        audioProcessorNode.port.onmessage = (event) => {
            const audioData = event.data.map((value)=>constrain(Math.round(127*value), -127, 127));            
            if (audioData[0] == 123) 
                audioData[0] = 122;
            const absMax = arrayAbsMax(audioData);
            gainNode.gain.setValueAtTime(muted ? 1 : (1 - absMax/768), audioContext.currentTime);
            if (!muted && absMax != 0)
                ws_audio.send(new Int8Array(resample(audioData, audioContext.sampleRate, SERVER_SAMPLE_RATE)).buffer);
        };
    };

    return {
        close: ()=>{audioProcessorNode.port.onmessage = ()=>{}; ws_audio.close();},
        onclose: (event)=>{stopStreamEvent = event;},
        setMute: (value)=>{muted = value;},
        getMute: ()=>muted
    };
}


const voiceChatDetails = document.getElementById('voice-chat-details');
const joinChatBtn = document.getElementById('join-voice-chat');
const leaveChatBtn = document.getElementById('leave-voice-chat');
const muteChatBtn = document.getElementById('mute-voice-chat');
const unmuteChatBtn = document.getElementById('unmute-voice-chat');

(async ()=>{
    const response = await fetch('/query/allow_audio_stream');
    const result = await response.json();
    if (result.status === "ok" && result.result && navigator.mediaDevices !== undefined)
        voiceChatDetails.style.display = '';
})();

var voiceChatStatus = null;

function refreshVoiceChatInterface() {
    if (voiceChatStatus === null) {
        joinChatBtn.style.display = '';
        leaveChatBtn.style.display = 'none';
        muteChatBtn.style.display = 'none';
        unmuteChatBtn.style.display = 'none';
    } else {
        joinChatBtn.style.display = 'none';
        leaveChatBtn.style.display = '';
        if (voiceChatStatus.getMute()) {
            muteChatBtn.style.display = 'none';
            unmuteChatBtn.style.display = '';
        } else {
            muteChatBtn.style.display = '';
            unmuteChatBtn.style.display = 'none';
        }
    }
}

joinChatBtn.onclick = async ()=>{
    voiceChatStatus = await startAudioStream();
    refreshVoiceChatInterface();
    voiceChatStatus.onclose(()=>{
        voiceChatStatus = null;
        refreshVoiceChatInterface();
        notification.play();
    });
};

leaveChatBtn.onclick = async ()=>{
    voiceChatStatus.close();
    voiceChatStatus.onclose(()=>{});
    voiceChatStatus = null;
    refreshVoiceChatInterface();
};

muteChatBtn.onclick = async ()=>{
    voiceChatStatus.setMute(true);
    refreshVoiceChatInterface();
};

unmuteChatBtn.onclick = async ()=>{
    voiceChatStatus.setMute(false);
    refreshVoiceChatInterface();
};

refreshVoiceChatInterface();


