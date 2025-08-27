export function scrollChatToBottom() {
  const messagesContainer = document.querySelector('.chat-messages');
  if (!messagesContainer) return;
  const style = getComputedStyle(messagesContainer);
  const hasOwnScroller = (style.overflowY !== 'visible' && style.overflowY !== 'unset');
  if (hasOwnScroller && messagesContainer.scrollHeight > messagesContainer.clientHeight + 1) {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  } else {
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
  }
}


