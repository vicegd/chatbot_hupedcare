// Professional chatbot plugin with internationalization support.

// Detect the browser language.
const browserLanguage = navigator.language.split('-')[0];
const supportedLanguages = ['es', 'en', 'pt', 'tr', 'pl'];
const currentLanguage = supportedLanguages.includes(browserLanguage) ? browserLanguage : 'en';

// UI translations.
const translations = {
    es: {
        header: "Asistente Virtual",
        typing: "Escribiendo...",
        placeholder: "Escribe tu mensaje...",
        welcome: "¡Hola! Soy tu asistente virtual. ¿En qué puedo ayudarte hoy?",
        error: "Lo siento, ocurrió un error: ",
        connectionError: "Error de conexión. Por favor, verifica tu conexión a internet."
    },
    en: {
        header: "Virtual Assistant",
        typing: "Typing...",
        placeholder: "Type your message...",
        welcome: "Hello! I'm your virtual assistant. How can I help you today?",
        error: "Sorry, an error occurred: ",
        connectionError: "Connection error. Please check your internet connection."
    },
    pt: {
        header: "Assistente Virtual",
        typing: "Digitando...",
        placeholder: "Digite sua mensagem...",
        welcome: "Olá! Sou seu assistente virtual. Como posso ajudá-lo hoje?",
        error: "Desculpe, ocorreu um erro: ",
        connectionError: "Erro de conexão. Por favor, verifique sua conexão com a internet."
    },
    tr: {
        header: "Sanal Asistan",
        typing: "Yazıyor...",
        placeholder: "Mesajınızı yazın...",
        welcome: "Merhaba! Ben sizin sanal asistanınızım. Bugün size nasıl yardımcı olabilirim?",
        error: "Üzgünüm, bir hata oluştu: ",
        connectionError: "Bağlantı hatası. Lütfen internet bağlantınızı kontrol edin."
    },
    pl: {
        header: "Asystent Wirtualny",
        typing: "Pisze...",
        placeholder: "Wpisz swoją wiadomość...",
        welcome: "Cześć! Jestem twoim wirtualnym asystentem. Jak mogę ci dziś pomóc?",
        error: "Przepraszam, wystąpił błąd: ",
        connectionError: "Błąd połączenia. Sprawdź swoje połączenie internetowe."
    }
};

document.addEventListener('DOMContentLoaded', function() {
    // Create the chatbot elements.
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

    // Wire up the interactive behavior.
    const messagesContainer = document.getElementById('chatbot-messages');
    const messageInput = document.getElementById('chatbot-input');
    const sendButton = document.getElementById('chatbot-send');

    toggleButton.addEventListener('click', function() {
        // Reuse CSS animations both when opening and closing the floating window.
        if (chatWindow.style.display === 'flex') {
            chatWindow.style.animation = 'slideDown 0.3s ease-in';
            setTimeout(() => {
                chatWindow.style.display = 'none';
            }, 300);
        } else {
            chatWindow.style.display = 'flex';
            chatWindow.style.animation = 'slideUp 0.3s ease-out';
        }
    });

    function typeWriter(element, text, speed = 5) {
        let i = 0;
        element.innerHTML = '';
        function type() {
            if (i < text.length) {
                // Append one character per tick to simulate streaming output.
                element.innerHTML += text.charAt(i);
                i++;
                messagesContainer.scrollTop = messagesContainer.scrollHeight; // Keep the latest message visible.
                setTimeout(type, speed);
            } else {
                // Italicize source markers after the typing animation finishes.
                element.innerHTML = element.innerHTML.replace(/\((source:[^)]+)\)/gi, '<i>($1)</i>');
            }
        }
        type();
    }

    function addMessage(text, sender, isTyping = false) {
        const msg = document.createElement('div');
        msg.className = 'message ' + sender;
        if (isTyping) {
            // A dedicated typing node makes it easy to replace or remove later.
            msg.innerHTML = '<span class="typing">' + translations[currentLanguage].typing + '</span>';
            msg.id = 'typing-indicator';
        } else {
            // Start the typewriter effect for regular messages.
            messagesContainer.appendChild(msg);
            typeWriter(msg, text);
            return; // Scrolling is handled inside typeWriter when needed.
        }
        messagesContainer.appendChild(msg);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        return msg;
    }

    function sendMessage() {
        const question = messageInput.value.trim();
        if (question) {
            // Echo the user message immediately so the UI feels responsive before the network round-trip.
            addMessage(question, 'user');
            messageInput.value = '';

            // Send the request to the backend.
            fetch('http://156.35.98.76:8000/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question: question })
            })
            .then(response => response.json())
            .then(data => {
                // The backend may return either a generated answer or a serialized error payload.
                if (data.response) {
                    addMessage(data.response, 'bot');
                } else if (data.error) {
                    addMessage(translations[currentLanguage].error + data.error, 'bot');
                }
            })
            .catch(error => {
                addMessage(translations[currentLanguage].connectionError, 'bot');
            });
        }
    }

    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});