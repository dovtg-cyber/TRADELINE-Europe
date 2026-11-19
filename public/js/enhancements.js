(() => {
  'use strict';

  function escLocal(s) { return String(s ?? '').replace(/[&<>\"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c])); }

  function directLinks(text) {
    if (typeof text !== 'string') return '';
    return text.replace(/https?:\/\/[^\s<]+/g, url => {
      const clean = url.replace(/[.,;:!?]+$/, '');
      const punctuation = url.slice(clean.length);
      return `<a class="lk2 tl-source-link" href="${escLocal(clean)}" target="_blank" rel="noopener noreferrer">${escLocal(clean)}</a>${punctuation}`;
    });
  }

  if (typeof md === 'function') {
    const originalMd = md;
    md = function(text) { return directLinks(originalMd(text)); };
  }

  function addChatToolbar(chat) {
    if (!chat || chat.dataset.tlToolbar) return;
    chat.dataset.tlToolbar = '1';
    chat.classList.add('tl-chat-shell');

    const toolbar = document.createElement('div');
    toolbar.className = 'tl-chat-toolbar';
    toolbar.innerHTML = '<button type="button" class="g tl-chat-icon" data-tl-history="1" title="Chat history" aria-label="Chat history">☰</button><button type="button" class="g tl-chat-icon" data-tl-full="1" title="Expand chat" aria-label="Expand chat">⛶</button><button type="button" class="g tl-chat-icon" data-tl-close="1" title="Close chat" aria-label="Close chat">×</button>';
    chat.insertBefore(toolbar, chat.firstChild);

    let history = chat.querySelector('.tl-history');
    if (!history) {
      history = document.createElement('aside');
      history.className = 'tl-history';
      chat.insertBefore(history, chat.querySelector('#chm'));
    }

    toolbar.querySelector('[data-tl-full]').addEventListener('click', () => {
      const expanded = chat.classList.toggle('tl-expanded');
      toolbar.querySelector('[data-tl-full]').textContent = expanded ? '↙' : '⛶';
      toolbar.querySelector('[data-tl-full]').title = expanded ? 'Restore chat' : 'Expand chat';
    });

    toolbar.querySelector('[data-tl-close]').addEventListener('click', () => {
      if (chat.classList.contains('tl-expanded')) chat.classList.remove('tl-expanded','tl-with-history');
      else chat.style.display = chat.style.display === 'none' ? '' : 'none';
    });

    toolbar.querySelector('[data-tl-history]').addEventListener('click', () => {
      if (!chat.classList.contains('tl-expanded')) chat.classList.add('tl-expanded');
      chat.classList.toggle('tl-with-history');
      if (chat.classList.contains('tl-with-history')) renderHistory(history);
    });
  }

  function renderHistory(container) {
    if (typeof cdb !== 'function') return;
    const db = cdb();
    container.innerHTML = '<b style="display:block;padding:6px 4px">Chats</b><button type="button" class="tl-history-item" data-tl-new>＋ New chat</button>' +
      db.threads.map(t => `<button type="button" class="tl-history-item ${t.id === db.cur ? 'on' : ''}" data-tl-thread="${escLocal(t.id)}">${escLocal(t.title || 'Untitled chat')}</button>`).join('');
    container.querySelector('[data-tl-new]').addEventListener('click', () => { if (typeof newChat === 'function') newChat(); });
    container.querySelectorAll('[data-tl-thread]').forEach(button => button.addEventListener('click', () => {
      if (typeof openChat === 'function') openChat(button.dataset.tlThread);
    }));
  }

  function enhanceJournal() {
    document.querySelectorAll('.home-journal-placeholder').forEach(el => el.remove());
    document.querySelectorAll('h2').filter
      ? null
      : null;
    const headings = [...document.querySelectorAll('h2')].filter(h => /from the journal/i.test(h.textContent));
    headings.forEach(head => {
      if (head.dataset.tlStrip) return;
      let node = head.nextElementSibling;
      const cards = [];
      while (node && node.matches('.it')) { cards.push(node); node = node.nextElementSibling; }
      if (!cards.length) return;
      head.dataset.tlStrip = '1';
      const wrap = document.createElement('div');
      wrap.className = 'tl-journal-wrap';
      const strip = document.createElement('div');
      strip.className = 'tl-journal-strip';
      cards.slice(0,5).forEach(card => {
        const clone = card.cloneNode(true);
        clone.className = 'tl-journal-card';
        strip.appendChild(clone);
      });
      const more = document.createElement('button');
      more.type = 'button';
      more.className = 'tl-journal-card tl-journal-more';
      more.innerHTML = '<b>View all</b><span class="sm mu">Open TRADELINE Journal →</span>';
      more.addEventListener('click', () => { if (typeof go === 'function') go('journal'); });
      strip.appendChild(more);
      cards.forEach(card => card.remove());
      wrap.appendChild(strip);
      head.after(wrap);
    });
  }

  function enhancePayment() {
    document.querySelectorAll('[onclick*="clm("]').forEach(button => {
      if (button.dataset.tlProcessing) return;
      button.dataset.tlProcessing = '1';
      button.addEventListener('click', () => {
        setTimeout(() => {
          const card = button.closest('.card');
          if (!card || card.querySelector('.tl-payment-processing')) return;
          card.insertAdjacentHTML('beforeend', '<div class="tl-payment-processing"><b>Payment processing</b><br><span class="sm mu">Please wait while we verify your payment. This usually takes about one minute. If it takes longer, write to <a class="lk2" href="mailto:gdm120609@gmail.com">gdm120609@gmail.com</a> or <a class="lk2" href="mailto:dovtg@icloud.com">dovtg@icloud.com</a>, or call <a class="lk2" href="tel:+48793683931">+48 793 683 931</a>.</span></div>');
        }, 0);
      }, {once:true});
    });
  }

  function enhanceNav() {
    document.querySelectorAll('nav').forEach(nav => {
      if (nav.querySelector('[data-tl-contact]')) return;
      const journal = [...nav.querySelectorAll('a')].find(a => /journal/i.test(a.textContent));
      if (!journal) return;
      const contact = document.createElement('a');
      contact.dataset.tlContact = '1';
      contact.href = 'mailto:gdm120609@gmail.com';
      contact.textContent = 'Contact';
      nav.insertBefore(contact, journal.nextSibling);
    });
  }

  const CRM_KEY = 'tlcrmchat';
  function crmStore() { try { return JSON.parse(localStorage.getItem(CRM_KEY) || '{}'); } catch (_) { return {}; } }
  function crmSave(store) { try { localStorage.setItem(CRM_KEY, JSON.stringify(store)); } catch (_) {} }

  function openCrmChat(clientId, clientName) {
    if (!clientId) return;
    const old = document.getElementById('tl-client-chat-modal');
    if (old) old.remove();
    const store = crmStore();
    const messages = store[clientId] || [];
    const modal = document.createElement('div');
    modal.id = 'tl-client-chat-modal';
    modal.className = 'tl-client-chat-modal';
    modal.innerHTML = `<div class="row" style="justify-content:space-between"><h2 style="margin:0">Chat with ${escLocal(clientName || 'client')}</h2><button type="button" class="g tl-chat-icon" id="tl-crm-close">×</button></div><div class="chat tl-client-chat-modal-chat" style="margin-top:10px"><div id="tl-crm-messages" class="chm">${messages.map(m => `<div class="msg ${m.role === 'admin' ? 'me' : ''}">${escLocal(m.text)}</div>`).join('')}</div><div><textarea id="tl-crm-input" placeholder="Write a message…"></textarea><div class="row"><button type="button" id="tl-crm-send">Send</button></div></div></div>`;
    document.body.appendChild(modal);
    document.getElementById('tl-crm-close').addEventListener('click', () => modal.remove());
    document.getElementById('tl-crm-send').addEventListener('click', () => {
      const input = document.getElementById('tl-crm-input');
      const text = input.value.trim();
      if (!text) return;
      const current = crmStore();
      current[clientId] = current[clientId] || [];
      current[clientId].push({role:'admin',text,ts:Date.now()});
      crmSave(current);
      const line = document.createElement('div');
      line.className = 'msg me';
      line.textContent = text;
      document.getElementById('tl-crm-messages').appendChild(line);
      input.value = '';
      if (typeof notify === 'function') notify(clientId, 'New message from TRADELINE', text);
    });
  }

  function enhanceCrm() {
    if (!me || me.role !== 'admin') return;
    document.querySelectorAll('a.it[onclick*="cid="]').forEach(link => {
      if (link.querySelector('.tl-crm-chat-link') || !link.getAttribute('onclick')) return;
      const match = link.getAttribute('onclick').match(/cid='([^']+)'/);
      if (!match) return;
      const name = link.querySelector('b')?.textContent || 'client';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'g tl-crm-chat-link';
      button.textContent = 'Chat';
      button.addEventListener('click', event => { event.prevent; event.stopPropagation(); openCrmChat(match[1], name); });
      link.after(button);
    });
  }

  function run() {
    document.querySelectorAll('.chat').forEach(addChatToolbar);
    enhanceJournal();
    enhancePayment();
    enhanceNav();
    enhanceCrm();
  }

  const observer = new MutationObserver(() => run());
  observer.observe(document.documentElement, {childList:true,subtree:true});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
