// Plugin del chatbot profesional con internacionalización

// Detectar idioma del navegador
const userLang = navigator.language.split('-')[0];
const supportedLangs = ['es', 'en', 'pt', 'tr', 'pl'];
const currentLang = supportedLangs.includes(userLang) ? userLang : 'en';

// Traducciones
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
    // Crear elementos del chatbot
    const button = document.createElement('button');
    button.id = 'chatbot-button';
    button.innerHTML = `
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2ZM20 16H5.17L4 17.17V4H20V16Z" fill="white"/>
            <path d="M7 9H17V11H7V9ZM7 12H15V14H7V12Z" fill="white"/>
        </svg>
    `;
    document.body.appendChild(button);

    const window = document.createElement('div');
    window.id = 'chatbot-window';
    window.innerHTML = `
        <div id="chatbot-header">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-right: 8px;">
                <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V11H13V17ZM13 9H11V7H13V9Z" fill="white"/>
            </svg>
            ${translations[currentLang].header}
        </div>
        <div id="chatbot-messages">
            <div class="message bot">${translations[currentLang].welcome}</div>
        </div>
        <div id="chatbot-input-area">
            <input type="text" id="chatbot-input" placeholder="${translations[currentLang].placeholder}">
            <button id="chatbot-send">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M2.01 21L23 12 2.01 3 2 10L17 12 2 14L2.01 21Z" fill="white"/>
                </svg>
            </button>
        </div>
    `;
    document.body.appendChild(window);

    // Funcionalidad
    const messages = document.getElementById('chatbot-messages');
    const input = document.getElementById('chatbot-input');
    const send = document.getElementById('chatbot-send');

    button.addEventListener('click', function() {
        if (window.style.display === 'flex') {
            window.style.animation = 'slideDown 0.3s ease-in';
            setTimeout(() => {
                window.style.display = 'none';
            }, 300);
        } else {
            window.style.display = 'flex';
            window.style.animation = 'slideUp 0.3s ease-out';
        }
    });

    function typeWriter(element, text, speed = 5) {
        let i = 0;
        element.innerHTML = '';
        function type() {
            if (i < text.length) {
                element.innerHTML += text.charAt(i);
                i++;
                messages.scrollTop = messages.scrollHeight; // Scroll automático
                setTimeout(type, speed);
            } else {
                // Aplicar cursiva a fuentes después de completar el typing
                element.innerHTML = element.innerHTML.replace(/\((source:[^)]+)\)/gi, '<i>($1)</i>');
            }
        }
        type();
    }

    function addMessage(text, sender, isTyping = false) {
        const msg = document.createElement('div');
        msg.className = 'message ' + sender;
        if (isTyping) {
            msg.innerHTML = '<span class="typing">' + translations[currentLang].typing + '</span>';
            msg.id = 'typing-indicator';
        } else {
            // Si no es typing, iniciar el efecto de escritura
            messages.appendChild(msg);
            typeWriter(msg, text);
            return; // No hacer scroll aquí, se hará en typeWriter si necesario
        }
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
        return msg;
    }

    function sendMessage() {
        const question = input.value.trim();
        if (question) {
            addMessage(question, 'user');
            input.value = '';

            // Enviar al servidor
            fetch('http://127.0.0.1:8000/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question: question })
            })
            .then(response => response.json())
            .then(data => {
                if (data.response) {
                    addMessage(data.response, 'bot');
                } else if (data.error) {
                    addMessage(translations[currentLang].error + data.error, 'bot');
                }
            })
            .catch(error => {
                addMessage(translations[currentLang].connectionError, 'bot');
            });
        }
    }

    send.addEventListener('click', sendMessage);
    input.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});