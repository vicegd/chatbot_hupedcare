/*
=============================================================================
RAG WIDGET LOGIC
=============================================================================
This script runs in the user's browser. It creates the HTML elements on the 
fly, handles multiple languages (i18n), creates a typewriter text effect, 
and communicates with the FastAPI backend.
=============================================================================
*/

// 1. INTERNATIONALIZATION (i18n)
// Detect the browser language dynamically.
const browserLanguage = navigator.language.split('-')[0];
const supportedLanguages = ['es', 'en', 'pt', 'tr', 'pl'];
// Fallback to English if the browser language is not explicitly supported.
const currentLanguage = supportedLanguages.includes(browserLanguage) ? browserLanguage : 'en';

// UI translations dictionary.
const translations = {
    es: {
        header: "Asistente Virtual",
        typing: "Escribiendo...",
        placeholder: "Escribe tu mensaje...",
        welcome: "¡Hola! Soy tu asistente virtual. ¿En qué puedo ayudarte hoy?",
        error: "Lo siento, ocurrió un error: ",
        connectionError: "Error de conexión. Por favor, verifica tu conexión a internet o asegúrate de que el servidor está encendido."
    },
    en: {
        header: "Virtual Assistant",
        typing: "Typing...",
        placeholder: "Type your message...",
        welcome: "Hello! I'm your virtual assistant. How can I help you today?",
        error: "Sorry, an error occurred: ",
        connectionError: "Connection error. Please check your internet connection or ensure the server is running."
    },
    pt: {
        header: "Assistente Virtual",
        typing: "A escrever...",
        placeholder: "Escreva a sua mensagem...",
        welcome: "Ola! Sou o seu assistente virtual. Como posso ajudar hoje?",
        error: "Desculpe, ocorreu um erro: ",
        connectionError: "Erro de ligacao. Verifique a sua ligacao a internet ou confirme que o servidor esta ligado."
    },
    tr: {
        header: "Sanal Asistan",
        typing: "Yaziyor...",
        placeholder: "Mesajinizi yazin...",
        welcome: "Merhaba! Ben sanal asistaninizim. Bugun size nasil yardim edebilirim?",
        error: "Uzgunum, bir hata olustu: ",
        connectionError: "Baglanti hatasi. Lutfen internet baglantinizi kontrol edin veya sunucunun acik oldugundan emin olun."
    },
    pl: {
        header: "Wirtualny Asystent",
        typing: "Pisze...",
        placeholder: "Wpisz wiadomosc...",
        welcome: "Czesc! Jestem Twoim wirtualnym asystentem. Jak moge Ci dzisiaj pomoc?",
        error: "Przepraszam, wystapil blad: ",
        connectionError: "Blad polaczenia. Sprawdz polaczenie z internetem lub upewnij sie, ze serwer jest uruchomiony."
    },
};

// Runtime endpoint config loaded from web/chatbot-config.js.
// Supports `apiUrls` (preferred) and `apiUrl` (backward compatibility).
function resolveApiUrls() {
    const cfg = window.CHATBOT_CONFIG || {};
    const candidates = [];

    if (Array.isArray(cfg.apiUrls)) {
        for (const url of cfg.apiUrls) {
            if (typeof url === 'string' && url.trim()) {
                candidates.push(url.trim());
            }
        }
    }

    if (typeof cfg.apiUrl === 'string' && cfg.apiUrl.trim()) {
        candidates.push(cfg.apiUrl.trim());
    }

    const uniqueUrls = [];
    for (const url of candidates) {
        if (!uniqueUrls.includes(url)) {
            uniqueUrls.push(url);
        }
    }

    return uniqueUrls;
}

const apiUrls = resolveApiUrls();
let preferredApiIndex = null;

document.addEventListener('DOMContentLoaded', function() {
    // 2. DOM INJECTION
    // Build the toggle button dynamically.
    const toggleButton = document.createElement('button');
    toggleButton.id = 'chatbot-button';
    toggleButton.innerHTML = `
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2ZM20 16H5.17L4 17.17V4H20V16Z" fill="white"/>
            <path d="M7 9H17V11H7V9ZM7 12H15V14H7V12Z" fill="white"/>
        </svg>
    `;
    document.body.appendChild(toggleButton);

    // Build the full widget markup at runtime so it can be dropped into any page with one script tag.
    const chatWindow = document.createElement('div');
    chatWindow.id = 'chatbot-window';
    chatWindow.innerHTML = `
        <div id="chatbot-header">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-right: 8px;">
                <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V11H13V17ZM13 9H11V7H13V9Z" fill="white"/>
            </svg>
            ${translations[currentLanguage].header}
        </div>
        <div id="chatbot-messages">
            <div class="message bot">${translations[currentLanguage].welcome}</div>
        </div>
        <div id="chatbot-input-area">
            <input type="text" id="chatbot-input" placeholder="${translations[currentLanguage].placeholder}">
            <button id="chatbot-send">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M2.01 21L23 12 2.01 3 2 10L17 12 2 14L2.01 21Z" fill="white"/>
                </svg>
            </button>
        </div>
    `;
    document.body.appendChild(chatWindow);

    // 3. UI INTERACTIONS
    const messagesContainer = document.getElementById('chatbot-messages');
    const messageInput = document.getElementById('chatbot-input');
    const sendButton = document.getElementById('chatbot-send');

    // Toggle window visibility with animations
    toggleButton.addEventListener('click', function() {
        if (chatWindow.style.display === 'flex') {
            chatWindow.style.animation = 'slideDown 0.3s ease-in';
            setTimeout(() => { chatWindow.style.display = 'none'; }, 300);
        } else {
            chatWindow.style.display = 'flex';
            chatWindow.style.animation = 'slideUp 0.3s ease-out';
        }
    });

    // Simulated streaming text effect for a natural feel
    function typeWriter(element, text, speed = 5) {
        let i = 0;
        element.innerHTML = '';
        function type() {
            if (i < text.length) {
                element.innerHTML += text.charAt(i);
                i++;
                messagesContainer.scrollTop = messagesContainer.scrollHeight; 
                setTimeout(type, speed);
            } else {
                // Italicize source markers after the typing animation finishes for better readability
                element.innerHTML = element.innerHTML.replace(/\((source:[^)]+)\)/gi, '<i>($1)</i>');
            }
        }
        type();
    }

    function addMessage(text, sender, isTyping = false) {
        const msg = document.createElement('div');
        msg.className = 'message ' + sender;
        
        if (isTyping) {
            msg.innerHTML = '<span class="typing">' + translations[currentLanguage].typing + '</span>';
            msg.id = 'typing-indicator';
            messagesContainer.appendChild(msg);
        } else {
            // FIX: Remove the "Typing..." indicator before appending the real answer
            const typingIndicator = document.getElementById('typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
            
            messagesContainer.appendChild(msg);
            typeWriter(msg, text);
        }
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // 4. API COMMUNICATION
    function sendMessage() {
        const question = messageInput.value.trim();
        if (question) {
            // A. Display user message and clear input
            addMessage(question, 'user');
            messageInput.value = '';
            
            // B. Display the "Typing..." loading state
            addMessage('', 'bot', true);

            // C. Send HTTP request to your FastAPI server
            if (apiUrls.length === 0) {
                addMessage(translations[currentLanguage].connectionError, 'bot');
                return;
            }

            const requestPayload = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question: question })
            };

            const tryEndpoint = (index) => {
                if (index >= apiUrls.length) {
                    addMessage(translations[currentLanguage].connectionError, 'bot');
                    return;
                }

                fetch(apiUrls[index], requestPayload)
                    .then(response => response.json())
                    .then(data => {
                        preferredApiIndex = index;

                        // Remove typing indicator and show the actual response
                        if (data.response) {
                            addMessage(data.response, 'bot');
                        } else if (data.error) {
                            addMessage(translations[currentLanguage].error + data.error, 'bot');
                        } else {
                            addMessage(translations[currentLanguage].connectionError, 'bot');
                        }
                    })
                    .catch(() => {
                        tryEndpoint(index + 1);
                    });
            };

            if (preferredApiIndex !== null && preferredApiIndex < apiUrls.length) {
                const stickyIndex = preferredApiIndex;

                // First try the last known-good endpoint.
                fetch(apiUrls[stickyIndex], requestPayload)
                    .then(response => response.json())
                    .then(data => {
                        preferredApiIndex = stickyIndex;

                        if (data.response) {
                            addMessage(data.response, 'bot');
                        } else if (data.error) {
                            addMessage(translations[currentLanguage].error + data.error, 'bot');
                        } else {
                            addMessage(translations[currentLanguage].connectionError, 'bot');
                        }
                    })
                    .catch(() => {
                        // If sticky endpoint fails, reset and retry from the start of the list.
                        preferredApiIndex = null;
                        tryEndpoint(0);
                    });
            } else {
                tryEndpoint(0);
            }
        }
    }

    // Bind events to the Send button and the Enter key
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});