document.addEventListener('DOMContentLoaded', () => {

  // password show/hide toggle
  const toggle = document.getElementById('togglePassword');
  const pwInput = document.getElementById('password');
  
  // svg icons for eye open/closed
  const eyeOpen = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-eye"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0z"/><circle cx="12" cy="12" r="3"/></svg>`;
  const eyeClosed = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-eye-off"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>`;

  if (toggle && pwInput) {
    toggle.innerHTML = eyeClosed;
    toggle.addEventListener('click', () => {
      const showing = pwInput.type === 'password';
      pwInput.type = showing ? 'text' : 'password';
      toggle.innerHTML = showing ? eyeOpen : eyeClosed;
    });
  }

  // live search suggestions
  const searchBox = document.getElementById('navSearchInput');
  const dropdown = document.getElementById('searchSuggestions');

  if (searchBox && dropdown) {
    const spinner = document.getElementById('searchSpinner');
    
    searchBox.addEventListener('input', async (e) => {
      const q = e.target.value.trim();
      
      // dont search for super short queries
      if (q.length < 2) {
        dropdown.innerHTML = '';
        dropdown.classList.remove('show');
        if (spinner) spinner.classList.remove('active');
        return;
      }

      if (spinner) spinner.classList.add('active');
      
      try {
        const res = await fetch(`/api/search/suggestions?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        
        if (spinner) spinner.classList.remove('active');
        
        if (data.length > 0) {
          // build suggestion html
          let html = '';
          for (let s of data) {
            let imgHtml = '';
            if (s.primary_image) {
              imgHtml = `<img src="/static/uploads/${s.primary_image}" style="width:24px;height:24px;border-radius:4px;object-fit:cover;">`;
            } else {
              imgHtml = `<span style="display:inline-block;width:24px;height:24px;border-radius:4px;background:var(--grey-100);text-align:center;line-height:24px;font-size:0.7rem;">📦</span>`;
            }
            
            html += `
              <a href="/browse?q=${encodeURIComponent(s.title)}" class="suggestion-item">
                <div style="display:flex; align-items:center; gap:8px;">
                  ${imgHtml}
                  <span class="s-title">${s.title}</span>
                </div>
                <span class="s-price">₹${s.price.toLocaleString()}</span>
              </a>
            `;
          }
          dropdown.innerHTML = html;
          dropdown.classList.add('show');
        } else {
          dropdown.innerHTML = '';
          dropdown.classList.remove('show');
        }
      } catch (err) {
        console.log('search error:', err);
      }
    });

    // close dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!searchBox.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.remove('show');
      }
    });
  }

  // role card selection on register page
  const roleInputs = document.querySelectorAll('input[name="role"]');
  if (roleInputs.length > 0) {
    function updateCards() {
      roleInputs.forEach(radio => {
        const card = radio.nextElementSibling;
        if (radio.checked) {
          card.style.borderColor = 'var(--blue)';
          card.style.background = 'var(--blue-50)';
          card.style.transform = 'translateY(-2px)';
          card.style.boxShadow = '0 4px 12px rgba(0, 113, 227, 0.1)';
        } else {
          card.style.borderColor = 'var(--grey-200)';
          card.style.background = 'transparent';
          card.style.transform = 'none';
          card.style.boxShadow = 'none';
        }
      });
    }
    roleInputs.forEach(r => r.addEventListener('change', updateCards));
    updateCards();
  }

  // auto dismiss flash messages
  const flashMsg = document.getElementById('flashWrap');
  if (flashMsg) {
    setTimeout(() => {
      flashMsg.style.transition = 'opacity 0.5s ease';
      flashMsg.style.opacity = '0';
      setTimeout(() => flashMsg.remove(), 500);
    }, 4000);
  }

});

// mark notification as read
async function markAsRead(notifId) {
  const card = document.getElementById('notif-' + notifId);
  if (!card || card.classList.contains('read')) return;

  try {
    const res = await fetch('/notifications/read/' + notifId, { method: 'POST' });
    if (res.ok) {
      card.classList.remove('unread');
      card.classList.add('read');
      
      // update the badge text
      const badge = card.querySelector('.notif-badge');
      if (badge) {
        badge.textContent = 'READ';
        badge.classList.remove('new');
        badge.classList.add('read');
      }
      
      // update sidebar count
      const countBadge = document.querySelector('.nav-item span.badge');
      if (countBadge) {
        const num = parseInt(countBadge.textContent);
        if (num <= 1) {
          countBadge.remove();
        } else {
          countBadge.textContent = num - 1;
        }
      }
    }
  } catch (e) {
    console.log('couldnt mark as read:', e);
  }
}

// toast popup when user shows interest
function simulatePurchase(itemTitle) {
  const toast = document.createElement('div');
  toast.className = 'purchase-toast';
  toast.innerHTML = `
    <div class="toast-content">
      <span class="toast-icon">✨</span>
      <div class="toast-text">
        <strong>Interested!</strong>
        <p>Your interest in ${itemTitle} has been noted.</p>
      </div>
    </div>
  `;
  document.body.appendChild(toast);

  // show and then hide after a few seconds
  setTimeout(() => toast.classList.add('show'), 10);
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}
