const PETAPETA_URL = 'https://shinsei99.github.io/project/scrapmemo-petapeta/';

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'clip-text',
    title: 'PetaPetaに送る',
    contexts: ['selection']
  });
  chrome.contextMenus.create({
    id: 'clip-image',
    title: 'PetaPetaに送る（画像）',
    contexts: ['image']
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const data = {
    type: info.menuItemId === 'clip-image' ? 'image' : 'text',
    content: info.menuItemId === 'clip-image' ? info.srcUrl : info.selectionText,
    sourceUrl: tab.url
  };

  const existing = await chrome.tabs.query({ url: PETAPETA_URL + '*' });

  if (existing.length > 0) {
    await chrome.tabs.update(existing[0].id, { active: true });
    chrome.scripting.executeScript({
      target: { tabId: existing[0].id },
      func: dispatch,
      args: [data]
    });
  } else {
    const newTab = await chrome.tabs.create({ url: PETAPETA_URL });
    chrome.tabs.onUpdated.addListener(function wait(tabId, info) {
      if (tabId === newTab.id && info.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(wait);
        setTimeout(() => {
          chrome.scripting.executeScript({
            target: { tabId: newTab.id },
            func: dispatch,
            args: [data]
          });
        }, 800);
      }
    });
  }
});

function dispatch(data) {
  window.dispatchEvent(new CustomEvent('petapeta-clip', { detail: data }));
}
