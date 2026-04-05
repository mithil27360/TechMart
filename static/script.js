document.addEventListener('DOMContentLoaded', () => {

  // Password toggle
  const toggle = document.getElementById('togglePassword');
  const pwInput = document.getElementById('password');
  
  const eyeIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-eye"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0z"/><circle cx="12" cy="12" r="3"/></svg>`;
  const eyeOffIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-eye-off"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>`;

  if (toggle && pwInput) {
    // Set initial icon
    toggle.innerHTML = eyeOffIcon;
    
    toggle.addEventListener('click', () => {
      const isPassword = pwInput.type === 'password';
      pwInput.type = isPassword ? 'text' : 'password';
      toggle.innerHTML = isPassword ? eyeIcon : eyeOffIcon;
    });
  }

  // Search Suggestions
  const searchInput = document.getElementById('navSearchInput');
  const suggestionsBox = document.getElementById('searchSuggestions');

  if (searchInput && suggestionsBox) {
    searchInput.addEventListener('input', async (e) => {
      const q = e.target.value.trim();
      if (q.length < 2) {
        suggestionsBox.innerHTML = '';
        suggestionsBox.classList.remove('show');
        return;
      }

      try {
        const res = await fetch(`/api/search/suggestions?q=${encodeURIComponent(q)}`);
        const suggestions = await res.json();
        
        if (suggestions.length > 0) {
          suggestionsBox.innerHTML = suggestions.map(s => `
            <a href="/browse?q=${encodeURIComponent(s.title)}" class="suggestion-item">
              <div style="display:flex; align-items:center; gap:8px;">
                ${s.primary_image ? `<img src="/static/uploads/${s.primary_image}" style="width:24px;height:24px;border-radius:4px;object-fit:cover;">` : `<span style="display:inline-block;width:24px;height:24px;border-radius:4px;background:var(--grey-100);text-align:center;line-height:24px;font-size:0.7rem;">📦</span>`}
                <span class="s-title">${s.title}</span>
              </div>
              <span class="s-price">₹${s.price.toLocaleString()}</span>
            </a>
          `).join('');
          suggestionsBox.classList.add('show');
        } else {
          suggestionsBox.innerHTML = '';
          suggestionsBox.classList.remove('show');
        }
      } catch (err) {
        console.error('Suggestions error:', err);
      }
    });

    // Close suggestions on blur / click outside
    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
        suggestionsBox.classList.remove('show');
      }
    });
  }

  // Auto-dismiss flash messages after 4s
  const flashWrap = document.getElementById('flashWrap');
  if (flashWrap) {
    setTimeout(() => {
      flashWrap.style.transition = 'opacity 0.5s ease';
      flashWrap.style.opacity = '0';
      setTimeout(() => flashWrap.remove(), 500);
    }, 4000);
  }

});

async function markAsRead(notifId) {
  const card = document.getElementById('notif-' + notifId);
  if (!card || card.classList.contains('read')) return;

  try {
    // Standardized to POST to match app.py
    const res = await fetch('/notifications/read/' + notifId, { method: 'POST' });
    if (res.ok) {
      card.classList.remove('unread');
      card.classList.add('read');
      const badge = card.querySelector('.notif-badge');
      if (badge) {
        badge.textContent = 'READ';
        badge.classList.remove('new');
        badge.classList.add('read');
      }
      
      // Update sidebar badge
      const sidebarBadge = document.querySelector('.nav-item span.badge');
      if (sidebarBadge) {
        const currentCount = parseInt(sidebarBadge.textContent);
        if (currentCount <= 1) {
          sidebarBadge.remove();
        } else {
          sidebarBadge.textContent = currentCount - 1;
        }
      }
    }
  } catch (e) {
    console.error('Mark as read failed:', e);
  }
}

function simulatePurchase(itemTitle) {
  // Create a toast notification
  const toast = document.createElement('div');
  toast.className = 'purchase-toast';
  toast.innerHTML = `
    <div class="toast-content">
      <span class="toast-icon">✨</span>
      <div class="toast-text">
        <strong>Interested!</strong>
        <p>Your interest in ${itemTitle} has been recorded. The seller will be notified.</p>
      </div>
    </div>
  `;
  document.body.appendChild(toast);

  // Animate toast
  setTimeout(() => toast.classList.add('show'), 10);
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}
