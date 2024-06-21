class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.buffer = [];
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (input.length > 0) {
            const inputChannel = input[0];
            this.buffer.push(...inputChannel);
            if (this.buffer.length >= 2048) {
                this.port.postMessage(this.buffer);
                this.buffer = [];
            }
        }
        return true;
    }
}

registerProcessor('audio-processor', AudioProcessor);
