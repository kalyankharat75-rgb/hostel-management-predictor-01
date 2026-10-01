// Hostel Maintenance Predictor - Master Interactive Engine
document.addEventListener('DOMContentLoaded', () => {

  // -------------------------------------------------------------
  // 1. AUTO-DISMISS FLASH ALERTS
  // -------------------------------------------------------------
  const flashAlerts = document.querySelectorAll('.flash-alert');
  flashAlerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 400);
    }, 5000);
  });

  // -------------------------------------------------------------
  // 2. COMPLAINT REGISTRATION: CASCADING & REAL-TIME IMPACT PREVIEW
  // -------------------------------------------------------------
  const floorSelect = document.getElementById('floor-select');
  const roomSelect = document.getElementById('room-select');
  const assetSelect = document.getElementById('asset-select');
  const issueSelect = document.getElementById('issue-type-select');
  const affectedInput = document.getElementById('affected-count');
  const descTextarea = document.getElementById('description');
  const duplicateAlertBox = document.getElementById('duplicate-alert-box');
  const duplicateDetails = document.getElementById('duplicate-details');
  const proceedDuplicateBtn = document.getElementById('proceed-duplicate-btn');
  const confirmedDuplicateInput = document.getElementById('confirmed-duplicate-input');

  // Real-time Impact Score Preview Box
  const impactPreviewBadge = document.getElementById('impact-preview-badge');
  const impactScoreValue = document.getElementById('impact-score-value');
  const charCountSpan = document.getElementById('char-count');

  function updateLiveImpactScore() {
    if (!assetSelect || !affectedInput) return;
    const selectedOption = assetSelect.options[assetSelect.selectedIndex];
    const assetTxt = selectedOption ? selectedOption.textContent.toLowerCase() : '';

    let weight = 1;
    if (assetTxt.includes('fan') || assetTxt.includes('light') || assetTxt.includes('switchboard') || assetTxt.includes('electrical')) {
      weight = 3;
    } else if (assetTxt.includes('geyser') || assetTxt.includes('tap') || assetTxt.includes('plumbing')) {
      weight = 2;
    }

    const students = parseInt(affectedInput.value) || 1;
    const score = students * weight;

    if (impactScoreValue) impactScoreValue.textContent = score;
    if (impactPreviewBadge) {
      if (score >= 9) {
        impactPreviewBadge.style.background = '#fee2e2';
        impactPreviewBadge.style.color = '#991b1b';
        impactPreviewBadge.style.borderColor = '#fca5a5';
      } else if (score >= 6) {
        impactPreviewBadge.style.background = '#fef3c7';
        impactPreviewBadge.style.color = '#92400e';
        impactPreviewBadge.style.borderColor = '#fde68a';
      } else {
        impactPreviewBadge.style.background = '#e0e7ff';
        impactPreviewBadge.style.color = '#3730a3';
        impactPreviewBadge.style.borderColor = '#c7d2fe';
      }
    }
  }

  if (affectedInput) affectedInput.addEventListener('input', updateLiveImpactScore);
  if (assetSelect) assetSelect.addEventListener('change', updateLiveImpactScore);

  if (descTextarea && charCountSpan) {
    descTextarea.addEventListener('input', () => {
      charCountSpan.textContent = `${descTextarea.value.length} characters`;
    });
  }

  // Cascading Floor -> Room
  if (floorSelect && roomSelect) {
    floorSelect.addEventListener('change', async () => {
      const fl = floorSelect.value;
      roomSelect.innerHTML = '<option value="">-- Choose Room --</option>';
      if (assetSelect) {
        assetSelect.innerHTML = '<option value="">-- Select Room First --</option>';
        assetSelect.disabled = true;
      }
      if (duplicateAlertBox) duplicateAlertBox.style.display = 'none';

      if (!fl) {
        roomSelect.disabled = true;
        return;
      }

      roomSelect.disabled = true;
      roomSelect.innerHTML = '<option value="">Loading rooms...</option>';

      try {
        const res = await fetch(`/api/rooms?floor=${encodeURIComponent(fl)}`);
        const rooms = await res.json();
        roomSelect.disabled = false;
        roomSelect.innerHTML = '<option value="">-- Choose Room --</option>';
        rooms.forEach(r => {
          const opt = document.createElement('option');
          opt.value = r;
          opt.textContent = `Room ${r}`;
          roomSelect.appendChild(opt);
        });
      } catch (err) {
        console.error('Error fetching rooms:', err);
        roomSelect.disabled = false;
      }
    });

    // Cascading Room -> Assets
    roomSelect.addEventListener('change', async () => {
      const rm = roomSelect.value;
      if (!assetSelect) return;
      assetSelect.innerHTML = '<option value="">-- Choose Asset --</option>';
      if (duplicateAlertBox) duplicateAlertBox.style.display = 'none';

      if (!rm) {
        assetSelect.disabled = true;
        return;
      }

      assetSelect.disabled = true;
      assetSelect.innerHTML = '<option value="">Loading assets...</option>';

      try {
        const res = await fetch(`/api/assets?room_no=${encodeURIComponent(rm)}`);
        const assets = await res.json();
        assetSelect.disabled = false;
        assetSelect.innerHTML = '<option value="">-- Choose Asset --</option>';
        assets.forEach(a => {
          const opt = document.createElement('option');
          opt.value = a.id;
          opt.textContent = `${a.asset_code} (${a.asset_type})`;
          assetSelect.appendChild(opt);
        });
      } catch (err) {
        console.error('Error fetching assets:', err);
        assetSelect.disabled = false;
      }
    });

    // Duplicate Check on Asset Select (Feature 6)
    if (assetSelect) {
      assetSelect.addEventListener('change', async () => {
        const aid = assetSelect.value;
        if (duplicateAlertBox) duplicateAlertBox.style.display = 'none';
        if (confirmedDuplicateInput) confirmedDuplicateInput.value = '0';
        if (!aid) return;

        try {
          const res = await fetch(`/api/check_duplicate?asset_id=${encodeURIComponent(aid)}`);
          const data = await res.json();
          if (data.exists) {
            const c = data.complaint;
            duplicateDetails.innerHTML = `
              <strong>Active Ticket #${c.id}:</strong> ${c.asset_code} in Room ${c.room_no} has an active issue:<br>
              <strong>Status:</strong> <span style="text-decoration:underline;">${c.status}</span> &bull; 
              <strong>Issue:</strong> ${c.issue_type} (Filed: ${c.date_filed})<br>
              <em style="color:#78350f;">"${c.description}"</em>
            `;
            duplicateAlertBox.style.display = 'block';
            duplicateAlertBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
        } catch (err) {
          console.error('Error checking duplicate:', err);
        }
      });
    }

    if (proceedDuplicateBtn) {
      proceedDuplicateBtn.addEventListener('click', () => {
        if (confirmedDuplicateInput) confirmedDuplicateInput.value = '1';
        duplicateAlertBox.style.background = '#f1f5f9';
        duplicateAlertBox.style.borderColor = '#cbd5e1';
        duplicateDetails.innerHTML = `<span style="color:#10b981; font-weight:700;">✓ Duplicate warning acknowledged. You may now submit your independent complaint.</span>`;
        proceedDuplicateBtn.style.display = 'none';
      });
    }
  }

  // -------------------------------------------------------------
  // 3. ADMIN DASHBOARD: REAL-TIME CLIENT-SIDE INSTANT FILTERING
  // -------------------------------------------------------------
  const liveTableSearch = document.getElementById('liveTableSearch');
  const complaintsTable = document.querySelector('.data-table tbody');

  if (liveTableSearch && complaintsTable) {
    liveTableSearch.addEventListener('input', () => {
      const q = liveTableSearch.value.toLowerCase().trim();
      const rows = complaintsTable.querySelectorAll('tr');

      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        if (text.includes(q)) {
          row.style.display = '';
        } else {
          row.style.display = 'none';
        }
      });
    });
  }

  // Quick Filter Chips (All, Pending, In Progress, Resolved)
  window.filterTableByStatus = function(statusFilter, btn) {
    const rows = complaintsTable ? complaintsTable.querySelectorAll('tr') : [];
    const filterButtons = document.querySelectorAll('.filter-chip');
    filterButtons.forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');

    rows.forEach(row => {
      if (statusFilter === 'all') {
        row.style.display = '';
      } else if (statusFilter === 'replacement') {
        if (row.innerHTML.includes('Needs Replacement')) {
          row.style.display = '';
        } else {
          row.style.display = 'none';
        }
      } else {
        const statusBadge = row.querySelector('.status-badge');
        if (statusBadge && statusBadge.textContent.toLowerCase().includes(statusFilter.toLowerCase())) {
          row.style.display = '';
        } else {
          row.style.display = 'none';
        }
      }
    });
  };

  // -------------------------------------------------------------
  // 4. ADMIN RESOLUTION MODAL
  // -------------------------------------------------------------
  window.openResolutionModal = function(complaintId, currentResolvedBy) {
    const modal = document.getElementById('resolutionModal');
    const form = document.getElementById('resolutionForm');
    const complaintIdSpan = document.getElementById('modalComplaintId');
    const resolvedByInput = document.getElementById('modalResolvedBy');

    if (modal && form) {
      form.action = `/admin/complaint/${complaintId}/update_status`;
      if (complaintIdSpan) complaintIdSpan.textContent = complaintId;
      if (resolvedByInput && currentResolvedBy) {
        resolvedByInput.value = currentResolvedBy;
      }
      modal.classList.add('show');
    }
  };

  window.closeResolutionModal = function() {
    const modal = document.getElementById('resolutionModal');
    if (modal) modal.classList.remove('show');
  };

  const modal = document.getElementById('resolutionModal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeResolutionModal();
    });
  }

  // -------------------------------------------------------------
  // 5. VISUAL HEATMAP: INTERACTIVE ROOM QUICK-INSPECT MODAL
  // -------------------------------------------------------------
  window.inspectRoomFromHeatmap = async function(roomNo, floorNo, count, label) {
    const modal = document.getElementById('heatmapRoomModal');
    if (!modal) return;

    document.getElementById('modalRoomTitle').textContent = `Room ${roomNo} (Floor ${floorNo})`;
    document.getElementById('modalRoomCount').textContent = count;
    document.getElementById('modalRoomLabel').textContent = label;
    document.getElementById('modalRoomActionBtn').href = `/admin?floor=${floorNo}&search=${roomNo}`;
    document.getElementById('modalFileForRoomBtn').href = `/complaint/new`;

    const assetsContainer = document.getElementById('modalRoomAssets');
    assetsContainer.innerHTML = '<span style="color:var(--text-muted);">Loading room assets...</span>';

    modal.classList.add('show');

    try {
      const res = await fetch(`/api/assets?room_no=${encodeURIComponent(roomNo)}`);
      const assets = await res.json();
      if (assets.length === 0) {
        assetsContainer.innerHTML = '<em>No assets registered.</em>';
      } else {
        assetsContainer.innerHTML = assets.map(a => `
          <a href="/asset/${a.id}" class="badge-normal" style="padding: 6px 12px; background: white; border: 1.5px solid var(--border-color); text-decoration: none; color: var(--text-main); font-weight: 700; border-radius: var(--radius-sm); transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
            🔧 ${a.asset_code} (${a.asset_type}) &rarr;
          </a>
        `).join('');
      }
    } catch (e) {
      assetsContainer.innerHTML = '<span style="color:red;">Failed to load assets.</span>';
    }
  };

  window.closeHeatmapModal = function() {
    const modal = document.getElementById('heatmapRoomModal');
    if (modal) modal.classList.remove('show');
  };

  // -------------------------------------------------------------
  // 6. TREND PREDICTIONS LIVE SEARCH & FILTERING
  // -------------------------------------------------------------
  const predSearch = document.getElementById('predSearchInput');
  const predTable = document.querySelector('.pred-table tbody');

  if (predSearch && predTable) {
    predSearch.addEventListener('input', () => {
      const query = predSearch.value.toLowerCase().trim();
      const rows = predTable.querySelectorAll('tr');
      rows.forEach(r => {
        r.style.display = r.textContent.toLowerCase().includes(query) ? '' : 'none';
      });
    });
  }

  window.filterPredByRisk = function(level, btn) {
    if (!predTable) return;
    const filterButtons = document.querySelectorAll('.pred-filter-chip');
    filterButtons.forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');

    const rows = predTable.querySelectorAll('tr');
    rows.forEach(r => {
      if (level === 'all') {
        r.style.display = '';
      } else {
        r.style.display = r.textContent.toLowerCase().includes(level.toLowerCase()) ? '' : 'none';
      }
    });
  };
});
