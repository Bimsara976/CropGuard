/* CropGuard — Client-side JavaScript
   Copyright U.J Tharushi Thathsarani w1953807 2025-2026 */

'use strict';

// ── Mobile navbar ────────────────────────────────────────────────────────────
(function () {
  const hamburger  = document.getElementById('hamburger-btn');
  const mobileMenu = document.getElementById('mobile-menu');
  if (!hamburger || !mobileMenu) return;

  hamburger.addEventListener('click', () => {
    mobileMenu.classList.toggle('open');
    hamburger.setAttribute('aria-expanded',
      mobileMenu.classList.contains('open'));
  });

  // Close when clicking outside
  document.addEventListener('click', (e) => {
    if (!hamburger.contains(e.target) && !mobileMenu.contains(e.target)) {
      mobileMenu.classList.remove('open');
    }
  });
})();

// ── Flash message dismiss ────────────────────────────────────────────────────
document.querySelectorAll('.alert-close').forEach((btn) => {
  btn.addEventListener('click', () => {
    const alert = btn.closest('.alert');
    if (alert) {
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-4px)';
      alert.style.transition = 'opacity .25s, transform .25s';
      setTimeout(() => alert.remove(), 260);
    }
  });
});

// Auto-dismiss success/info flashes after 5 seconds
setTimeout(() => {
  document.querySelectorAll('.alert-success, .alert-info').forEach((el) => {
    el.style.opacity = '0';
    el.style.transition = 'opacity .4s';
    setTimeout(() => el.remove(), 420);
  });
}, 5000);

// ── Upload zone ──────────────────────────────────────────────────────────────
(function () {
  const zone           = document.getElementById('upload-zone');
  const fileInput      = document.getElementById('file-input');
  const previewWrap    = document.getElementById('image-preview-wrap');
  const previewImg     = document.getElementById('image-preview');
  const previewName    = document.getElementById('preview-name');
  const uploadForm     = document.getElementById('upload-form');
  const submitBtn      = document.getElementById('submit-btn');
  const loadingOverlay = document.getElementById('loading-overlay');

  if (!uploadForm) return;   // not on upload page

  // ── Tab switching ─────────────────────────────────────────────
  const tabUpload = document.getElementById('tab-upload');
  const tabCamera = document.getElementById('tab-camera');
  const panelUpload = document.getElementById('panel-upload');
  const panelCamera = document.getElementById('panel-camera');

  if (tabUpload && tabCamera) {
    tabUpload.addEventListener('click', () => {
      tabUpload.classList.add('active');
      tabCamera.classList.remove('active');
      panelUpload.style.display = '';
      panelCamera.style.display = 'none';
    });
    tabCamera.addEventListener('click', () => {
      tabCamera.classList.add('active');
      tabUpload.classList.remove('active');
      panelCamera.style.display = '';
      panelUpload.style.display = 'none';
    });
  }

  // ── File upload zone ──────────────────────────────────────────
  if (zone && fileInput) {
    zone.addEventListener('click', () => fileInput.click());

    ['dragenter', 'dragover'].forEach((evt) => {
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
      });
    });
    ['dragleave', 'drop'].forEach((evt) => {
      zone.addEventListener(evt, () => zone.classList.remove('dragover'));
    });
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) handleFile(fileInput.files[0]);
    });
  }

  function handleFile(file) {
    const allowed = ['image/jpeg', 'image/png', 'image/jpg'];
    if (!allowed.includes(file.type)) {
      showZoneError('Please select a JPG or PNG image file.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      showZoneError('File size must be under 10 MB.');
      return;
    }
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;

    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      previewName.textContent = file.name + '  (' + (file.size / 1024).toFixed(1) + ' KB)';
      previewWrap.style.display = 'block';
      if (submitBtn) submitBtn.disabled = false;
    };
    reader.readAsDataURL(file);
  }

  function showZoneError(msg) {
    if (!zone) return;
    let err = zone.querySelector('.zone-error');
    if (!err) {
      err = document.createElement('p');
      err.className = 'zone-error';
      err.style.cssText = 'color:#c62828;font-size:.82rem;margin-top:.5rem;';
      zone.appendChild(err);
    }
    err.textContent = msg;
    setTimeout(() => err && err.remove(), 4000);
  }

  // ── Form submit ───────────────────────────────────────────────
  uploadForm.addEventListener('submit', (e) => {
    if (!fileInput.files || !fileInput.files.length) {
      e.preventDefault();
      showZoneError('Please select or capture an image before submitting.');
      return;
    }
    if (loadingOverlay) loadingOverlay.classList.add('show');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Analysing...';
    }
  });
})();

// ── DroidCam capture ─────────────────────────────────────────────────────────
(function () {
  const btnConnect  = document.getElementById('btn-connect');
  const btnCapture  = document.getElementById('btn-capture');
  const btnRetake   = document.getElementById('btn-retake');
  const urlInput    = document.getElementById('droidcam-url');
  const feedImg     = document.getElementById('droidcam-feed');
  const placeholder = document.getElementById('feed-placeholder');
  const feedError   = document.getElementById('feed-error');
  const feedErrMsg  = document.getElementById('feed-error-msg');
  const canvas      = document.getElementById('capture-canvas');
  const fileInput   = document.getElementById('file-input');
  const previewWrap = document.getElementById('image-preview-wrap');
  const previewImg  = document.getElementById('image-preview');
  const previewName = document.getElementById('preview-name');
  const submitBtn   = document.getElementById('submit-btn');

  if (!btnConnect) return;   // DroidCam panel not on page

  let feedConnected = false;

  // ── Connect button ────────────────────────────────────────────
  btnConnect.addEventListener('click', () => {
    const url = (urlInput.value || '').trim();
    if (!url) {
      feedErrMsg.textContent = 'Please enter a DroidCam URL.';
      showError();
      return;
    }

    // Reset state
    feedImg.style.display   = 'none';
    feedError.style.display = 'none';
    placeholder.style.display = 'flex';
    btnCapture.disabled = true;
    feedConnected = false;

    btnConnect.disabled = true;
    btnConnect.textContent = 'Connecting…';

    // Set the img src — DroidCam /video is an MJPEG stream
    // Browsers render MJPEG streams natively via <img>
    feedImg.onload = () => {
      placeholder.style.display = 'none';
      feedError.style.display   = 'none';
      feedImg.style.display     = 'block';
      btnCapture.disabled       = false;
      feedConnected             = true;
      btnConnect.disabled       = false;
      btnConnect.textContent    = 'Reconnect';
    };

    feedImg.onerror = () => {
      feedErrMsg.textContent =
        'Could not connect to DroidCam. Make sure your phone and PC are on the same Wi-Fi network and DroidCam is running.';
      showError();
      btnConnect.disabled   = false;
      btnConnect.textContent = 'Connect';
    };

    // Cache-bust to force reload each connect attempt
    feedImg.src = url + (url.includes('?') ? '&' : '?') + '_t=' + Date.now();
  });

  function showError() {
    placeholder.style.display = 'none';
    feedImg.style.display     = 'none';
    feedError.style.display   = 'flex';
    btnCapture.disabled       = true;
  }

  // ── Capture button ────────────────────────────────────────────
  btnCapture.addEventListener('click', () => {
    if (!feedConnected || feedImg.style.display === 'none') return;

    // Draw current frame to canvas
    const w = feedImg.naturalWidth  || feedImg.width  || 640;
    const h = feedImg.naturalHeight || feedImg.height || 480;
    canvas.width  = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(feedImg, 0, 0, w, h);

    canvas.toBlob((blob) => {
      if (!blob) {
        feedErrMsg.textContent =
          'Could not capture frame. The browser may be blocking cross-origin image data. ' +
          'Try accessing DroidCam via http (not https).';
        showError();
        return;
      }

      const filename = 'droidcam_capture_' + Date.now() + '.jpg';
      const file = new File([blob], filename, { type: 'image/jpeg' });

      // Inject into the form's file input
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files = dt.files;

      // Show preview
      const reader = new FileReader();
      reader.onload = (e) => {
        previewImg.src = e.target.result;
        previewName.textContent = 'DroidCam capture  (' + (blob.size / 1024).toFixed(1) + ' KB)';
        previewWrap.style.display = 'block';
        if (submitBtn) submitBtn.disabled = false;
      };
      reader.readAsDataURL(blob);

      // Pause the live feed visually to show the captured frame
      feedImg.style.display = 'none';
      previewWrap.scrollIntoView({ behavior: 'smooth', block: 'center' });
      btnRetake.style.display = 'inline-flex';
    }, 'image/jpeg', 0.92);
  });

  // ── Retake button ─────────────────────────────────────────────
  btnRetake.addEventListener('click', () => {
    // Clear captured image
    fileInput.value         = '';
    previewWrap.style.display = 'none';
    if (submitBtn) submitBtn.disabled = true;
    btnRetake.style.display = 'none';

    // Restore live feed
    feedImg.style.display = 'block';
  });
})();

// ── Probability bar animation (result page) ──────────────────────────────────
(function () {
  const fills = document.querySelectorAll('.prob-bar-fill');
  if (!fills.length) return;

  // Animate on load using IntersectionObserver
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const el  = entry.target;
        const pct = el.getAttribute('data-pct') || '0';
        el.style.width = pct + '%';
        observer.unobserve(el);
      }
    });
  }, { threshold: 0.2 });

  fills.forEach((fill) => {
    fill.style.width = '0%';
    observer.observe(fill);
  });
})();

// ── Frequency bar animation (dashboard) ──────────────────────────────────────
(function () {
  const fills = document.querySelectorAll('.freq-fill');
  if (!fills.length) return;

  fills.forEach((fill) => {
    const target = fill.getAttribute('data-width') || '0';
    fill.style.width = '0%';
    requestAnimationFrame(() => {
      setTimeout(() => { fill.style.width = target + '%'; fill.style.transition = 'width .7s ease'; }, 200);
    });
  });
})();

// ── Password strength ────────────────────────────────────────────────────────
(function () {
  const pwInput  = document.getElementById('password');
  const indicator= document.getElementById('pw-strength');
  if (!pwInput || !indicator) return;

  pwInput.addEventListener('input', () => {
    const v = pwInput.value;
    let score = 0;
    if (v.length >= 6)  score++;
    if (v.length >= 10) score++;
    if (/[A-Z]/.test(v)) score++;
    if (/[0-9]/.test(v)) score++;
    if (/[^A-Za-z0-9]/.test(v)) score++;

    const labels = ['', 'Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'];
    const colors = ['', '#c62828', '#e65100', '#bdc741', '#2d6a4f', '#1b4332'];
    indicator.textContent  = labels[score] || '';
    indicator.style.color  = colors[score] || '';
  });
})();
