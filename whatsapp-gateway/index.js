const { makeWASocket, useMultiFileAuthState, DisconnectReason, delay, downloadMediaMessage } = require('@whiskeysockets/baileys');
const QRCode = require('qrcode');
const axios = require('axios');

async function updateBackendStatus(status, qrCodeData = "") {
    try {
        await axios.post('http://localhost:8000/api/update-status', {
            status: status,
            qr_code: qrCodeData
        });
    } catch (err) {
        console.error("Failed to sync status with Python backend:", err.message);
    }
}

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys');

    const sock = makeWASocket({
        auth: state,
        browser: ["Ubuntu", "Chrome", "20.0.04"]
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            const qrImageBase64 = await QRCode.toDataURL(qr);
            await updateBackendStatus("DISCONNECTED", qrImageBase64);
        }

        if (connection === 'close') {
            await updateBackendStatus("DISCONNECTED", "");
            const shouldReconnect = (lastDisconnect.error?.output?.statusCode !== DisconnectReason.loggedOut);
            if (shouldReconnect) connectToWhatsApp();
        } else if (connection === 'open') {
            console.log('✅ WhatsApp Agent Ready!');
            await updateBackendStatus("CONNECTED", "");
        }
    });

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify') return;
        const msg = messages[0];
        if (!msg.message || msg.key.fromMe) return;

        const senderJid = msg.key.remoteJid;
        const senderName = msg.pushName || senderJid.split('@')[0];

        await delay(Math.floor(Math.random() * 2000) + 2000);
        await sock.sendPresenceUpdate('composing', senderJid);

        let payload = { sender: senderName, type: 'text', text: '', mediaB64: null };
        const messageType = Object.keys(msg.message)[0];

        if (messageType === 'conversation' || messageType === 'extendedTextMessage') {
            payload.text = msg.message.conversation || msg.message.extendedTextMessage.text;
        } else if (messageType === 'audioMessage') {
            payload.type = 'audio';
            const buffer = await downloadMediaMessage(msg, 'buffer', {});
            payload.mediaB64 = buffer.toString('base64');
        } else if (messageType === 'imageMessage') {
            payload.type = 'image';
            payload.text = msg.message.imageMessage.caption || '';
            const buffer = await downloadMediaMessage(msg, 'buffer', {});
            payload.mediaB64 = buffer.toString('base64');
        }

        try {
            const response = await axios.post('http://localhost:8000/whatsapp-webhook', payload);
            
            if (response.data.reply) {
                await sock.sendPresenceUpdate('paused', senderJid);
                await sock.sendMessage(senderJid, { text: response.data.reply }, { quoted: msg });
            }
        } catch (err) {
            console.error('Error forwarding message:', err.message);
        }
    });
}

connectToWhatsApp();