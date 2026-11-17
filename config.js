// Settings of the site.
// legalApi: leave empty until the Legal Intelligence backend (legal-api/) is deployed.
// chatApi: address of the chat proxy (chat-server/) after you deploy it, e.g. "https://tradeline-chat.onrender.com".
//          While it is empty the chat shows an honest "AI engine is not connected" message and does not use up free generations.
window.TL_CONFIG = Object.assign({ legalApi: "", chatApi: "" }, window.TL_CONFIG || {});
